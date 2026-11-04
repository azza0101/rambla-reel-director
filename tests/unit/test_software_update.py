import hashlib
import json
from pathlib import Path
import uuid
import zipfile
import pytest
from tools.verify_update_archive import verify
from backend.app.software_update import installed_root
from backend.app.curation_ui_v2 import render_curation_page_v2

@pytest.fixture
def work():
    p=Path('.test-tmp')/('updater-'+uuid.uuid4().hex)
    p.mkdir(parents=True)
    return p

def archive(work,extra=None):
    z=work/'RMBL-B-ROLL-Windows-v0119.zip'
    with zipfile.ZipFile(z,'w') as f:
        for name,value in {'RAMBLA_VERSION':'v0119','INSTALL_RMBL_B_ROLL.ps1':'test','launch_local_v5.py':'test','SEARCH_UPDATE.ps1':'test',**(extra or {})}.items():f.writestr(name,value)
    m=work/'update.json'
    m.write_text(json.dumps({'version':'v0119','archive':z.name,'sha256':hashlib.sha256(z.read_bytes()).hexdigest()}))
    return z,m

def test_valid_archive(work):
    assert verify(*archive(work))['version']=='v0119'

@pytest.mark.parametrize('bad',['../escape','/absolute','C:/drive','folder/../escape'])
def test_unsafe_paths(work,bad):
    with pytest.raises(ValueError,match='Unsafe'):
        verify(*archive(work,{bad:'bad'}))

def test_damaged_download(work):
    z,m=archive(work);z.write_bytes(z.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='SHA256'):verify(z,m)

def test_development_checkout_never_updated(work):
    app=work/'app';app.mkdir()
    (work/'install.json').write_text(json.dumps({'app_root':str(app.resolve())}))
    assert installed_root(app)
    (app/'.git').mkdir()
    assert not installed_root(app)

def test_update_button_has_handler():
    html=render_curation_page_v2()
    assert 'id="searchSoftwareUpdate"' in html
    assert '/api/curation/software-update' in html
    assert "'X-RMBL-Update':'1'" in html


def test_update_api_rejects_cross_origin_and_busy(work):
    from fastapi.testclient import TestClient
    from backend.app.curation_server import create_app
    app=create_app(project_root=work/'projects')
    with TestClient(app) as client:
        assert client.get('/api/curation/software-update/status').json()=={'busy':False}
        assert client.post('/api/curation/software-update').status_code==403
        assert client.post('/api/curation/software-update',headers={'X-RMBL-Update':'1','origin':'https://untrusted.example'}).status_code==403
        app.state.cut_jobs['active']={'status':'running'}
        assert client.post('/api/curation/software-update',headers={'X-RMBL-Update':'1'}).status_code==409


def test_updater_uses_foreground_owned_confirmation_not_hidden_messagebox():
    script = Path("SEARCH_UPDATE.ps1").read_text(encoding="utf-8-sig")
    assert "function Confirm-RMBLSoftwareUpdate" in script
    assert "$form.TopMost = $true" in script
    assert "$form.ShowInTaskbar = $true" in script
    assert "$form.ShowDialog()" in script
    assert "PACCHETTO VERIFICATO" in script
    assert "ALT+TAB" in script
    assert "[Windows.MessageBox]::Show" not in script
    assert "verify_update_archive.py" in script
    assert "INSTALL_RMBL_B_ROLL.ps1" in script
    assert "-ForceUpdate" in script


def test_updater_skips_duplicate_download_after_reading_manifest():
    script = Path("SEARCH_UPDATE.ps1").read_text(encoding="utf-8-sig")
    no_op = script.index("if (-not $CheckOnly -and $manifest.version -le $current)")
    archive_download = script.index("release download $manifest.version")
    assert no_op < archive_download
