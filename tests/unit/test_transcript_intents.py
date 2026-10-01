import json
from pathlib import Path
import shutil
import uuid

import pytest

from backend.app.editorial_import import digest
from backend.app.transcript_intents import (
    load_phrase_intents,
    planning_chunks_for_coverage,
    save_phrase_intents,
    save_transcript_document,
    transcript_document,
)
from backend.app.transcript_corrections import needs_editorial_refresh


@pytest.fixture
def workdir():
    path = Path(f".transcript-intents-test-{uuid.uuid4().hex}")
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _run(workdir):
    run = workdir / "run"
    run.mkdir()
    chunks = [
        {"id": "chunk_001", "start": 0.0, "end": 2.0, "text": "Ciao mondo.", "words": [
            {"start": 0.0, "end": 0.8, "text": "Ciao"},
            {"start": 0.8, "end": 2.0, "text": "mondo."},
        ]},
        {"id": "chunk_002", "start": 2.0, "end": 5.0, "text": "Poi cambia tutto.", "words": [
            {"start": 2.0, "end": 3.0, "text": "Poi"},
            {"start": 3.0, "end": 4.0, "text": "cambia"},
            {"start": 4.0, "end": 5.0, "text": "tutto."},
        ]},
    ]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "semantic-beats.json").write_text(json.dumps({"schema_version": "content-sprint-0.1", "beats": []}), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"language": "it", "timeline_fps": 25, "segments": chunks}), encoding="utf-8")
    (run / "analysis-signature.json").write_text(json.dumps({"analysis_signature": "analysis-1"}), encoding="utf-8")
    return run


def test_intents_are_independent_and_persisted(workdir):
    run = _run(workdir)
    initial = load_phrase_intents(run)
    assert initial["explicit"] is False
    assert initial["phrases"]["chunk_001"] == {
        "coverage": False, "animation": False, "highlight": False,
        "coverage_word_indices": [], "animation_word_indices": [], "highlighted_word_indices": [],
    }

    saved = save_phrase_intents(
        run,
        {"chunk_001": {"coverage": True, "animation": True, "highlighted_word_indices": [1]}},
        initial["transcript_signature"],
    )
    assert saved["phrases"]["chunk_001"] == {
        "coverage": True, "animation": True, "highlight": True,
        "coverage_word_indices": [0, 1], "animation_word_indices": [0, 1], "highlighted_word_indices": [1],
    }
    assert saved["phrases"]["chunk_002"] == {
        "coverage": False, "animation": False, "highlight": False,
        "coverage_word_indices": [], "animation_word_indices": [], "highlighted_word_indices": [],
    }


def test_highlighted_words_are_validated_against_real_word_timing(workdir):
    run = _run(workdir)
    state = load_phrase_intents(run)
    with pytest.raises(ValueError, match="word index"):
        save_phrase_intents(run, {"chunk_001": {"highlighted_word_indices": [2]}}, state["transcript_signature"])


def test_visual_plan_does_not_preselect_coverage_for_a_new_project(workdir):
    run = _run(workdir)
    (run / "visual-plan.json").write_text(json.dumps({
        "visual_beats": [{"action": "BROLL", "covered_chunk_ids": ["chunk_001"]}],
    }), encoding="utf-8")
    state = load_phrase_intents(run)
    assert state["explicit"] is False
    assert state["phrases"]["chunk_001"]["coverage_word_indices"] == []
    assert state["phrases"]["chunk_001"]["coverage"] is False


def test_stale_intent_signature_changes_nothing(workdir):
    run = _run(workdir)
    before = list(run.iterdir())
    with pytest.raises(ValueError, match="changed"):
        save_phrase_intents(run, {"chunk_001": {"coverage": True}}, "stale")
    assert list(run.iterdir()) == before
    assert not (run / "phrase-intents.json").exists()


def test_stored_intents_from_another_transcript_are_not_reused(workdir):
    run = _run(workdir)
    (run / "phrase-intents.json").write_text(json.dumps({
        "schema_version": "rambla-phrase-intents-1", "transcript_signature": "old",
        "phrases": {"chunk_001": {"coverage": True, "animation": True, "highlight": True}},
    }), encoding="utf-8")
    state = load_phrase_intents(run)
    assert state["explicit"] is True
    assert state["phrases"]["chunk_001"] == {
        "coverage": False, "animation": False, "highlight": False,
        "coverage_word_indices": [], "animation_word_indices": [], "highlighted_word_indices": [],
    }


def test_coverage_change_marks_existing_plan_stale_without_deleting_it(workdir):
    run = _run(workdir)
    plan = {"schema_version": "rambla-visual-plan-1", "visual_beats": []}
    (run / "visual-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    before = (run / "visual-plan.json").read_bytes()
    state = load_phrase_intents(run)

    save_phrase_intents(run, {"chunk_001": {"coverage": True}}, state["transcript_signature"])

    assert (run / "visual-plan.json").read_bytes() == before
    assert needs_editorial_refresh(run) is True


def test_long_coverage_is_split_into_short_searchable_beats(workdir):
    run = _run(workdir)
    words = [
        {"start": index * 0.5, "end": (index + 1) * 0.5, "text": f"word{index}"}
        for index in range(18)
    ]
    chunks = [{"id": "long", "start": 0.0, "end": 9.0,
               "text": " ".join(word["text"] for word in words), "words": words}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"long": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert len(selected) == 3
    assert all(len(row["words"]) <= 10 for row in selected)
    assert all(row["end"] - row["start"] <= 4.0 for row in selected)
    assert [row["source_word_start_index"] for row in selected] == [0, 8, 16]


def test_coverage_preserves_spoken_segment_before_applying_word_limit(workdir):
    run = _run(workdir)
    texts = ["davvero", "nessuno", "ha", "vissuto", "una", "storia", "di", "violenza", "importante",
             "Negli", "anni", "novanta", "questa", "zona", "cambiò"]
    words = [
        {"start": index * .4, "end": (index + 1) * .4, "text": text}
        for index, text in enumerate(texts)
    ]
    chunks = [{"id": "story", "start": 0.0, "end": 6.0, "text": " ".join(texts), "words": words}]
    raw_segments = [
        {"start": 0.0, "end": 3.6, "text": " ".join(texts[:9]), "words": words[:9]},
        {"start": 3.6, "end": 6.0, "text": " ".join(texts[9:]), "words": words[9:]},
    ]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"segments": raw_segments}), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"story": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert [row["text"] for row in selected] == [
        "davvero nessuno ha vissuto una storia di violenza importante",
        "Negli anni novanta questa zona cambiò",
    ]


def test_coverage_uses_spoken_restart_before_duration_cut(workdir):
    run = _run(workdir)
    texts = [
        "Elmini", "ha", "vissuto", "una", "storia", "di", "violenza", "importante",
        "Negli", "anni", "90", "questa", "zona", "fu", "una", "delle", "più", "colpite",
    ]
    words = [
        {"start": index * .32, "end": (index + 1) * .32, "text": text}
        for index, text in enumerate(texts)
    ]
    chunks = [{"id": "history", "start": 0.0, "end": 5.76,
               "text": " ".join(texts), "words": words}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"segments": [chunks[0]]}), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"history": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert [row["text"] for row in selected] == [
        "Elmini ha vissuto una storia di violenza importante",
        "Negli anni 90 questa zona fu una delle più colpite",
    ]


def test_coverage_rebalances_final_orphan_without_splitting_polizia_turistica(workdir):
    run = _run(workdir)
    texts = ["soprattutto", "in", "una", "cosa", "molto", "concreta", "la", "presenza",
             "costante", "della", "polizia", "turistica."]
    times = [
        (0.00, .28), (.28, .46), (.46, .66), (.66, .94), (.94, 1.12), (1.12, 1.34),
        (1.44, 1.66), (1.66, 2.00), (2.00, 2.60), (2.60, 2.84), (2.84, 3.16), (3.16, 4.08),
    ]
    words = [
        {"start": start, "end": end, "text": text}
        for text, (start, end) in zip(texts, times)
    ]
    chunks = [{"id": "police", "start": 0.0, "end": 4.08,
               "text": " ".join(texts), "words": words}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"segments": [chunks[0]]}), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"police": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert [row["text"] for row in selected] == [
        "soprattutto in una cosa molto concreta",
        "la presenza costante della polizia turistica.",
    ]
    assert all(row["end"] - row["start"] <= 4.0 for row in selected)


def test_coverage_splits_unpunctuated_sentence_and_keeps_jihadist_noun_phrase(workdir):
    run = _run(workdir)
    texts = (
        "cioè veramente nessuno Elmini ha vissuto una storia di violenza importante "
        "Negli anni 90 questa zona fu una delle più colpite delle attività dei gruppi jihadisti"
    ).split()
    words = [
        {"start": index * .305, "end": (index + 1) * .305, "text": text}
        for index, text in enumerate(texts)
    ]
    chunks = [{"id": "history", "start": 0.0, "end": len(words) * .305,
               "text": " ".join(texts), "words": words}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"segments": [chunks[0]]}), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"history": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert [row["text"] for row in selected] == [
        "cioè veramente nessuno",
        "Elmini ha vissuto una storia di violenza importante",
        "Negli anni 90 questa zona fu una delle più colpite",
        "delle attività dei gruppi jihadisti",
    ]


def test_coverage_does_not_orphan_capitalized_name_at_end(workdir):
    run = _run(workdir)
    texts = "Amarna la città che Achenaton".split()
    words = [
        {"start": index * .25, "end": (index + 1) * .25, "text": text}
        for index, text in enumerate(texts)
    ]
    chunks = [{"id": "place", "start": 0.0, "end": 1.25,
               "text": " ".join(texts), "words": words}]
    (run / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
    (run / "transcript-raw.json").write_text(json.dumps({"segments": [chunks[0]]}), encoding="utf-8")
    state = load_phrase_intents(run)
    save_phrase_intents(run, {"place": {"coverage": True}}, state["transcript_signature"])

    selected = [row for row in planning_chunks_for_coverage(run) if row["coverage_selected"]]

    assert [row["text"] for row in selected] == ["Amarna la città che Achenaton"]


def test_full_transcript_save_retimes_words_and_remaps_tags(workdir):
    run = _run(workdir)
    (run / "visual-plan.json").write_text("{}", encoding="utf-8")
    doc = transcript_document(run)
    save_phrase_intents(run, {"chunk_002": {"animation": True}}, doc["transcript_signature"])
    saved = save_transcript_document(
        run,
        "Ciao grande mondo.\nPoi cambia davvero tutto.",
        doc["revision"],
    )

    chunks = json.loads((run / "semantic-chunks.json").read_text(encoding="utf-8"))
    assert [row["text"] for row in chunks] == ["Ciao grande mondo.", "Poi cambia davvero tutto."]
    assert chunks[0]["start"] == 0.0 and chunks[0]["end"] == 2.0
    assert chunks[1]["start"] == 2.0 and chunks[1]["end"] == 5.0
    assert len(chunks[0]["words"]) == 3
    assert all(a["end"] <= b["start"] for a, b in zip(chunks[0]["words"], chunks[0]["words"][1:]))
    intents = load_phrase_intents(run)
    assert intents["phrases"]["chunk_002"]["animation"] is True
    assert saved["editorial_refresh_required"] is True


def test_stale_transcript_revision_changes_no_artifact(workdir):
    run = _run(workdir)
    before = {path.name: path.read_bytes() for path in run.iterdir()}
    with pytest.raises(ValueError, match="changed"):
        save_transcript_document(run, "Nuovo testo.", "stale")
    assert {path.name: path.read_bytes() for path in run.iterdir()} == before


def test_added_lines_stay_ordered_inside_source_duration(workdir):
    run = _run(workdir)
    doc = transcript_document(run)
    save_transcript_document(run, "Uno.\nDue.\nTre.", doc["revision"])
    chunks = json.loads((run / "semantic-chunks.json").read_text(encoding="utf-8"))
    assert [row["text"] for row in chunks] == ["Uno.", "Due.", "Tre."]
    assert chunks[0]["start"] == 0.0
    assert chunks[-1]["end"] == 5.0
    assert all(a["end"] <= b["start"] for a, b in zip(chunks, chunks[1:]))
