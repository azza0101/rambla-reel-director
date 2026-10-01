import socket
import time

from tools.resolve_bridge.standalone_bridge import (
    BridgeApp,
    BridgeClient,
    BridgeSnapshot,
    SingleInstance,
    window_geometry,
)


def test_active_timeline_is_the_default_destination(monkeypatch):
    from tools.resolve_bridge.standalone_bridge import default_destination
    monkeypatch.delenv("RAMBLA_BRIDGE_DESTINATION", raising=False)
    monkeypatch.delenv("RAMBLA_BRIDGE_DESTINATION_EXPLICIT", raising=False)
    assert default_destination() == "active"


def test_destination_survives_bridge_auto_update(monkeypatch):
    from tools.resolve_bridge.standalone_bridge import default_destination
    monkeypatch.setenv("RAMBLA_BRIDGE_DESTINATION", "new")
    monkeypatch.setenv("RAMBLA_BRIDGE_DESTINATION_EXPLICIT", "1")
    assert default_destination() == "new"


def test_old_implicit_new_default_is_migrated_to_active(monkeypatch):
    from tools.resolve_bridge.standalone_bridge import default_destination
    monkeypatch.setenv("RAMBLA_BRIDGE_DESTINATION", "new")
    monkeypatch.delenv("RAMBLA_BRIDGE_DESTINATION_EXPLICIT", raising=False)
    assert default_destination() == "active"


def test_bridge_uses_modern_cards_for_capture_and_destination_controls():
    from pathlib import Path
    source = Path("tools/resolve_bridge/standalone_bridge.py").read_text(encoding="utf-8")
    assert "CompactChoiceRow" in source
    assert "DestinationCard" in source
    assert "Non sposta né modifica le clip già presenti" in source
    assert "Analizza le tracce video superiori" in source
    assert "ToggleCard" not in source


def test_window_expands_for_a_received_package_and_stays_on_screen():
    assert window_geometry(1920, 1080, requested_height=640, package_visible=False) == "600x680"
    assert window_geometry(1920, 1080, requested_height=780, package_visible=True) == "660x840"
    assert window_geometry(1280, 720, requested_height=900, package_visible=True) == "600x640"


def test_bridge_branding_assets_and_visual_language_are_present():
    from pathlib import Path

    source = Path("tools/resolve_bridge/standalone_bridge.py").read_text(encoding="utf-8")
    assert "rmbl_wordmark_white.png" in source
    assert "draw_bridge_mark" in source
    assert "build_bridge_icon" in source
    assert "self.root.iconphoto(True, bridge_icon)" in source
    assert "RoundedButton" in source
    assert "RoundedPanel" in source
    assert "Scrollable bridge surface" in source
    assert "#7c6cf2" in source
    assert Path("backend/assets/branding/rmbl_mark_white.png").is_file()
    assert Path("backend/assets/branding/rmbl_bridge_mark.svg").is_file()


def test_bridge_svg_layers_the_bridge_over_the_original_rmbl_mark():
    from pathlib import Path

    source = Path("backend/assets/branding/rmbl_bridge_mark.svg").read_text(encoding="utf-8")
    assert 'href="rmbl_mark_white.png"' in source
    assert 'id="bridge-overlay"' in source


def test_hidden_test_desktop_cannot_block_the_users_bridge():
    from tools.resolve_bridge.standalone_bridge import instance_port_for_desktop
    assert instance_port_for_desktop('Default') == 38742
    assert instance_port_for_desktop('CodexSandboxDesktop-test') != 38742
    assert instance_port_for_desktop('CodexSandboxDesktop-test') == instance_port_for_desktop('CodexSandboxDesktop-test')


def test_running_bridge_reloads_after_a_source_update(monkeypatch):
    import tools.resolve_bridge.standalone_bridge as module
    app=BridgeApp(FakeRoot(),FakeClient(),build_ui=False)
    restarted=[]
    monkeypatch.setattr(module,'bridge_build_token',lambda: 'updated-source')
    monkeypatch.setattr(app,'_restart_for_update',lambda: restarted.append(True))
    assert app._maybe_update()
    assert restarted == [True]


def test_update_is_deferred_while_resolve_is_applying(monkeypatch):
    import tools.resolve_bridge.standalone_bridge as module
    app=BridgeApp(FakeRoot(),FakeClient(),build_ui=False)
    monkeypatch.setattr(module,'bridge_build_token',lambda: 'updated-source')
    restarted=[]
    monkeypatch.setattr(app,'_restart_for_update',lambda: restarted.append(True))
    app.applying=True
    assert not app._maybe_update()
    app.applying=False
    app.client.current_package={'status':'applying'}
    assert not app._maybe_update()
    app.client.current_package={'status':'completed'}
    assert app._maybe_update() and restarted == [True]


def test_poll_heartbeats_and_receives_newest_matching_package():
    calls=[]
    def request(path, method="GET", payload=None):
        calls.append((path,method,payload))
        if path == "/api/curation/resolve-bridge/session" and method == "POST": return {"bridge_session_id":"session-1","connected":True}
        if path == "/api/curation/resolve-bridge/status": return {"connected":True,"project":"P","timeline":"T","timeline_id":"tl-1","mark_in":0,"mark_out":100,"range_source":"timeline"}
        if path.startswith("/api/curation/resolve-handoffs/pending?"): return {"packages":[
            {"package_id":"new","created_at":"2026-09-30T12:00:00","status":"pending","summary":{}},
            {"package_id":"old","created_at":"2026-09-30T11:00:00","status":"pending","summary":{}},
        ]}
        if path == "/api/curation/resolve-handoffs/new/received": return {"package_id":"new","status":"pending","bridge_received_at":"now","summary":{}}
        raise AssertionError(path)
    client=BridgeClient(request_json=request, session_id="session-1")
    snapshot=client.poll_once()
    assert snapshot.connected and snapshot.package["package_id"] == "new"
    assert any(path.endswith("/new/received") for path,_,_ in calls)
    pending_path=next(path for path,_,_ in calls if "/pending?" in path)
    assert "timeline_id=" not in pending_path


def test_apply_requires_received_package_and_uses_current_timeline():
    calls=[]
    responses={
        "/api/curation/resolve-bridge/status":{"connected":True,"project":"P","timeline":"T","timeline_id":"tl-2"},
        "/api/curation/resolve-handoffs/pkg/apply":{"status":"applying"},
    }
    def request(path,method="GET",payload=None): calls.append((path,method,payload)); return responses[path]
    client=BridgeClient(request_json=request,session_id="s")
    client.current_package={"package_id":"pkg","bridge_received_at":"now"}
    row=client.apply("active")
    assert row["status"] == "applying"
    assert calls[-1][2] == {"destination_mode":"active","current_project":"P","current_timeline_id":"tl-2"}


def test_apply_is_gated_until_bridge_received_at_exists():
    client=BridgeClient(request_json=lambda *args,**kwargs: {},session_id="s")
    client.current_package={"package_id":"pkg"}
    try: client.apply("new")
    except RuntimeError as exc: assert "received" in str(exc).lower()
    else: raise AssertionError("apply should be gated")


def test_force_audio_recalculation_is_sent_to_the_server():
    calls=[]
    def request(path,method="GET",payload=None):
        calls.append((path,method,payload)); return {"status":"captured"}
    client=BridgeClient(request_json=request,session_id="s")
    client.capture(detect_videos=True,include_v1=False,force_recalculate=True)
    assert calls == [("/api/curation/resolve-bridge/capture","POST",{
        "detect_videos":True,"include_v1":False,"force_recalculate":True,
    })]


def test_bridge_exposes_a_force_recalculate_in_out_button():
    from pathlib import Path
    source=Path("tools/resolve_bridge/standalone_bridge.py").read_text(encoding="utf-8")
    assert "RICALCOLA AUDIO · IN → OUT" in source
    assert "force_recalculate=True" in source


class FakeRoot:
    def __init__(self):
        self.scheduled=[]
        self.destroyed=False
    def after(self, delay, callback): self.scheduled.append((delay, callback)); return "timer-1"
    def after_cancel(self, token): self.scheduled.append(("cancel", token))
    def destroy(self): self.destroyed=True
    def deiconify(self): pass
    def lift(self): pass
    def focus_force(self): pass


class FakeClient:
    def __init__(self):
        self.polls=0
        self.current_package=None
    def poll_once(self):
        self.polls+=1
        self.current_package={"package_id":"pkg","bridge_received_at":"now","summary":{}}
        return BridgeSnapshot(True,{"project":"P","timeline":"T"},self.current_package)


def test_app_polls_immediately_then_schedules_every_second():
    root=FakeRoot(); client=FakeClient()
    app=BridgeApp(root,client,build_ui=False)
    app.start()
    assert client.polls == 1
    assert root.scheduled[0][0] == 1000


def test_new_package_forces_the_expanded_geometry_after_render():
    class Widget:
        def configure(self, **_kwargs): pass
    class IdleRoot(FakeRoot):
        def after_idle(self, callback): callback()
    root=IdleRoot(); app=BridgeApp(root,FakeClient(),build_ui=False)
    app.widgets={name:Widget() for name in ('connection','timeline','package','apply','discard','message','progress')}
    fitted=[]; app._fit_window=lambda *,package_visible: fitted.append(package_visible)
    package={'package_id':'new','bridge_received_at':'now','summary':{},'change_summary':{}}
    app._render(BridgeSnapshot(True,{'project':'P','timeline':'T'},package))
    assert fitted == [True]


def test_app_close_cancels_poll_and_releases_instance():
    root=FakeRoot(); client=FakeClient()
    class Lock:
        closed=False
        def close(self): self.closed=True
    lock=Lock(); app=BridgeApp(root,client,single_instance=lock,build_ui=False)
    app.start(); app.close()
    assert ("cancel","timer-1") in root.scheduled
    assert lock.closed and root.destroyed


def test_second_single_instance_sends_focus_signal():
    probe=socket.socket(); probe.bind(("127.0.0.1",0)); port=probe.getsockname()[1]; probe.close()
    focused=[]
    first=SingleInstance(port=port,on_focus=lambda: focused.append(True))
    assert first.acquire()
    second=SingleInstance(port=port)
    assert not second.acquire()
    for _ in range(50):
        if focused: break
        time.sleep(.01)
    first.close()
    assert focused == [True]
