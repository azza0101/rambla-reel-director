import shutil, time, uuid, threading
from pathlib import Path

from backend.app.resolve_handoff import ResolveHandoffStore
from backend.app.resolve_handoff_jobs import ResolveHandoffJobs


def test_failure_preserves_last_checkpoint_and_traceback():
    import json
    root=Path('.test-resolve-jobs')/uuid.uuid4().hex;root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,{'project_id':'p','source_project_name':'P'})
        def runner(payload):
            Path(payload['handoff_progress_path']).write_text(json.dumps({'phase':'broll','percent':84,'message':'Clip 5/13'}),encoding='utf-8')
            time.sleep(.08)
            raise RuntimeError('Import failed')
        jobs=ResolveHandoffJobs(store,runner)
        jobs.apply(root,package['package_id'],'new',current_project='P',current_timeline_id='T')
        for _ in range(100):
            row=store.read(root,package['package_id'])
            if row['status']=='failed':break
            time.sleep(.01)
        assert row['status']=='failed' and row['progress']['percent']==84
        assert row['diagnostics']['last_progress']['phase']=='broll'
        assert 'RuntimeError: Import failed' in row['diagnostics']['traceback']
        assert (root/'resolve-outbox'/package['package_id']/'progress.json').is_file()
    finally:shutil.rmtree(root,ignore_errors=True)


def test_completed_package_can_be_applied_again_without_repreparing_handoff():
    root = Path('.test-resolve-jobs') / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        store = ResolveHandoffStore(root.parent)
        package = store.prepare(root, {"project_id":"p", "source_project_name":"P", "source_timeline_id":"T", "subtitles":[]})
        calls=[]
        jobs=ResolveHandoffJobs(store, lambda payload: calls.append(payload) or {"timeline_name":"OUT", "broll_count":0})
        started=jobs.apply(root, package["package_id"], "new", current_project="P", current_timeline_id="T")
        assert started["status"] == "applying"
        for _ in range(100):
            result=store.read(root, package["package_id"])
            if result["status"] != "applying": break
            time.sleep(.01)
        assert result["status"] == "completed" and result["application_count"] == 1

        restarted=jobs.apply(root, package["package_id"], "active", "media", current_project="P", current_timeline_id="T")
        assert restarted["status"] == "applying"
        for _ in range(100):
            result=store.read(root, package["package_id"])
            if result["status"] != "applying": break
            time.sleep(.01)

        assert result["status"] == "completed" and result["application_count"] == 2
        assert [row["apply_scope"] for row in calls] == ["all", "media"]
    finally: shutil.rmtree(root, ignore_errors=True)


def test_handoff_payload_title_can_be_refreshed_before_apply():
    root = Path('.test-resolve-jobs') / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        store = ResolveHandoffStore(root.parent)
        package = store.prepare(root, {
            "project_id": "p", "source_project_name": "P", "source_timeline_id": "T",
            "title_name": "Old_Title",
        })
        store.update_payload(root, package["package_id"], title_name="KURA_paper_title_v9")
        calls = []
        jobs = ResolveHandoffJobs(store, lambda payload: calls.append(payload) or {})
        jobs.apply(root, package["package_id"], "active", "titles",
                   current_project="P", current_timeline_id="T")
        for _ in range(100):
            row = store.read(root, package["package_id"])
            if row["status"] != "applying":
                break
            time.sleep(.01)
        assert row["status"] == "completed"
        assert calls[0]["title_name"] == "KURA_paper_title_v9"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_running_apply_can_be_cancelled_cooperatively_and_package_remains_reusable():
    root = Path('.test-resolve-jobs') / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,{"project_id":"p","source_project_name":"P","source_timeline_id":"T"})
        started=threading.Event()
        def runner(payload):
            started.set()
            cancel=Path(payload["handoff_cancel_path"])
            for _ in range(200):
                if cancel.is_file():
                    raise RuntimeError("cancelled by user")
                time.sleep(.005)
            return {}
        jobs=ResolveHandoffJobs(store,runner)
        jobs.apply(root,package["package_id"],"active",current_project="P",current_timeline_id="T")
        assert started.wait(1)
        cancelling=jobs.cancel(root,package["package_id"])
        assert cancelling["status"]=="applying"
        assert cancelling["cancel_requested"] is True
        for _ in range(200):
            row=store.read(root,package["package_id"])
            if row["status"]!="applying": break
            time.sleep(.005)
        assert row["status"]=="cancelled"
        assert "ripristinata" in row["progress"]["message"]
        assert jobs.apply(root,package["package_id"],"active","titles",current_project="P",current_timeline_id="T")["status"]=="applying"
    finally:
        shutil.rmtree(root,ignore_errors=True)


def test_active_destination_uses_the_timeline_focused_at_apply_time():
    root = Path('.test-resolve-jobs') / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,{"project_id":"p","source_project_name":"P","source_timeline_id":"T"})
        calls=[]
        jobs=ResolveHandoffJobs(store, lambda payload: calls.append(payload) or {})
        assert jobs.apply(root,package["package_id"],"active",current_project="P",current_timeline_id="focused",current_mark_in=4321)["status"] == "applying"
        for _ in range(100):
            result=store.read(root,package["package_id"])
            if result["status"] != "applying": break
            time.sleep(.01)
        assert result["status"] == "completed"
        assert calls[0]["source_timeline_id"] == "focused"
        assert calls[0]["bridge_mark_in"] == 4321
    finally: shutil.rmtree(root, ignore_errors=True)


def test_selective_apply_scope_reaches_resolve_runner_and_requires_active_destination():
    root=Path('.test-resolve-jobs')/uuid.uuid4().hex; root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,{"project_id":"p","source_project_name":"P","source_timeline_id":"T"})
        calls=[]
        jobs=ResolveHandoffJobs(store,lambda payload:calls.append(payload) or {})
        try:
            jobs.apply(root,package["package_id"],"new","titles",current_project="P",current_timeline_id="T")
        except ValueError as exc:
            assert "active timeline" in str(exc)
        else:
            raise AssertionError("selective apply must reject new destination")
        jobs.apply(root,package["package_id"],"active","titles",current_project="P",current_timeline_id="T")
        for _ in range(100):
            row=store.read(root,package["package_id"])
            if row["status"] != "applying": break
            time.sleep(.01)
        assert row["status"] == "completed"
        assert calls[0]["apply_scope"] == "titles"
        assert row["apply_scope"] == "titles"
    finally: shutil.rmtree(root,ignore_errors=True)


def test_new_destination_can_be_applied_while_a_generated_timeline_is_open():
    root=Path('.test-resolve-jobs')/uuid.uuid4().hex; root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent); package=store.prepare(root,{"project_id":"p","source_project_name":"P","source_timeline_id":"source"})
        jobs=ResolveHandoffJobs(store,lambda payload:{"timeline_name":"v2"})
        assert jobs.apply(root,package["package_id"],"new",current_project="P",current_timeline_id="generated")["status"]=="applying"
    finally: shutil.rmtree(root,ignore_errors=True)


def test_apply_surfaces_real_helper_progress_file():
    root = Path('.test-resolve-jobs') / uuid.uuid4().hex
    root.mkdir(parents=True)
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,{"project_id":"p","source_project_name":"P","source_timeline_id":"T"})
        def runner(payload):
            import json
            Path(payload["handoff_progress_path"]).write_text(json.dumps({"phase":"subtitles","percent":78,"message":"Inserisco sottotitoli"}),encoding="utf-8")
            time.sleep(.08)
            return {"timeline_name":"OUT"}
        jobs=ResolveHandoffJobs(store,runner)
        jobs.apply(root,package["package_id"],"new",current_project="P",current_timeline_id="T")
        seen=[]
        for _ in range(100):
            row=store.read(root,package["package_id"]); seen.append(row.get("progress",{}).get("percent"))
            if row["status"] != "applying": break
            time.sleep(.01)
        assert 78 in seen and row["status"] == "completed"
    finally: shutil.rmtree(root, ignore_errors=True)


def test_package_read_retries_transient_windows_lock(monkeypatch):
    from backend.app.resolve_handoff import _read_json
    attempts=[]
    original_read = Path.read_text
    def read(path, **kwargs):
        if path != Path('package.json'):
            return original_read(path, **kwargs)
        attempts.append(path)
        if len(attempts)==1:
            raise PermissionError("sharing violation")
        return '{"status":"completed"}'
    monkeypatch.setattr(Path, 'read_text', read)
    assert _read_json(Path('package.json'))['status']=='completed'
    assert len(attempts)==2
