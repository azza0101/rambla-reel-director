from pathlib import Path
import shutil
import uuid
import zipfile

from backend.app.workspace_backup import backup_project_state


def test_backup_keeps_editorial_state_but_skips_media():
    root = Path(".test-workspace-backup") / uuid.uuid4().hex
    try:
        project = root / "projects" / "p1"
        (project / "run").mkdir(parents=True)
        (project / "resolve-media").mkdir()
        (project / "project.rambla.json").write_text('{"name":"Egitto"}', encoding="utf-8")
        (project / "run" / "selection-plan.json").write_text('{"selected":true}', encoding="utf-8")
        (project / "resolve-media" / "clip.mp4").write_bytes(b"video")
        archive = backup_project_state(project, root / "backups")
        with zipfile.ZipFile(archive) as saved:
            assert set(saved.namelist()) == {"project.rambla.json", "run/selection-plan.json"}
    finally:
        shutil.rmtree(root, ignore_errors=True)
