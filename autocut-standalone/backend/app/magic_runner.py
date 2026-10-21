"""Sequential, checkpointed MAGICO execution; no UI automation or agent loop."""
import asyncio
import traceback
import uuid
from .magic_models import MagicContext, MagicOptions
from .magic_store import fingerprint
from .magic_services import MagicWaitingInput, MagicBudgetReached

PHASES = ('cut', 'editorial', 'research', 'selection', 'preparation', 'delivery')


class MagicCancelled(RuntimeError):
    pass


class MagicRunner:
    def __init__(self, store, services, source_signature, *, on_error=None):
        self.store, self.services, self.source_signature = store, services, source_signature
        self.tasks = {}
        self.on_error = on_error

    def start(self, project_id, options):
        row = self.store.create_or_resume(project_id, self.source_signature(project_id), options)
        if row['status'] in {'ready', 'partial'}:
            return row
        return self._schedule(row)

    def _schedule(self, row):
        run_id = row['run_id']
        if run_id in self.tasks and not self.tasks[run_id].done():
            return self.store.read(run_id)
        row = self.store.recover(run_id)
        if any(call['status'] == 'unknown' for call in row['calls'].values()):
            return row
        self.store.validate_source(run_id, self.source_signature(row['source_project_id']))
        row = self.store.transition(run_id, status='running', cancel_requested=False, error=None, diagnostics=None)
        self.tasks[run_id] = asyncio.create_task(self._run(run_id))
        return row

    def resume(self, run_id):
        return self._schedule(self.store.read(run_id))

    def restart(self, run_id):
        """Start a new MAGICO run while retaining the prior run and its artifacts."""
        previous = self.store.read(run_id)
        if run_id in self.tasks and not self.tasks[run_id].done():
            raise ValueError('MAGICO è ancora in corso: annullalo prima di ripartire da zero')
        self.store.validate_source(run_id, self.source_signature(previous['source_project_id']))
        row = self.store.create_or_resume(previous['source_project_id'], previous['source_signature'],
                                          previous['options'], fresh=True)
        return self._schedule(row)

    def retry_from(self, run_id, phase):
        """Rebuild only the research/selection tail of a durable MAGICO run.

        CUT and editorial checkpoints are immutable here: retrying coverage
        must never spend another transcript/director call or alter the CUT.
        """
        if phase not in {'research', 'selection'}:
            raise ValueError('Puoi ripetere soltanto ricerca o coperture MAGICO')
        row = self.store.read(run_id)
        if run_id in self.tasks and not self.tasks[run_id].done():
            return row
        self.store.validate_source(run_id, self.source_signature(row['source_project_id']))
        start = PHASES.index(phase)
        checkpoints = {name: value for name, value in row['checkpoints'].items()
                       if PHASES.index(name) < start}
        row = self.store.transition(run_id, checkpoints=checkpoints, status='queued',
            cancel_requested=False, error=None, diagnostics=None,
            message='Riprovo le coperture con CUT e piano editoriale già salvati')
        return self._schedule(row)

    def resend(self, run_id):
        row = self.store.read(run_id)
        if run_id in self.tasks and not self.tasks[run_id].done():
            return row
        self.store.validate_source(run_id,self.source_signature(row['source_project_id']))
        if 'preparation' not in row['checkpoints']:
            raise ValueError('Il pacchetto non è ancora pronto: premi RIPRENDI')
        journal = self.store._path(run_id).with_name('delivery.json')
        if journal.is_file():
            journal.rename(journal.with_name('delivery-history-'+uuid.uuid4().hex+'.json'))
        checkpoints = {k:v for k,v in row['checkpoints'].items() if k!='delivery'}
        row = self.store.transition(run_id,checkpoints=checkpoints,message='Invio il pacchetto salvato al bridge')
        return self._schedule(row)

    def status(self, run_id):
        row = self.store.read(run_id)
        task = self.tasks.get(run_id)
        if row['status'] in {'running', 'queued'} and (task is None or task.done()):
            row = self.store.recover(run_id)
            if row['status'] != 'waiting_input':
                row = self.store.transition(run_id, status='waiting_input',
                    message='Esecuzione interrotta: premi RIPRENDI per usare i risultati salvati')
        return row

    def cancel(self, run_id):
        row = self.store.read(run_id)
        if row['status'] in {'ready', 'failed', 'partial', 'cancelled'}:
            return row
        return self.store.transition(run_id, cancel_requested=True,
            status='running' if run_id in self.tasks and not self.tasks[run_id].done() else 'cancelled',
            message='Interruzione richiesta: conservo i risultati già pronti')

    def check(self, run_id):
        row = self.store.read(run_id)
        if row['cancel_requested']:
            raise MagicCancelled()
        self.store.validate_source(run_id, self.source_signature(row['source_project_id']))
        return row

    async def _run(self, run_id):
        try:
            row = self.check(run_id)
            context = MagicContext.model_validate(row)
            options = MagicOptions.model_validate(row['options'])
            chain = fingerprint({'source': context.source_signature, 'options': options.model_dump()})
            warnings, partial, awaiting_bridge = [], False, False
            for index, phase in enumerate(PHASES):
                row = self.check(run_id)
                cached = row['checkpoints'].get(phase)
                if cached and cached['input_signature'] == chain and not (phase == 'delivery' and cached['result'].get('awaiting_bridge')):
                    result = cached['result']
                else:
                    self.store.transition(run_id, phase=phase, completed=0, total=0,
                                          percent=int(index * 100 / len(PHASES)), message=f'MAGICO · {phase}')
                    def report(done, total, message):
                        self.check(run_id)
                        if done < 0 or total < 0 or done > total:
                            raise ValueError('Progresso MAGICO non valido')
                        current = self.store.read(run_id)
                        percent = int((index + (done / total if total else 0)) * 100 / len(PHASES))
                        self.store.transition(run_id, completed=done, total=total,
                                              percent=max(current['percent'], min(99, percent)), message=message)
                    result = await self.services.run_phase(phase, context, options, report)
                    self.check(run_id)
                    self.store.checkpoint(run_id, phase, result, chain)
                warnings.extend(str(value) for value in result.get('warnings', []))
                partial = partial or bool(result.get('partial'))
                awaiting_bridge = awaiting_bridge or bool(result.get('awaiting_bridge'))
                if phase == 'cut':
                    context.output_project_id = result.get('output_project_id', context.output_project_id)
                    context.cut_revision = result.get('cut_revision', context.cut_revision)
                    self.store.transition(run_id, output_project_id=context.output_project_id,
                                          cut_revision=context.cut_revision)
                chain = fingerprint({'parent': chain, 'phase': phase, 'result': result})
            message = 'MAGICO parziale · controlla le segnalazioni' if partial else 'MAGICO pronto · applicazione in Resolve solo dopo APPLICA'
            if awaiting_bridge:
                message += ' · pacchetto salvato, apri il bridge e premi RIPRENDI'
            self.store.transition(run_id, status='partial' if partial else 'ready', phase='completed', percent=100,
                                  warnings=list(dict.fromkeys(warnings)), message=message)
        except MagicCancelled:
            self.store.transition(run_id, status='cancelled', message='MAGICO interrotto · risultati conservati')
        except MagicWaitingInput as exc:
            self.store.transition(run_id, status='waiting_input', message=str(exc), error=str(exc))
        except MagicBudgetReached as exc:
            self.store.transition(run_id, status='partial', message=str(exc), error=str(exc))
        except Exception as exc:
            if self.on_error:
                try:self.on_error(exc,component='magic',phase=locals().get('phase','unknown'))
                except Exception:pass
            self.store.transition(run_id, status='failed', message=str(exc), error=str(exc),
                                  diagnostics={'traceback': traceback.format_exc()})
