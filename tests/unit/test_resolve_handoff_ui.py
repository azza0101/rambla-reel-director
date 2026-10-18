from pathlib import Path


def test_rambla_primary_control_prepares_package_without_direct_resolve_mutation():
    source=Path('backend/app/timeline_export_ui.py').read_text(encoding='utf-8')
    assert 'INVIA A RESOLVE</button>' in source
    assert 'Componenti da esportare' in source
    assert 'resolveComponentsV71' in source
    assert '/resolve-handoffs' in source
    assert 'PACCHETTO PRONTO · ATTESA RICEZIONE' in source
    assert "resolveDeliveryProgressV33').removeAttribute('value')" not in source
    assert 'poster="${esc(row.preview_url)}"' in source
    assert 'src="${esc(row.selected_rendition_url)}"' in source
    assert '<progress id="resolveDeliveryProgressV33"' not in source
    assert 'setResolveDeliveryProgressV33(job.percent)' in source
    assert 'ESPORTA XML' in source and 'ESPORTA DRA' in source
    assert 'genericCoverageMicroV34' in source
    assert source.index('genericCoverageMicroV34') < source.index('id="timelineExportV33"')
    assert 'PACCHETTO PRONTO · ATTESA RICEZIONE' in source


def test_bridge_requires_confirmation_and_offers_both_destinations():
    source=Path('tools/resolve_bridge/standalone_bridge.py').read_text(encoding='utf-8')
    assert 'PACCHETTO DA RMBL B ROLL' in source
    assert 'CREA UNA NUOVA TIMELINE TEMP' in source
    assert 'APPLICA ALLA TIMELINE ATTIVA' in source
    assert 'APPLICA' in source and 'SCARTA' in source
    assert '/resolve-handoffs/pending' in source
    assert 'ProgressBar' in source
    assert 'def _render_job' in source
    assert 'NUOVA REVISIONE' in source
    assert 'self.client.apply(self.destination.get(), scope)' in source
    assert 'ESPORTATO SU RESOLVE · RICEVUTO DAL BRIDGE' in Path('backend/app/timeline_export_ui.py').read_text(encoding='utf-8')
    assert 'RMBL B ROLL CONNECTED' in source
    assert 'RMBL B ROLL OFFLINE' in source
    assert 'RESOLVE OFFLINE' in source
    assert 'SingleInstance' in source
    assert '"#d8ff5b"' in source
