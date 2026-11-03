from pathlib import Path
from backend.app.software_update import launch_update
import json


def test_updater_console_remains_open_on_error(tmp_path, monkeypatch):
    root=tmp_path/"app"
    root.mkdir()
    (root/"SEARCH_UPDATE.ps1").write_text("exit 0",encoding="utf-8")
    (tmp_path/"install.json").write_text(json.dumps({"app_root":str(root)}),encoding="utf-8")
    captured={}
    from backend.app import software_update
    monkeypatch.setattr("backend.app.github_auth.github_environment",lambda *_: {})
    monkeypatch.setattr(software_update.subprocess,"Popen",lambda args,**kw:captured.update({"args":args,"kwargs":kw}))
    response=launch_update(root)
    assert response["status"]=="started"
    assert "-NoExit" in captured["args"]
    assert "-File" in captured["args"]
    assert captured["kwargs"]["cwd"]==str(root)
