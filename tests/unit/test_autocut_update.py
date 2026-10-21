import hashlib,json,zipfile
from pathlib import Path
import pytest
from tests.unit.test_cut_pass_routes import tmp_path


def test_verified_update_preserves_credentials_projects_and_native_sdk(tmp_path):
    from backend.app.autocut_update import apply_archive
    root=tmp_path/'app';root.mkdir();plugin=tmp_path/'plugin';plugin.mkdir();data=tmp_path/'data';data.mkdir()
    (root/'.env.local').write_text('PRIVATE');(data/'project.json').write_text('CHOICES');(plugin/'WorkflowIntegration.node').write_bytes(b'NATIVE')
    (root/'pyproject.toml').write_text('[project]\ndependencies=[]\n')
    archive=tmp_path/'update.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('backend/app/autocut_ui.py','UPDATED')
        z.writestr('tools/autocut_integration/main.js','NEW MAIN')
        z.writestr('pyproject.toml',(root/'pyproject.toml').read_text())
    apply_archive(root,plugin,data,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
    assert (root/'.env.local').read_text()=='PRIVATE'
    assert (data/'project.json').read_text()=='CHOICES'
    assert (plugin/'WorkflowIntegration.node').read_bytes()==b'NATIVE'
    assert (plugin/'main.js').read_text()=='NEW MAIN'


@pytest.mark.parametrize('name',['../escape.py','backend/../../escape.py','.env.local','tools/autocut_integration/WorkflowIntegration.node'])
def test_update_refuses_files_outside_managed_code(tmp_path,name):
    from backend.app.autocut_update import apply_archive
    root=tmp_path/'app';root.mkdir();plugin=tmp_path/'plugin';plugin.mkdir();data=tmp_path/'data'
    archive=tmp_path/'update.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,'BAD')
    with pytest.raises(ValueError):apply_archive(root,plugin,data,archive,hashlib.sha256(archive.read_bytes()).hexdigest())
    assert not (tmp_path/'escape.py').exists()


def test_wrong_hash_does_not_modify_code(tmp_path):
    from backend.app.autocut_update import apply_archive
    archive=tmp_path/'update.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('RAMBLA_VERSION','v9999')
    root=tmp_path/'app';root.mkdir();(root/'RAMBLA_VERSION').write_text('v0122')
    with pytest.raises(ValueError):apply_archive(root,tmp_path/'plugin',tmp_path/'data',archive,'0'*64)
    assert (root/'RAMBLA_VERSION').read_text()=='v0122'
