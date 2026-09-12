from __future__ import annotations

from backend.app.proposals import select_proposals


def _row(
    asset_id: str,
    *,
    score: float,
    source: str,
    provider_id: str,
    width: int,
    height: int,
    preview_sha256: str,
) -> dict:
    return {
        "id": asset_id,
        "score": score,
        "embedding_score": score,
        "source": source,
        "provider_id": provider_id,
        "width": width,
        "height": height,
        "preview_sha256": preview_sha256,
    }


def test_two_distinct_proposals_are_retained() -> None:
    rows = [
        _row("youtube:1", score=.91, source="youtube", provider_id="1", width=1920, height=1080, preview_sha256="a"),
        _row("pexels:2", score=.84, source="pexels", provider_id="2", width=1080, height=1920, preview_sha256="b"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] in {"youtube:1", "pexels:2"}
    assert result["proposal_B"] is not None
    assert result["proposal_B"]["id"] != result["proposal_A"]["id"]
    assert result["review_state"] == "READY"
    assert 0 <= result["proposal_A"]["crop_score"] <= 1
    assert len(result["proposal_A"]["crop_box"]) == 4


def test_crop_score_can_demote_semantically_close_landscape_candidate() -> None:
    rows = [
        _row("landscape", score=.90, source="youtube", provider_id="1", width=1920, height=1080, preview_sha256="a"),
        _row("portrait", score=.86, source="pexels", provider_id="2", width=1080, height=1920, preview_sha256="b"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] == "portrait"
    assert result["proposal_A"]["final_score"] > result["proposal_B"]["final_score"]


def test_duplicate_preview_is_not_used_as_second_proposal() -> None:
    rows = [
        _row("one", score=.95, source="youtube", provider_id="1", width=1080, height=1920, preview_sha256="same"),
        _row("duplicate", score=.94, source="youtube", provider_id="2", width=1080, height=1920, preview_sha256="same"),
        _row("different", score=.80, source="pexels", provider_id="3", width=1080, height=1920, preview_sha256="different"),
    ]

    result = select_proposals(rows)

    assert result["proposal_A"]["id"] == "one"
    assert result["proposal_B"]["id"] == "different"


def test_single_candidate_is_explicitly_marked() -> None:
    result = select_proposals([
        _row("one", score=.8, source="pexels", provider_id="1", width=1080, height=1920, preview_sha256="a")
    ])

    assert result["proposal_B"] is None
    assert result["review_state"] == "SINGLE_PROPOSAL"


def test_empty_candidates_report_no_visual_found() -> None:
    result = select_proposals([])

    assert result["proposal_A"] is None
    assert result["proposal_B"] is None
    assert result["review_state"] == "NO_VISUAL_FOUND"
