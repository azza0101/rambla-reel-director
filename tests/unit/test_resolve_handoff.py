import shutil
import uuid
from pathlib import Path

import pytest

from backend.app.resolve_handoff import ResolveHandoffStore


def _root():
    path = Path(".test-resolve-handoff") / uuid.uuid4().hex
    path.mkdir(parents=True)
    return path


def _payload(**updates):
    payload = {
        "project_id": "p1", "project_name": "Egitto", "source_project_name": "Egitto2",
        "source_timeline_id": "tl-1", "source_timeline_name": "EGITTO", "duration_seconds": 42.5,
        "titles": [{"text": "ciao"}], "subtitles": [{"text": "ciao"}, {"text": "mondo"}],
        "broll_clips": [{"media_path": __file__, "provider": "pexels"}],
        "generic_broll_clips": [{"media_path": "missing.mp4", "provider": "pexels"}],
        "broll_unavailable": [{"asset_id": "x", "reason": "download missing"}],
    }
    payload.update(updates)
    return payload


def test_prepare_is_versioned_and_summarizes_unavailable_media():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        one = store.prepare(root, _payload())
        two = store.prepare(root, _payload())
        assert one["package_id"] != two["package_id"]
        assert one["status"] == "pending"
        assert one["summary"] == {
            "duration_seconds": 42.5, "title_count": 1, "subtitle_count": 2,
            "broll_count": 1, "generic_broll_count": 0, "unavailable_count": 2,
        }
        assert store.read(root, one["package_id"])["schema"] == "rambla-resolve-handoff-1"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prepare_exposes_media_issues_without_putting_payload_in_api_metadata():
    root = _root()
    try:
        issue = {"beat_id": "beat_003", "source_page": "https://www.youtube.com/shorts/example"}
        package = ResolveHandoffStore(root.parent).prepare(root, _payload(media_issues=[issue]))
        assert package["media_issues"] == [issue]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_pending_filters_and_transitions_are_guarded():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        package = store.prepare(root, _payload())
        assert [p["package_id"] for p in store.pending(resolve_project="Egitto2", timeline_id="tl-1")] == [package["package_id"]]
        assert not store.pending(resolve_project="Other", timeline_id="tl-1")
        assert not store.pending(resolve_project="Egitto2", timeline_id="generated-timeline")
        applying = store.transition(root, package["package_id"], "applying", progress={"percent": 5})
        failed = store.transition(root, package["package_id"], "failed", error="boom")
        discarded = store.transition(root, package["package_id"], "discarded")
        assert applying["status"] == "applying" and failed["status"] == "failed" and discarded["status"] == "discarded"
        with pytest.raises(ValueError):
            store.transition(root, package["package_id"], "applying")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_new_bridge_session_does_not_offer_old_pending_package():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        old = store.prepare(root, _payload(bridge_session_id="old-session"))
        current = store.prepare(root, _payload(bridge_session_id="current-session"))

        rows = store.pending(resolve_project="Egitto2", timeline_id="tl-1", bridge_session_id="current-session")

        assert [row["package_id"] for row in rows] == [current["package_id"]]
        assert old["package_id"] not in {row["package_id"] for row in rows}
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_unassigned_package_can_be_claimed_and_acknowledged_by_current_bridge():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        package = store.prepare(root, _payload(bridge_session_id=""))
        rows = store.pending(resolve_project="Egitto2", timeline_id="tl-1", bridge_session_id="live")
        assert [row["package_id"] for row in rows] == [package["package_id"]]
        received = store.mark_received(root, package["package_id"], bridge_session_id="live")
        assert received["bridge_session_id"] == "live"
        assert received["bridge_received_at"]
        assert received["progress"]["percent"] == 100
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_new_package_describes_revision_against_last_completed_package():
    root=_root()
    try:
        store=ResolveHandoffStore(root.parent)
        first=store.prepare(root,_payload(broll_clips=[{"asset_id":"a","media_path":__file__}]))
        store.transition(root,first["package_id"],"applying")
        store.transition(root,first["package_id"],"completed")
        second=store.prepare(root,_payload(broll_clips=[{"asset_id":"b","media_path":__file__}]))
        assert second["revision"] == 2 and second["supersedes"] == first["package_id"]
        assert second["change_summary"]["broll_added"] == 1
        assert second["change_summary"]["broll_removed"] == 1
    finally: shutil.rmtree(root,ignore_errors=True)


def test_completed_handoff_remains_discoverable_for_same_bridge_session_and_can_reenter_apply():
    root=_root()
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,_payload(bridge_session_id="session-1"))
        store.mark_received(root,package["package_id"],bridge_session_id="session-1")
        store.transition(root,package["package_id"],"applying")
        store.transition(root,package["package_id"],"completed")
        rows=store.pending(resolve_project="Egitto2",timeline_id="tl-1",bridge_session_id="session-1")
        assert [row["package_id"] for row in rows] == [package["package_id"]]
        row=store.transition(root,package["package_id"],"applying",apply_scope="subtitles")
        assert row["status"] == "applying" and row["apply_scope"] == "subtitles"
    finally:
        shutil.rmtree(root,ignore_errors=True)


def test_cancelled_handoff_stays_discoverable_and_can_be_reapplied():
    root=_root()
    try:
        store=ResolveHandoffStore(root.parent)
        package=store.prepare(root,_payload(bridge_session_id="session-cancel"))
        store.mark_received(root,package["package_id"],bridge_session_id="session-cancel")
        store.transition(root,package["package_id"],"applying")
        cancelled=store.transition(root,package["package_id"],"cancelled")
        assert cancelled["status"]=="cancelled"
        rows=store.pending(resolve_project="Egitto2",timeline_id="tl-1",bridge_session_id="session-cancel")
        assert [row["package_id"] for row in rows] == [package["package_id"]]
        reapplied=store.transition(root,package["package_id"],"applying",apply_scope="media")
        assert reapplied["status"]=="applying"
    finally:
        shutil.rmtree(root,ignore_errors=True)


def test_standard_delivery_retargets_stale_capture_safely():
    from backend.app.resolve_handoff import bind_standard_target
    original = _payload(source_project_name="Old project", source_timeline_id="old-tl", bridge_mark_in=3)
    target = {"connected": True, "project": "Active project", "timeline_id": "active-tl",
              "timeline": "Edit 1", "mark_in": 42}
    result = bind_standard_target(original, target)
    assert result["source_project_name"] == "Active project"
    assert result["source_timeline_id"] == "active-tl"
    assert result["source_timeline_name"] == "Edit 1"
    assert result["bridge_mark_in"] == 42
    assert original["source_project_name"] == "Old project"


@pytest.mark.parametrize("cut_flag", ["native_cut", "native_cut_reference"])
def test_native_cut_delivery_never_retargets(cut_flag):
    from backend.app.resolve_handoff import bind_standard_target
    original = _payload(**{cut_flag: {"segments": []}})
    target = {"connected": True, "project": "Wrong project", "timeline_id": "wrong-tl",
              "timeline": "Wrong edit", "mark_in": 100}
    assert bind_standard_target(original, target) == original


def test_offline_bridge_does_not_retarget_original_capture():
    from backend.app.resolve_handoff import bind_standard_target
    original = _payload()
    assert bind_standard_target(original, {"connected": False}) == original


def test_unbound_package_visible_only_to_its_live_bridge_session():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        package = store.prepare(root, _payload(
            source_project_name="", source_timeline_id="", bridge_session_id="live-bridge"))
        rows = store.pending(resolve_project="Current Resolve", timeline_id="",
                             bridge_session_id="live-bridge")
        assert [row["package_id"] for row in rows] == [package["package_id"]]
        assert store.pending(resolve_project="Current Resolve", timeline_id="",
                             bridge_session_id="other-bridge") == []
        received = store.mark_received(root, package["package_id"], bridge_session_id="live-bridge")
        assert received["bridge_received_at"]
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_bound_project_remains_invisible_to_other_project_same_session():
    root = _root()
    try:
        store = ResolveHandoffStore(root.parent)
        store.prepare(root, _payload(bridge_session_id="live-bridge"))
        assert store.pending(resolve_project="Wrong project", timeline_id="",
                             bridge_session_id="live-bridge") == []
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_reconnect_reassigns_pending_package_without_copying_or_rebuilding(tmp_path):
    store = ResolveHandoffStore(tmp_path)
    root = tmp_path / 'p1'; root.mkdir()
    package = store.prepare(root, _payload(bridge_session_id='old'))
    row = store.reconnect(root, package['package_id'], bridge_session_id='new',
                          resolve_project='Egitto2', timeline_id='tl-1')
    assert row['package_id'] == package['package_id']
    assert row['payload'] == package['payload']
    assert row['bridge_session_id'] == 'new' and not row.get('bridge_received_at')
    assert store.pending(resolve_project='Egitto2', timeline_id='', bridge_session_id='new')[0]['package_id'] == package['package_id']


def test_reconnect_rejects_wrong_project_and_applying_package(tmp_path):
    store = ResolveHandoffStore(tmp_path)
    root = tmp_path / 'p1'; root.mkdir()
    package = store.prepare(root, _payload(bridge_session_id='old'))
    with pytest.raises(ValueError, match='(?i)progetto'):
        store.reconnect(root, package['package_id'], bridge_session_id='new', resolve_project='Wrong', timeline_id='tl-1')
    store.transition(root, package['package_id'], 'applying')
    with pytest.raises(ValueError, match='applicazione'):
        store.reconnect(root, package['package_id'], bridge_session_id='new', resolve_project='Egitto2', timeline_id='tl-1')


def test_reconnect_rejects_native_cut_reference_on_wrong_timeline(tmp_path):
    store = ResolveHandoffStore(tmp_path)
    root = tmp_path / 'p1'; root.mkdir()
    package = store.prepare(root, _payload(bridge_session_id='old', native_cut_reference={'x': 1}))
    with pytest.raises(ValueError, match='timeline'):
        store.reconnect(root, package['package_id'], bridge_session_id='new', resolve_project='Egitto2', timeline_id='wrong')
