"""Opt-in, allowlisted diagnostics to a private GitHub repository; stdlib only.

No raw messages, source text, file contents, project ids, local paths or tokens
are persisted in the report. Delivery never runs on the UI/request thread.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
import traceback
import uuid
from .atomic_io import write_json

REPOSITORY = 'azza0101/rambla-reel-director'
COMPONENTS = {'app','bridge','magic','cut','research','export','startup'}
PHASES = {'unknown','manual','startup','analyze','analysis','cut','editorial','research','selection','preparation','delivery','preview','confirm','residual','boundaries','apply','capture'}
ERROR_TYPES = {'Exception','RuntimeError','ValueError','TypeError','OSError','PermissionError','FileNotFoundError','TimeoutError','ConnectionError','HTTPException','HTTPStatusError','RequestError','GeminiAPIError','GroqAPIError','CalledProcessError','JSONDecodeError','ValidationError','KeyError','IndexError','AssertionError','Manual','AttributeError','ImportError','ModuleNotFoundError','MemoryError','OverflowError','UnicodeDecodeError','ConnectionResetError','BrokenPipeError','ProcessLookupError'}
CATEGORIES = [
    ('PROVIDER_OUTPUT_TRUNCATED', ('max completion tokens reached','output was truncated','output truncated','completion token limit reached')),
    ('PROVIDER_JSON', ('failed to validate json','failed to generate json','json outside expected schema','invalid structured json','generated json does not match')),
    ('TEMPLATE_UNAVAILABLE', ('fusion title', 'template is unavailable', 'kura_paper')),
    ('SUBTITLE_IMPORT', ('no native subtitle', 'imported the srt')),
    ('RATE_LIMIT', ('429', 'rate limit', 'tokens per minute', 'request too large')),
    ('PROVIDER_VERIFICATION', ('captcha', 'verification required')),
    ('MEDIA_DOWNLOAD', ('download', 'media format')),
    ('TIMEOUT', ('timeout', 'timed out', 'did not answer in time')),
    ('CONNECTION', ('connection', 'offline', 'connect to script server')),
]


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def _delivery_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    acquired = False
    try:
        if not path.stat().st_size:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            pass
        yield acquired
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


class Diagnostics:
    def __init__(self, root, *, app_root, github=None, version=None):
        self.root, self.app_root = Path(root), Path(app_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.version = version or (self.app_root/'RAMBLA_VERSION').read_text().strip()
        if not re.fullmatch(r'v[0-9]{4}', self.version):
            self.version = 'unknown'
        self.github = github or self._github
        self.lock = threading.RLock()
        self.wake, self.stopped = threading.Event(), threading.Event()
        self.worker = None
        self.settings()

    def settings(self):
        with self.lock:
            path = self.root/'settings.json'
            row = _read(path, {})
            try:
                installation = str(uuid.UUID(row.get('installation_id', '')))
            except (ValueError, TypeError, AttributeError):
                installation = str(uuid.uuid4())
            result = {'installation_id':installation, 'automatic':row.get('automatic') is True and row.get('choice_made') is True and row.get('policy_version')==1,
                      'choice_made':row.get('choice_made') is True and row.get('policy_version')==1, 'policy_version':1}
            if row != result:
                write_json(path, result)
            return result

    def set_automatic(self, enabled, *, start_worker=True):
        with self.lock:
            row = self.settings()
            row.update(automatic=bool(enabled), choice_made=True)
            write_json(self.root/'settings.json', row)
        if start_worker:
            self.start()
        self.wake.set()
        return self.view()

    def _report(self, exc, component, phase):
        component = component if component in COMPONENTS else 'app'
        phase = phase if phase in PHASES else 'unknown'
        error_type = type(exc).__name__ if exc else 'Manual'
        if error_type not in ERROR_TYPES:
            error_type = 'Exception'
        message = str(exc).lower() if exc else ''
        category = 'UNCLASSIFIED_ERROR' if exc else 'MANUAL_DIAGNOSTIC'
        for code, patterns in CATEGORIES:
            if any(pattern in message for pattern in patterns):
                category = code; break
        frames = []
        if exc and exc.__traceback__:
            for frame in traceback.extract_tb(exc.__traceback__):
                try:
                    relative = Path(frame.filename).resolve().relative_to(self.app_root).as_posix()
                except (OSError, ValueError):
                    continue
                if not (relative.startswith('backend/app/') or relative.startswith('tools/resolve_bridge/') or relative == 'launch_local_v5.py'):
                    continue
                # Source code line text and locals are deliberately never included.
                if re.fullmatch('[a-zA-Z0-9_./-]+', relative) and re.fullmatch('[a-zA-Z0-9_<>]+', frame.name):
                    frames.append({'module':relative, 'function':frame.name[:80], 'line':int(frame.lineno)})
        system = platform.system()
        row = {'schema_version':1, 'version':self.version, 'installation_id':self.settings()['installation_id'],
               'component':component, 'phase':phase, 'category':category, 'error_type':error_type,
               'os':system if system in {'Windows','Linux','Darwin'} else 'other',
               'architecture_bits':struct.calcsize('P')*8,
               'python':f'{sys.version_info.major}.{sys.version_info.minor}', 'frames':frames[-8:]}
        row['fingerprint'] = hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest()[:24]
        row['recorded_at_utc'] = _stamp()
        return row

    def capture_exception(self, exc=None, *, component='app', phase='unknown'):
        try:
            with self.lock:
                report = self._report(exc, component, phase)
                path = self.root/'reports'/(report['fingerprint']+'.json')
                old = _read(path, {})
                entry = {'report':report, 'count':int(old.get('count',0))+1,
                         'first_seen':old.get('first_seen',report['recorded_at_utc']),
                         'last_seen':report['recorded_at_utc'], 'issue_url':old.get('issue_url'),
                         'attempts':int(old.get('attempts',0)), 'next_attempt':old.get('next_attempt',0)}
                write_json(path, entry)
                write_json(self.root/'latest.json', report)
                self.wake.set()
                return report
        except Exception:
            # Diagnostics must never break a render or hide the original error.
            return {}

    def _github_executable(self):
        local = self.app_root/'runtime/bin/gh.exe'
        return str(local) if local.is_file() else shutil.which('gh')

    def _github(self, args, payload=None):
        executable = self._github_executable()
        if not executable:
            raise RuntimeError('github_unavailable')
        command = [executable,'api','--hostname','github.com',*args]
        if payload is not None:
            command += ['--method','POST','--input','-']
        from .github_auth import github_environment
        reply = subprocess.run(command, env=github_environment(self.app_root), input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if reply.returncode:
            # GitHub stderr can contain credentials/paths: never record or return it.
            raise RuntimeError('github_unavailable')
        return json.loads(reply.stdout)

    @staticmethod
    def _body(entry):
        return ('RMBL sanitized diagnostic. No media, transcript, project names, local paths or API keys.\n\n'
                '```json\n'+json.dumps(entry['report'],indent=2,sort_keys=True)+'\n```\n'
                +f"Occurrences on this installation: {entry['count'] if type(entry.get('count')) is int and 0<entry['count']<1000000 else 1}\n")

    def _valid(self, row):
        fields={'schema_version','version','installation_id','component','phase','category','error_type','os','architecture_bits','python','frames','fingerprint','recorded_at_utc'}
        try:
            if set(row)!=fields or row['schema_version']!=1:return False
            if not re.fullmatch(r'v[0-9]{4}|unknown',row['version']):return False
            if str(uuid.UUID(row['installation_id']))!=row['installation_id']:return False
            if row['component'] not in COMPONENTS or row['phase'] not in PHASES:return False
            if row['category'] not in {code for code,_ in CATEGORIES}|{'UNCLASSIFIED_ERROR','MANUAL_DIAGNOSTIC'}:return False
            if row['error_type'] not in ERROR_TYPES:return False
            if row['os'] not in {'Windows','Linux','Darwin','other'} or row['architecture_bits'] not in {32,64}:return False
            if not re.fullmatch(r'[23]\.[0-9]{1,2}',row['python']):return False
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00',row['recorded_at_utc']):return False
            if not isinstance(row['frames'],list) or len(row['frames'])>8:return False
            for frame in row['frames']:
                if set(frame)!={'module','function','line'}:return False
                name=frame['module']
                if not re.fullmatch(r'[a-zA-Z0-9_./-]+',name) or '..' in Path(name).parts:return False
                if not (name.startswith('backend/app/') or name.startswith('tools/resolve_bridge/') or name=='launch_local_v5.py'):return False
                if not re.fullmatch(r'[a-zA-Z0-9_<>]{1,80}',frame['function']):return False
                if type(frame['line']) is not int or not 0<frame['line']<100000:return False
            canonical={key:value for key,value in row.items() if key not in {'fingerprint','recorded_at_utc'}}
            return row['fingerprint']==hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()[:24]
        except (TypeError,ValueError,KeyError):
            return False

    def _send(self, entry):
        report = entry['report']; key = 'rmbl-diag-'+report['fingerprint']
        found = self.github(['search/issues','--method','GET','-f',f'q=repo:{REPOSITORY} is:issue in:title {key}'])
        items = found.get('items') or []
        issue = items[0] if items else self.github([f'repos/{REPOSITORY}/issues'],{
            'title':f"[RMBL {report['version']}] {report['category']} {key}", 'body':self._body(entry)})
        number = issue.get('number')
        url = issue.get('html_url')
        if not isinstance(number,int) or url != f'https://github.com/{REPOSITORY}/issues/{number}':
            raise RuntimeError('invalid_issue_response')
        return url

    def _state(self, **changes):
        row = _read(self.root/'delivery.json', {})
        row.update(changes)
        write_json(self.root/'delivery.json', row)

    def flush(self, *, manual=False):
        if not manual and not self.settings()['automatic']:
            return 0
        with _delivery_lock(self.root/'delivery.lock') as acquired:
            if not acquired:
                return 0
            paths = sorted((self.root/'reports').glob('*.json'))
            pending = [(path,_read(path,{})) for path in paths]
            pending = [(path,row) for path,row in pending if row.get('report') and not row.get('issue_url') and (manual or row.get('next_attempt',0)<=time.time())]
            if not pending:
                return 0
            if manual:
                latest = _read(self.root/'latest.json',{}).get('fingerprint')
                pending = [(path,row) for path,row in pending if row['report']['fingerprint']==latest]
                if not pending:
                    return 0
            if any(not self._valid(entry['report']) for _,entry in pending):
                self._state(delivery_state='invalid_local_report');return 0
            self._state(delivery_state='sending')
            today = datetime.now(timezone.utc).date().isoformat()
            budget = _read(self.root/'budget.json',{})
            count = int(budget.get('count',0)) if budget.get('day')==today else 0
            if count >= 10:
                self._state(delivery_state='daily_limit');return 0
            sent = 0
            try:
                repo = self.github([f'repos/{REPOSITORY}'])
                if repo.get('private') is not True:
                    self._state(delivery_state='private_repo_required');return 0
                for path, entry in pending[:min(3,10-count)]:
                    url = self._send(entry)
                    entry = _read(path,entry)
                    entry.update(issue_url=url, next_attempt=0)
                    write_json(path,entry)
                    sent+=1;count+=1
                    write_json(self.root/'budget.json',{'day':today,'count':count})
                    self._state(delivery_state='sent',last_url=url,last_sent_at=_stamp())
            except Exception:
                for path,entry in pending:
                    if not _read(path,{}).get('issue_url'):
                        entry['attempts']+=1
                        entry['next_attempt']=time.time()+min(3600,60*2**min(6,entry['attempts']-1))
                        write_json(path,entry)
                self._state(delivery_state='github_unavailable',last_attempt_at=_stamp())
            return sent

    def view(self):
        state = _read(self.root/'delivery.json',{})
        rows = [_read(path,{}) for path in (self.root/'reports').glob('*.json')]
        latest=_read(self.root/'latest.json',None)
        if latest and not self._valid(latest):latest=None
        url=state.get('last_url')
        if not isinstance(url,str) or not re.fullmatch(r'https://github\.com/azza0101/rambla-reel-director/issues/[1-9][0-9]*',url):url=None
        return {'settings':self.settings(), 'last_report':latest,
                'pending_count':sum(bool(row.get('report')) and not row.get('issue_url') for row in rows),
                'delivery_state':state.get('delivery_state','idle'), 'last_url':url}

    def submit_async(self):
        latest=_read(self.root/'latest.json',{})
        previous=_read(self.root/'reports'/(str(latest.get('fingerprint',''))+'.json'),{})
        if previous.get('issue_url'):
            self._state(delivery_state='sent',last_url=previous['issue_url']);return self.view()
        if not latest:
            self.capture_exception(component='app',phase='manual')
        self._state(delivery_state='sending')
        def send():
            try:self.flush(manual=True)
            except Exception:self._state(delivery_state='local_storage_error')
        threading.Thread(target=send,name='rmbl-diagnostic-send',daemon=True).start()
        return self.view()

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        self.stopped.clear()
        def loop():
            while not self.stopped.is_set():
                try:self.flush()
                except Exception:pass
                self.wake.wait(30);self.wake.clear()
        self.worker=threading.Thread(target=loop,name='rmbl-diagnostics',daemon=True)
        self.worker.start()

    def close(self):
        self.stopped.set();self.wake.set()

    def login(self):
        from .github_auth import load_token
        if load_token(self.app_root):return {'status':'configured'}
        executable=self._github_executable()
        if not executable:
            raise RuntimeError('GitHub CLI mancante: ripara il setup.')
        subprocess.Popen([executable,'auth','login','--hostname','github.com','--web','--git-protocol','https'],
                         creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
        return {'status':'started'}
