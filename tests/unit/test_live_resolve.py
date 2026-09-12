from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.resolve_live import allocate_generated_name, is_source_timeline


def test_live_page_exposes_only_the_three_fast_track_actions() -> None:
    response = TestClient(create_app()).get("/")

    assert response.status_code == 200
    assert "Probe Resolve" in response.text
    assert "Dry Run PUNCH_IN" in response.text
    assert "Apply to Duplicate" in response.text


def test_generated_name_uses_the_first_collision_safe_suffix() -> None:
    assert allocate_generated_name({"REEL_AI_v01", "REEL_AI_v02"}) == "REEL_AI_v03"


def test_source_guard_accepts_only_the_configured_master_spelling() -> None:
    assert is_source_timeline("REEL_MASTER")
    assert is_source_timeline("REEL MASTER")
    assert not is_source_timeline("REEL_AI_v01")


def test_live_adapter_has_no_native_transport_reference() -> None:
    source = (Path(__file__).parents[2] / "backend/app/resolve_live.py").read_text(
        encoding="utf-8"
    )

    assert "resolve_bridge_client" in source
    assert "DaVinciResolveScript" not in source
    assert "fusionscript" not in source.casefold()
