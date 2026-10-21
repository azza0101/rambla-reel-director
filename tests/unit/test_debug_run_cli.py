import json
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

from backend.app.debug_run_cli import _consume_segments, analysis_input_signature, build_image_intent, build_short_outline, build_video_diagnostics, editorial_artifacts_match, invalidate_stale_analysis_outputs, persist_analysis_signature, semantic_query_variants


def workspace_dir() -> Path:
    root = Path.cwd() / ".test-debug-cli" / uuid.uuid4().hex
    root.mkdir(parents=True)
    return root


def test_analysis_input_signature_tracks_source_and_guide_independently():
    root = workspace_dir()
    try:
        source = root / "source.mp4"; guide = root / "guide.wav"
        source.write_bytes(b"video"); guide.write_bytes(b"guide")
        signature = analysis_input_signature(source, guide)
        assert signature["source"]["video"] == str(source.resolve())
        assert signature["guide"]["video"] == str(guide.resolve())
    finally:
        shutil.rmtree(root)


def test_analysis_marker_is_written_only_after_required_success_artifacts():
    root = workspace_dir()
    try:
        persist_analysis_signature(root, "sig")
        assert not (root / "analysis-signature.json").exists()
        for name in ("semantic-chunks.json", "review.html", "edit-plan.json"):
            (root / name).write_text("ok", encoding="utf-8")
        persist_analysis_signature(root, "sig")
        assert json.loads((root / "analysis-signature.json").read_text(encoding="utf-8")) == {"analysis_signature": "sig"}
    finally:
        shutil.rmtree(root)


def test_changed_guide_cannot_reuse_or_rebless_stale_downstream_artifacts():
    root = workspace_dir()
    try:
        for name in ("online-candidates.json", "image-candidates.json", "edit-plan.json", "review.html"):
            (root / name).write_text("old", encoding="utf-8")
        (root / "analysis-signature.json").write_text('{"analysis_signature":"run-a"}', encoding="utf-8")

        assert editorial_artifacts_match(root, "run-b") is False
        invalidate_stale_analysis_outputs(root, "run-b")
        assert not any((root / name).exists() for name in ("online-candidates.json", "image-candidates.json", "edit-plan.json", "review.html", "analysis-signature.json"))
        persist_analysis_signature(root, "run-b")
        assert not (root / "analysis-signature.json").exists()
    finally:
        shutil.rmtree(root)


def test_main_uses_guide_for_asr_but_source_for_timeline(monkeypatch):
    import backend.app.debug_run_cli as cli
    root = workspace_dir(); captured = {}
    try:
        source = root / "source.mp4"; guide = root / "guide.wav"; output = root / "run"
        source.write_bytes(b"video"); guide.write_bytes(b"audio"); output.mkdir()
        for name in ("online-candidates.json", "edit-plan.json", "review.html"):
            (output / name).write_text("ok", encoding="utf-8")
        (output / "image-candidates.json").write_text('{"chunks":{"chunk-1":{"candidates":[{}]}}}', encoding="utf-8")
        (output / "analysis-signature.json").write_text('{"analysis_signature":"sig"}', encoding="utf-8")
        def asr(path, **kwargs):
            captured.update(path=path, **kwargs)
            return {"timeline_fps": kwargs["timeline_fps"], "segments": [{"words": [{"text": "hello", "start": 0, "end": 1}]}]}, "fresh"
        monkeypatch.setattr(cli, "_probe", lambda _: (10.0, 250))
        monkeypatch.setattr(cli, "run_asr_stage", asr)
        monkeypatch.setattr(cli, "DEFAULT_MODEL_CACHE", root / "models")
        monkeypatch.setattr(cli, "discover_image_candidates", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("analyze must not source images")))
        monkeypatch.setattr(cli.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("analyze must not source videos")))
        monkeypatch.setattr("sys.argv", ["debug_run_cli", "--video", str(source), "--guide-audio", str(guide), "--output-dir", str(output), "--analysis-signature", "sig", "--stage", "analyze"])
        cli.main()
        assert captured["path"] == guide.resolve()
        assert captured["timeline_fps"] == 25
        assert (output / "semantic-chunks.json").is_file()
    finally:
        shutil.rmtree(root)


def test_semantic_chunking_splits_complete_italian_ideas_not_fixed_word_counts():
    tokens = "La città cambia rapidamente, ma i quartieri storici resistono. Quindi i giovani cercano nuovi spazi creativi.".split()
    words = [{"text": token, "start": i * 0.35, "end": (i + 1) * 0.35} for i, token in enumerate(tokens)]
    _, chunks = build_short_outline({"segments": [{"words": words}]}, max_chunk_seconds=20)
    texts = [chunk["text"] for chunk in chunks]
    assert texts == ["La città cambia rapidamente,", "ma i quartieri storici resistono.", "Quindi i giovani cercano nuovi spazi creativi."]
    assert [len(text.split()) for text in texts] == [4, 5, 7]


def test_semantic_chunking_protects_subordinates_and_short_punchlines():
    tokens = "Quando arriviamo nel villaggio, scopriamo che le famiglie lavorano insieme. Poi cambia tutto. Il viaggio diventa una responsabilità condivisa.".split()
    words = []; clock = 0.0
    for token in tokens:
        if token == "Poi": clock += 0.8
        words.append({"text": token, "start": clock, "end": clock + .42}); clock += .42
    _, chunks = build_short_outline({"segments": [{"words": words}]})
    texts = [chunk["text"] for chunk in chunks]
    assert all(not text.endswith(" che") for text in texts)
    assert "Poi cambia tutto." in texts
    assert all(chunk["duration"] <= 8.0 for chunk in chunks)


def test_semantic_chunking_normalizes_tiny_boundary_overlaps():
    words = [
        {"text": "Prima", "start": 0.0, "end": 0.3},
        {"text": "frase", "start": 0.3, "end": 0.6},
        {"text": "qui.", "start": 0.6, "end": 1.0},
        {"text": "Dopo", "start": 0.97, "end": 1.3},
        {"text": "frase", "start": 1.3, "end": 1.6},
        {"text": "ora.", "start": 1.6, "end": 2.0},
    ]
    _, chunks = build_short_outline({"segments": [{"words": words}]})
    assert len(chunks) == 2
    assert chunks[1]["start"] >= chunks[0]["end"]
    assert chunks[1]["duration"] > 0


def test_semantic_chunking_does_not_orphan_last_word_after_long_enumeration():
    tokens = "Avevo trovato un centro che sembrava perfetto, niente spettacoli, niente cavalcate, solo parole giuste, etico, responsabile, sostenibile.".split()
    words = [{"text": token, "start": i * .48, "end": (i + 1) * .48} for i, token in enumerate(tokens)]
    _, chunks = build_short_outline({"segments": [{"words": words}]})
    assert all(len(chunk["text"].split()) >= 3 for chunk in chunks)
    assert chunks[-1]["text"].endswith("sostenibile.")
    assert all(chunk["duration"] <= 8.0 for chunk in chunks)


def test_semantic_queries_remove_narration_filler_and_keep_visual_subject():
    queries = semantic_query_variants(
        "Per esempio in Thailandia avevo trovato un centro elefanti che sembrava perfetto"
    )
    assert queries[0] == "Thailandia centro elefanti"
    assert all("avevo trovato" not in query for query in queries)


def test_diagnostic_lexical_intent_preserves_context_without_domain_templates():
    chunks = [
        {"id": "chunk-1", "text": "Possiamo chiamarlo turismo sostenibile."},
        {"id": "chunk-2", "text": "Per arrivarci prendiamo tre voli, autobus e barche."},
        {"id": "chunk-3", "text": "Quindi, il punto non è non partire."},
    ]
    outline = {"beats": [{"id": "chunk-3", "intent": "responsible travel choices", "broll_queries": []}]}
    intent = build_image_intent(2, chunks, outline)
    assert intent["intent"] == "responsible travel choices"
    assert intent["queries"] == ["punto partire"]
    assert "tre voli" in intent["context"]
    assert all("point" not in query.casefold() for query in intent["queries"])


def test_partial_asr_callback_exposes_growing_transcript():
    words = lambda text, start: [SimpleNamespace(word=text, start=start, end=start + .4)]
    segments = [
        SimpleNamespace(text="Prima", start=0.0, end=.4, words=words("Prima", 0.0)),
        SimpleNamespace(text="Seconda", start=.5, end=.9, words=words("Seconda", .5)),
    ]
    updates = []
    rows = _consume_segments(
        iter(segments), SimpleNamespace(language="it", duration=1.0), 25,
        lambda partial, progress: updates.append((partial, progress)),
    )
    assert rows == segments
    assert [len(partial["segments"]) for partial, _ in updates] == [1, 2]
    assert [progress for _, progress in updates] == [40.0, 90.0]
    assert all(partial["timeline_fps"] == 25 for partial, _ in updates)


def test_independent_sourcing_stages_reuse_analysis_without_cross_calls(monkeypatch):
    import backend.app.debug_run_cli as cli
    root = workspace_dir()
    try:
        source = root / "source.mp4"; source.write_bytes(b"video")
        monkeypatch.setattr(cli, "_probe", lambda _: (10.0, 250))
        monkeypatch.setattr(cli, "DEFAULT_MODEL_CACHE", root / "models")
        monkeypatch.setattr(cli, "run_asr_stage", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("sourcing must not rerun ASR")))

        video_output = root / "videos"; video_output.mkdir()
        image_output = root / "images"; image_output.mkdir()
        for output in (video_output, image_output):
            (output / "transcript-raw.json").write_text('{"segments":[]}', encoding="utf-8")
            (output / "semantic-beats.json").write_text('{"beats":[]}', encoding="utf-8")
            (output / "semantic-chunks.json").write_text('[{"id":"chunk-1"}]', encoding="utf-8")

        from backend.app.editorial_import import transcript_package, import_plan, retrieval_bundle
        for output in (video_output,image_output):
            (output/'semantic-chunks.json').write_text(json.dumps([{'id':'chunk-1','start':0.0,'end':10.0,'text':'Example.'}]),encoding='utf-8')
            package=transcript_package(output,'demo',10.0)
            import_plan(output,{'schema_version':'rambla-visual-plan-1','project_id':'demo','transcript_signature':package['transcript_signature'],'global_topic':'Example','visual_beats':[{'id':'vb-1','start':0.0,'end':10.0,'covered_chunk_ids':['chunk-1'],'original_text':'Example.','action':'KEEP_TALKING_HEAD','editorial_function':'statement','core_meaning':'Example','subtext':'','visual_mode':'single','shots':[],'avoid':[]}]},package)
        video_calls = []
        monkeypatch.setattr(cli.subprocess, "run", lambda command, check: video_calls.append(command))
        monkeypatch.setattr(cli, "discover_image_candidates", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("video stage must not source images")))
        monkeypatch.setattr("sys.argv", ["debug_run_cli", "--video", str(source), "--output-dir", str(video_output), "--stage", "videos"])
        cli.main()
        assert len(video_calls) == 1
        assert (video_output / "video-sourcing.json").is_file()

        image_calls = []
        def run_images(command, check):
            image_calls.append(command)
            (retrieval_bundle(image_output)[0] / "image-candidates.json").write_text('{"chunks":{"chunk-1":{"candidates":[]}}}', encoding="utf-8")
        monkeypatch.setattr(cli.subprocess, "run", run_images)
        monkeypatch.setattr("sys.argv", ["debug_run_cli", "--video", str(source), "--output-dir", str(image_output), "--stage", "images"])
        cli.main()
        assert len(image_calls) == 1 and "backend.app.image_sourcing_cli" in image_calls[0]
        assert (image_output / "image-sourcing.json").is_file()
    finally:
        shutil.rmtree(root)


def test_video_diagnostics_explain_results_rejections_scores_and_previews():
    result = build_video_diagnostics([{"parent_beat_id": "chunk-1", "queries": ["artisan workshop"], "candidates": [{"id": "v1", "source": "pexels", "qwen_score": .81, "preview_path": "v.mp4"}], "rejected_candidates": [{"id": "v2", "reason": "rights"}]}])
    row = result["chunks"][0]
    assert row["queries"] == ["artisan workshop"] and row["providers"] == ["pexels"]
    assert row["raw_results"] == 2 and row["rejection_reasons"] == ["rights"]
    assert row["ranked"] == [{"asset_id": "v1", "score": .81, "preview": "ready"}]


def test_hydrated_asset_ids_remain_unique_when_provider_repeats_across_chunks():
    from backend.app.curation_artifacts import load_curation_run
    root = workspace_dir()
    try:
        chunks = [{"id": "chunk-1", "text": "one"}, {"id": "chunk-2", "text": "two"}]
        image = {"provider": "wikimedia", "provider_id": "same", "source_page": "https://commons.wikimedia.org/x", "title": "Same", "rights_state": "known_public_license", "orientation": "landscape", "thumbnail_url": "https://upload.wikimedia.org/x.jpg"}
        images = {"chunks": {chunk["id"]: {"candidates": [image]} for chunk in chunks}}
        (root / "semantic-chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
        (root / "online-candidates.json").write_text("[]", encoding="utf-8")
        (root / "image-candidates.json").write_text(json.dumps(images), encoding="utf-8")
        run = load_curation_run(root)
        assert len(run.candidate_index) == 2
        assert {candidate.chunk_id for candidate in run.candidate_index.values()} == {"chunk-1", "chunk-2"}
    finally:
        shutil.rmtree(root)
