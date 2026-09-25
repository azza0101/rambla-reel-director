def _beat(text, core, *, avoid=None):
    return {
        "id": "b1",
        "original_text": text,
        "core_meaning": core,
        "subtext": "",
        "avoid": list(avoid or []),
    }


def _shot(description, query):
    return {
        "shot_id": "s1",
        "description": description,
        "image_queries": [query],
        "video_queries": [query],
    }


def test_unsupported_generic_laptop_shot_is_demoted_by_spoken_context():
    from backend.app.editorial_relevance import build_retrieval_spec

    beat = _beat(
        "Poi ho chiesto chi possedeva la struttura, quanto venissero pagati i lavoratori, dove finissero i soldi e come davvero venissero trattati gli elefanti. Silenzio.",
        "Le domande concrete sulla struttura e sugli elefanti non ricevono risposta",
    )
    shot = _shot("Traveler taking notes on a laptop", "traveler taking notes laptop")
    spec = build_retrieval_spec(beat, shot, "video")

    assert spec["generic_shot_demoted"] is True
    assert any("laptop" in value.casefold() for value in spec["negatives"])
    assert any("silence" in value.casefold() for value in spec["queries"])
    assert any("elephant" in value.casefold() for value in spec["queries"])
    assert "laptop" not in spec["positive"].casefold()


def test_compromise_beat_does_not_fall_back_to_generic_hotel_planning():
    from backend.app.editorial_relevance import build_retrieval_spec

    beat = _beat(
        "Ma poi scalavo anche solo mezzo centimetro e usciva sempre un compromesso, piccolo, grande, medio, formato famiglia, ma usciva.",
        "La promessa sostenibile si incrina appena si guardano i compromessi reali",
        avoid=["generic travel planning"],
    )
    shot = _shot("Traveler comparing accommodation options", "traveler comparing accommodation options")
    spec = build_retrieval_spec(beat, shot, "image")

    assert spec["generic_shot_demoted"] is True
    assert any("greenwashing" in value.casefold() or "eco label" in value.casefold() for value in spec["queries"])
    assert any("hotel room" in value.casefold() or "laptop" in value.casefold() for value in spec["negatives"])


def test_basil_context_generates_literal_wilted_basil_fallbacks():
    from backend.app.editorial_relevance import build_retrieval_spec

    beat = _beat(
        "Detta terra terra, non basta scrivere eco sull'insegna, sennò pure io con la piantina di basilico mezzo morto sul balcone divento un progetto di rigenerazione urbana.",
        "Un'etichetta eco non rende automaticamente sostenibile qualcosa",
    )
    shot = _shot("Wilted basil plant on balcony", "wilted basil balcony")
    spec = build_retrieval_spec(beat, shot, "image")

    assert spec["generic_shot_demoted"] is False
    assert spec["queries"] == ["wilted basil balcony"]
    assert spec["visual_target"] == "Wilted basil plant on balcony"


def test_encoded_intent_round_trips_machine_actionable_negatives():
    from backend.app.editorial_relevance import encode_retrieval_intent, decode_retrieval_intent

    beat = _beat("Silenzio.", "Nessuno risponde", avoid=["text slides"])
    shot = _shot("Awkward silence between people", "awkward silence people")
    decoded = decode_retrieval_intent(encode_retrieval_intent(beat, shot))

    assert "silence" in decoded["positive"].casefold() or "silenzio" in decoded["context"].casefold()
    assert any("text slides" in value.casefold() for value in decoded["negatives"])


def test_ranker_rejects_candidate_that_matches_negative_better_than_editorial_target():
    from backend.app.editorial_relevance import encode_retrieval_intent
    from backend.app.retrieval_quality import QualityRanker

    beat = _beat("Silenzio.", "Nessuno risponde")
    shot = _shot("Awkward silence between people", "awkward silence people")
    intent = encode_retrieval_intent(beat, shot)

    class Visual:
        def rank(self, query, rows):
            q = query.casefold()
            if "laptop" in q or "tutorial" in q:
                score = 0.78
            elif "awkward silence" in q or "nessuno risponde" in q:
                score = 0.52
            else:
                score = 0.48
            return [{**row, "embedding_score": score} for row in rows]

    asset = {
        "id": "pexels:1",
        "kind": "image",
        "provider": "pexels",
        "title": "Person using laptop in hotel room",
        "description": "Typing notes on a laptop",
        "query": "awkward silence people",
    }
    ranked = QualityRanker(Visual()).rank(intent, [asset])

    assert ranked[0]["quality_state"] == "rejected"
    assert any("negative" in reason for reason in ranked[0]["quality_reasons"])
