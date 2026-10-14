import json
from pathlib import Path
import shutil
import uuid

import pytest

from backend.app.captions import render_semantic_srt
from backend.app.transcript_intents import (
    build_animation_export,
    build_combined_resolve_export,
    build_textplus_export,
    transcript_document,
)


@pytest.fixture
def run():
    root = Path(f".transcript-exports-test-{uuid.uuid4().hex}")
    root.mkdir()
    chunks = [
        {"id": "c1", "start": 0.0, "end": 1.5, "text": "Uno due tre", "words": [
            {"start": 0.0, "end": 0.5, "text": "Uno"}, {"start": 0.5, "end": 1.0, "text": "due"}, {"start": 1.0, "end": 1.5, "text": "tre"}]},
        {"id": "c2", "start": 1.5, "end": 3.5, "text": "Quattro cinque, sei sette", "words": [
            {"start": 1.5, "end": 2.0, "text": "Quattro"}, {"start": 2.0, "end": 2.5, "text": "cinque,"},
            {"start": 2.5, "end": 3.0, "text": "sei"}, {"start": 3.0, "end": 3.5, "text": "sette"}]},
        {"id": "c3", "start": 4.0, "end": 5.0, "text": "Otto nove", "words": [
            {"start": 4.0, "end": 4.5, "text": "Otto"}, {"start": 4.5, "end": 5.0, "text": "nove"}]},
    ]
    (root / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    signature = transcript_document(root)["transcript_signature"]
    (root / "phrase-intents.json").write_text(json.dumps({
        "schema_version": "rambla-phrase-intents-1", "transcript_signature": signature, "phrases": {
            "c1": {"coverage": False, "animation": True, "highlight": True, "highlighted_word_indices": [1, 2]},
            "c2": {"coverage": True, "animation": True, "highlight": False},
            "c3": {"coverage": False, "animation": False, "highlight": True, "highlighted_word_indices": [0]},
        }}), encoding="utf-8")
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_semantic_srt_never_exceeds_three_words(run):
    chunks = json.loads((run / "semantic-chunks.json").read_text(encoding="utf-8"))
    output = render_semantic_srt(chunks)
    cue_text = [block.splitlines()[2] for block in output.strip().split("\n\n")]
    assert cue_text == ["Uno due tre", "Quattro cinque,", "sei sette", "Otto nove"]
    assert "00:00:01,500 --> 00:00:02,500" in output


def test_subtitles_include_highlighted_words_when_titles_are_not_exported(run):
    result = build_combined_resolve_export(run, 'p', fps=30000/1001, include_highlights=False)
    assert result['titles'] == []
    assert ' '.join(row['text'] for row in result['subtitles']) == 'Uno due tre Quattro cinque, sei sette Otto nove'
    assert result['fps'] == 30000/1001


def test_animation_export_keeps_order_separators_and_concatenation(run):
    result = build_animation_export(run, "project-1")
    assert result["schema_version"] == "rambla-animation-selection-2"
    phrases = [row for row in result["items"] if row["type"] == "phrase"]
    assert [row["id"] for row in phrases] == ["c1", "c2"]
    assert phrases[1]["concatenated_with_previous"] is True
    assert phrases[1]["duration_seconds"] == 2.0
    assert any(row.get("relationship") == "consecutive" for row in result["items"])


def test_textplus_export_joins_selected_words_and_uses_real_frames(run):
    result = build_textplus_export(run, "project-1", fps=25)
    assert result["schema_version"] == "rambla-resolve-textplus-1"
    assert [row["text"] for row in result["items"]] == ["due tre", "Otto"]
    assert result["items"][0] == {
        "kind": "TEXT_PLUS", "phrase_id": "c1", "text": "due tre",
        "word_start_index": 1, "word_end_index": 2,
        "start_seconds": 0.5, "end_seconds": 1.5, "duration_seconds": 1.0,
        "start_frame": 12, "end_frame": 38, "track_hint": 3,
    }


def test_textplus_splits_more_than_three_consecutive_words(run):
    payload = json.loads((run / "phrase-intents.json").read_text(encoding="utf-8"))
    payload["phrases"]["c1"]["highlighted_word_indices"] = []
    payload["phrases"]["c1"]["highlight"] = False
    payload["phrases"]["c2"]["highlighted_word_indices"] = [0, 1, 2, 3]
    payload["phrases"]["c2"]["highlight"] = True
    payload["phrases"]["c3"]["highlighted_word_indices"] = []
    payload["phrases"]["c3"]["highlight"] = False
    (run / "phrase-intents.json").write_text(json.dumps(payload), encoding="utf-8")
    result = build_textplus_export(run, "project-1", fps=25)
    assert [row["text"] for row in result["items"]] == ["Quattro cinque, sei", "sette"]


def test_combined_export_excludes_highlights_only_from_subtitles(run):
    result = build_combined_resolve_export(run, "project-1", fps=25)

    assert [row["text"] for row in result["titles"]] == ["due tre", "Otto"]
    assert [row["text"] for row in result["subtitles"]] == [
        "Uno", "Quattro cinque, sei", "sette", "nove",
    ]
    assert result["subtitles"][1]["start_frame"] == round(1.5 * 25)
    assert all(len(row["text"].split()) <= 3 for row in result["subtitles"])


def test_combined_subtitles_never_join_across_a_highlighted_word(run):
    payload = json.loads((run / "phrase-intents.json").read_text(encoding="utf-8"))
    payload["phrases"]["c2"].update(highlight=True, highlighted_word_indices=[1])
    (run / "phrase-intents.json").write_text(json.dumps(payload), encoding="utf-8")

    result = build_combined_resolve_export(run, "project-1", fps=25)

    assert [row["text"] for row in result["subtitles"] if row["phrase_id"] == "c2"] == ["Quattro", "sei sette"]
    assert any(row["text"] == "cinque," for row in result["titles"])


def test_combined_export_allows_zero_subtitles_when_every_word_is_highlighted(run):
    payload = json.loads((run / "phrase-intents.json").read_text(encoding="utf-8"))
    chunks = json.loads((run / "semantic-chunks.json").read_text(encoding="utf-8"))
    for chunk in chunks:
        payload["phrases"][chunk["id"]].update(
            highlight=True,
            highlighted_word_indices=list(range(len(chunk["words"]))),
        )
    (run / "phrase-intents.json").write_text(json.dumps(payload), encoding="utf-8")

    result = build_combined_resolve_export(run, "project-1", fps=25)

    assert result["subtitles"] == []
    assert result["titles"]


def test_export_requires_a_selection(run):
    payload = json.loads((run / "phrase-intents.json").read_text(encoding="utf-8"))
    for value in payload["phrases"].values():
        value["animation"] = False
    (run / "phrase-intents.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Animation"):
        build_animation_export(run, "project-1")
