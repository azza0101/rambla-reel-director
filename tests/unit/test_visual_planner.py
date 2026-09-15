import importlib.util


def _flat_embedder(items):
    return [[1.0, 0.0] for _ in items]


def test_kura_meaning_becomes_concrete_searchable_shots_with_context_inheritance():
    assert importlib.util.find_spec("backend.app.visual_planner") is not None
    from backend.app.visual_planner import ConcreteVisualPlanner

    chunks = [
        {"id": "transport", "text": "turismo sostenibile ma prendiamo tre voli, un autobus e due barche"},
        {"id": "story", "text": "forse di sostenibile c'è solo il racconto che ci facciamo di noi stessi"},
        {"id": "label", "text": "appiccicarci sopra un'etichetta verde"},
        {"id": "ideal", "text": "strutture locali, zero plastica, guide del posto, orto"},
        {"id": "chickens", "text": "galline possibilmente consenzienti"},
        {"id": "elephant", "text": "in Thailandia un centro elefanti che sembrava etico"},
        {"id": "accountability", "text": "chi possedeva la struttura, quanto venissero pagati i lavoratori, dove finissero i soldi"},
        {"id": "silence", "text": "Silenzio."},
        {"id": "basil", "text": "scrivere eco sull'insegna e basilico mezzo morto sul balcone diventa rigenerazione urbana"},
        {"id": "flight", "text": "volo intercontinentale per Bangkok ecosostenibile e coscienza pulita"},
        {"id": "compromise", "text": "accettare il compromesso e provare a ridurre il danno"},
        {"id": "exploitation", "text": "non sfruttare persone o animali e non impoverire i territori per chi vive nei luoghi"},
        {"id": "cta", "text": "viaggio su misura, scrivici in DM, lo costruiamo insieme"},
    ]
    artifact = ConcreteVisualPlanner(embed=_flat_embedder).plan(chunks, {"beats": []})
    plans = artifact["chunks"]
    expected = {
        "transport": "transport_chain", "story": "self_story", "label": "green_label",
        "ideal": "local_eco_ideal", "chickens": "consenting_chickens", "elephant": "elephant_sanctuary",
        "accountability": "tourism_accountability", "silence": "tourism_accountability",
        "basil": "eco_sign_basil", "flight": "long_haul_flight", "compromise": "harm_reduction",
        "exploitation": "exploitation_overtourism", "cta": "custom_trip_cta",
    }
    assert {chunk_id: row["template_id"] for chunk_id, row in plans.items()} == expected
    assert plans["transport"]["visual_mode"] == "sequence"
    assert [shot["shot_id"] for shot in plans["transport"]["shots"]] == ["airplane", "transfer_bus", "passenger_ferry"]
    assert plans["silence"]["core_meaning"] == plans["accountability"]["core_meaning"]
    assert plans["silence"]["editorial_function"] == "pause"
    assert "silence" not in " ".join(query for shot in plans["silence"]["shots"] for query in shot["image_queries"]).casefold()
    banned = {"contradiction", "subtext", "meaning", "compromise", "conscience", "morality"}
    for row in plans.values():
        assert row["avoid"]
        assert row["planner_provider"] == "Qwen3-VL-Embedding-2B"
        for shot in row["shots"]:
            for query in shot["image_queries"]:
                assert len(query.split()) <= 5 and not banned.intersection(query.casefold().split())
            for query in shot["video_queries"]:
                assert len(query.split()) <= 6 and not banned.intersection(query.casefold().split())


def test_visual_plan_supplies_concrete_video_queries_to_coverage_outline():
    assert importlib.util.find_spec("backend.app.visual_planner") is not None
    from backend.app.visual_planner import ConcreteVisualPlanner, apply_visual_plan_to_outline

    chunks = [{"id": "chunk-1", "text": "tre voli un autobus e due barche per turismo sostenibile"}]
    artifact = ConcreteVisualPlanner(embed=_flat_embedder).plan(chunks, {"beats": [{"id": "chunk-1", "intent": "old", "broll_queries": ["abstract contradiction"]}]})
    outline = apply_visual_plan_to_outline({"beats": [{"id": "chunk-1", "start_seconds": 0, "end_seconds": 4, "intent": "old", "broll_queries": ["abstract contradiction"]}]}, artifact)
    queries = outline["beats"][0]["broll_queries"]
    assert queries[:3] == ["airport passengers boarding plane", "tourist bus with luggage", "passengers boarding ferry"]
    assert "abstract contradiction" not in queries
