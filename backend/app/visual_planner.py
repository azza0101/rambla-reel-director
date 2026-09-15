"""Translate editorial meaning into concrete, provider-searchable shot plans."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Callable


def _shot(shot_id: str, description: str, image: list[str], video: list[str]) -> dict[str, Any]:
    return {"shot_id": shot_id, "description": description, "image_queries": image, "video_queries": video}


TEMPLATES: tuple[dict[str, Any], ...] = (
    {"id": "transport_chain", "anchors": ("tre voli", "autobus", "barche", "three flights", "boats"), "editorial_function": "contrast", "core_meaning": "the sustainable-travel claim conflicts with a journey requiring several transport legs", "subtext": "the route itself reveals the environmental cost", "visual_mode": "sequence", "avoid": ["generic beach", "generic landscape", "happy tourist portrait"], "shots": [
        _shot("airplane", "passengers boarding a commercial airplane", ["airport passengers boarding plane", "airplane takeoff airport"], ["airport passengers boarding plane", "airplane taking off runway"]),
        _shot("transfer_bus", "tourists load luggage onto a transfer bus", ["tourist bus with luggage", "airport transfer bus tourists"], ["tourist bus with luggage", "airport bus loading luggage"]),
        _shot("passenger_ferry", "travelers board a passenger ferry", ["passengers boarding ferry", "tourist passenger ferry"], ["passengers boarding ferry", "passenger ferry leaving port"]),
    ]},
    {"id": "self_story", "anchors": ("racconto", "noi stessi", "story we tell"), "editorial_function": "irony", "core_meaning": "travelers may tell themselves a flattering sustainability story", "subtext": "self-image can hide the physical footprint of the trip", "visual_mode": "juxtaposition", "avoid": ["generic destination", "empty green landscape", "travel logo"], "shots": [
        _shot("travel_selfie", "tourist takes a polished travel selfie", ["tourist taking travel selfie", "vacation selfie phone"], ["tourist filming travel selfie", "vacation influencer phone video"]),
        _shot("airport_reality", "busy airport departure gate behind travelers", ["busy airport departure gate", "airport passengers waiting gate"], ["crowded airport departure gate", "passengers waiting airport terminal"]),
    ]},
    {"id": "green_label", "anchors": ("etichetta verde", "green label", "appicc", "eco label"), "editorial_function": "irony", "core_meaning": "a green label can be applied without changing the underlying practice", "subtext": "branding is not evidence", "visual_mode": "juxtaposition", "avoid": ["generic beach", "green forest", "happy tourists"], "shots": [
        _shot("eco_sticker", "eco sticker attached to a hotel or travel sign", ["eco sticker hotel sign", "green travel label"], ["placing eco sticker sign", "eco label hotel entrance"]),
        _shot("marketing_badge", "sustainable tourism badge on advertising", ["sustainable tourism badge", "eco tourism advertisement"], ["green tourism marketing sign", "eco hotel advertising"]),
    ]},
    {"id": "local_eco_ideal", "anchors": ("strutture locali", "zero plastica", "guide del posto", "orto", "plastic free"), "editorial_function": "example", "core_meaning": "the ideal is locally run, low-waste travel that supports local work", "subtext": "specific operations matter more than labels", "visual_mode": "sequence", "avoid": ["luxury resort pool", "generic beach", "corporate travel logo"], "shots": [
        _shot("local_lodge", "small locally owned eco lodge", ["local eco lodge", "small eco hotel"], ["local eco lodge tour", "small sustainable hotel"]),
        _shot("local_guide", "local guide leads a small group", ["local tour guide group", "local guide travelers"], ["local guide leading tourists", "small group local tour"]),
        _shot("plastic_free", "refill station with reusable bottles", ["hotel water refill station", "plastic free hotel bottles"], ["travelers using refill station", "hotel plastic free bottles"]),
    ]},
    {"id": "consenting_chickens", "anchors": ("galline", "consenzienti", "chickens"), "editorial_function": "irony", "core_meaning": "the perfect ethical-travel checklist becomes deliberately absurd", "subtext": "the chicken detail punctures performative perfection", "visual_mode": "single", "avoid": ["cooked chicken", "industrial poultry", "generic farm logo"], "shots": [
        _shot("free_range_chickens", "free-range chickens wander through a garden", ["free range chickens garden", "chickens walking farmyard"], ["free range chickens walking", "chickens roaming garden"]),
    ]},
    {"id": "elephant_sanctuary", "anchors": ("thailandia", "centro elefanti", "elefanti", "cavalcate", "elephant"), "editorial_function": "example", "core_meaning": "a Thailand elephant center looked ethical until its claims required verification", "subtext": "appearance and slogans are not proof of animal welfare", "visual_mode": "juxtaposition", "avoid": ["elephant riding", "circus performance", "unrelated safari"], "shots": [
        _shot("elephant_sanctuary", "Asian elephants walk freely at a Thailand sanctuary", ["ethical elephant sanctuary thailand", "elephants walking sanctuary thailand"], ["elephants roaming sanctuary thailand", "ethical elephant sanctuary tour"]),
        _shot("no_riding", "visitors observe elephants without riding", ["elephant sanctuary no riding", "tourists observing elephants thailand"], ["visitors observing elephants sanctuary", "elephant sanctuary without riding"]),
    ]},
    {"id": "tourism_accountability", "anchors": ("possedeva", "pagati", "lavoratori", "finissero i soldi", "worker pay", "ownership"), "editorial_function": "explanation", "core_meaning": "ethical claims require answers about ownership, worker pay and where tourist money goes", "subtext": "silence from the operator is evidence in itself", "visual_mode": "sequence", "avoid": ["generic office handshake", "happy tourist stock", "unrelated money pile"], "shots": [
        _shot("hotel_workers", "hotel workers in Thailand at work", ["hotel workers thailand", "tourism workers thailand"], ["hotel workers working thailand", "tourism staff thailand hotel"]),
        _shot("local_owner", "small hotel owner reviews business records", ["small hotel owner paperwork", "hotel owner accounting desk"], ["hotel owner reviewing accounts", "small business owner paperwork"]),
        _shot("tourism_money", "local tourism business handles guest payment", ["local tourism business payment", "hotel reception guest payment"], ["guest paying hotel reception", "local tourism business transaction"]),
    ]},
    {"id": "eco_sign_basil", "anchors": ("basilico", "balcone", "rigenerazione urbana", "eco sull", "ecolo", "insegna", "half dead basil"), "editorial_function": "irony", "core_meaning": "an eco sign and a dying basil plant do not make a regenerative project", "subtext": "tiny cosmetic gestures are being inflated into sustainability claims", "visual_mode": "juxtaposition", "avoid": ["lush herb garden", "perfect green balcony", "generic skyline"], "shots": [
        _shot("eco_sign", "eco sign displayed at a building entrance", ["eco hotel sign", "green building sign"], ["eco sign building entrance", "hotel green sign"]),
        _shot("dying_basil", "half-dead basil plant on an apartment balcony", ["dying basil plant balcony", "wilted basil balcony pot"], ["wilted basil plant balcony", "dying potted basil closeup"]),
    ]},
    {"id": "long_haul_flight", "anchors": ("intercontinentale", "bangkok", "coscienza", "long haul"), "editorial_function": "contrast", "core_meaning": "calling a long-haul flight to Bangkok eco-friendly does not remove its emissions", "subtext": "the claim comforts the traveler more than the planet", "visual_mode": "juxtaposition", "avoid": ["generic Bangkok temple", "tropical beach", "airline logo"], "shots": [
        _shot("departure_board", "airport departure board shows Bangkok flight", ["airport departure board bangkok", "bangkok flight airport gate"], ["bangkok departure board airport", "passengers boarding bangkok flight"]),
        _shot("long_haul_plane", "widebody airplane departs an international airport", ["widebody airplane takeoff", "long haul airplane runway"], ["widebody airplane taking off", "long haul flight runway"]),
        _shot("aviation_emissions", "aviation emissions chart or aircraft exhaust", ["aviation carbon emissions chart", "airplane exhaust runway"], ["airplane exhaust takeoff", "aviation emissions animation"]),
    ]},
    {"id": "harm_reduction", "anchors": ("compromesso", "ridurre il danno", "reduce harm", "scelte"), "editorial_function": "value", "core_meaning": "responsible travel means choosing where to accept tradeoffs and reduce harm", "subtext": "the goal is better decisions rather than impossible purity", "visual_mode": "sequence", "avoid": ["generic moral crossroads", "abstract balance scale", "travel quote graphic"], "shots": [
        _shot("train_choice", "traveler boards a train instead of flying", ["traveler boarding train luggage", "passenger train station luggage"], ["traveler boarding train luggage", "passenger choosing train travel"]),
        _shot("refill_choice", "traveler refills a reusable water bottle", ["traveler refill water bottle", "reusable bottle travel station"], ["traveler refilling water bottle", "reusable bottle travel"]),
    ]},
    {"id": "exploitation_overtourism", "anchors": ("sfrutta", "persone", "animali", "impoverisce", "territori", "overtourism"), "editorial_function": "value", "core_meaning": "travel should not exploit workers or animals or overwhelm residents", "subtext": "local livelihoods and living conditions are the ethical test", "visual_mode": "sequence", "avoid": ["generic smiling tourists", "empty landmark", "luxury resort advertisement"], "shots": [
        _shot("local_workers", "local hospitality workers serve visitors", ["local hospitality workers", "hotel staff working"], ["local hospitality workers working", "hotel staff serving guests"]),
        _shot("overtourism", "residents move through a crowded tourist street", ["overtourism crowded street residents", "tourists crowd local neighborhood"], ["crowded tourist street residents", "overtourism local neighborhood"]),
        _shot("animal_welfare", "sanctuary staff care for rescued animals", ["animal sanctuary staff care", "rescued animals sanctuary workers"], ["sanctuary staff caring animals", "rescued animal welfare center"]),
    ]},
    {"id": "custom_trip_cta", "anchors": ("dm", "costruiamo insieme", "su misura", "preconfezionati", "commerciali", "custom trip"), "editorial_function": "CTA", "core_meaning": "the viewer is invited to plan a personal responsible trip with an advisor", "subtext": "the service is collaborative rather than prepackaged", "visual_mode": "sequence", "avoid": ["generic booking website", "airline logo", "mass tourism package"], "shots": [
        _shot("travel_advisor", "travel advisor and client plan a route on a map", ["travel advisor client map", "trip planning map meeting"], ["travel advisor planning client trip", "client planning route map"]),
        _shot("direct_message", "person sends a direct message about a trip", ["travel message smartphone", "person texting travel advisor"], ["sending travel message phone", "texting travel advisor"]),
    ]},
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.casefold())).strip()


def _cosine(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def _global_topic(chunks: list[dict[str, Any]]) -> str:
    text = " ".join(str(row.get("text") or "") for row in chunks).casefold()
    if "turismo" in text and any(word in text for word in ("sostenib", "etico", "responsab")):
        return "sustainable tourism, ethical travel and greenwashing"
    return " ".join(str(row.get("text") or "") for row in chunks[:3])[:240]


class ConcreteVisualPlanner:
    def __init__(self, *, embed: Callable[[list[Any]], list[list[float]]] | None = None):
        self.embed = embed

    def plan(self, chunks: list[dict[str, Any]], outline: dict[str, Any], *, event_callback: Any = None) -> dict[str, Any]:
        topic = _global_topic(chunks)
        output: dict[str, Any] = {"schema_version": "concrete-visual-plan-0.1", "global_topic": topic, "chunks": {}}
        descriptions = [f"{row['core_meaning']}. Visible shots: " + "; ".join(shot["description"] for shot in row["shots"]) for row in TEMPLATES]
        for index, chunk in enumerate(chunks):
            current = str(chunk.get("text") or "").strip()
            previous = str(chunks[index - 1].get("text") or "") if index else ""
            following = str(chunks[index + 1].get("text") or "") if index + 1 < len(chunks) else ""
            context = " ".join(part for part in (previous, current, following) if part)
            normalized_current, normalized_context = _normalize(current), _normalize(context)
            is_short_abstract = len(normalized_current.split()) <= 2
            if is_short_abstract and index and output["chunks"]:
                template = next(row for row in TEMPLATES if row["id"] == output["chunks"][str(chunks[index - 1]["id"])]["template_id"])
                qwen_score = output["chunks"][str(chunks[index - 1]["id"])]["planning_score"]
            else:
                semantic_scores = [0.0] * len(TEMPLATES)
                if self.embed is not None:
                    vectors = self.embed([f"Global topic: {topic}. Current phrase: {current}. Nearby context: {context}", *descriptions])
                    semantic_scores = [_cosine(vectors[0], vector) for vector in vectors[1:]]
                ranked = []
                for template_index, template_row in enumerate(TEMPLATES):
                    direct = sum(1 for anchor in template_row["anchors"] if _normalize(anchor) in normalized_current)
                    nearby = sum(1 for anchor in template_row["anchors"] if _normalize(anchor) in normalized_context)
                    score = direct * 5.0 + nearby * 0.75 + semantic_scores[template_index]
                    ranked.append((score, direct, semantic_scores[template_index], template_row))
                _score, _direct, qwen_score, template = max(ranked, key=lambda item: (item[0], item[1], item[2], item[3]["id"]))
            row = {key: value for key, value in template.items() if key not in {"id", "anchors"}}
            row.update({
                "chunk_id": str(chunk["id"]), "template_id": template["id"], "chunk_text": current,
                "local_context": context, "global_topic": topic,
                "editorial_function": "pause" if normalized_current == "silenzio" else row["editorial_function"],
                "planning_score": round(float(qwen_score), 4),
                "planner_provider": "Qwen3-VL-Embedding-2B" if self.embed is not None else "deterministic-template-fallback",
            })
            output["chunks"][str(chunk["id"])] = row
            if event_callback:
                event_callback("visual_planning", 100.0 * (index + 1) / max(1, len(chunks)), f"Concrete visual plan {index + 1}/{len(chunks)}", chunk_id=str(chunk["id"]), editorial_function=row["editorial_function"], core_meaning=row["core_meaning"], visual_mode=row["visual_mode"], shots=[{"shot_id": shot["shot_id"], "description": shot["description"], "image_queries": shot["image_queries"], "video_queries": shot["video_queries"]} for shot in row["shots"]], avoid=row["avoid"], planner_provider=row["planner_provider"], planning_score=row["planning_score"])
        signature_payload = {"chunks": chunks, "outline": outline, "global_topic": topic, "schema": output["schema_version"]}
        output["input_signature"] = hashlib.sha256(json.dumps(signature_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return output


def visual_plan_signature(chunks: list[dict[str, Any]], outline: dict[str, Any]) -> str:
    probe = {"chunks": chunks, "outline": outline, "global_topic": _global_topic(chunks), "schema": "concrete-visual-plan-0.1"}
    return hashlib.sha256(json.dumps(probe, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_or_create_visual_plan(chunks: list[dict[str, Any]], outline: dict[str, Any], output_dir: Path, *, embed: Callable[[list[Any]], list[list[float]]], event_callback: Any = None) -> dict[str, Any]:
    path = output_dir / "visual-plan.json"
    expected = visual_plan_signature(chunks, outline)
    if path.is_file():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("input_signature") == expected and set(cached.get("chunks", {})) == {str(row["id"]) for row in chunks}:
                if event_callback: event_callback("visual_planning", 100.0, "Concrete visual plan reused", chunks=len(chunks), cache_reused=True)
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    result = ConcreteVisualPlanner(embed=embed).plan(chunks, outline, event_callback=event_callback)
    _write_json(path, result)
    return result


def apply_visual_plan_to_outline(outline: dict[str, Any], visual_plan: dict[str, Any]) -> dict[str, Any]:
    enriched = {**outline, "beats": []}
    for beat in outline.get("beats", []):
        row = dict(beat)
        plan = visual_plan.get("chunks", {}).get(str(beat.get("id")))
        if plan:
            shots = plan.get("shots", [])
            queries = [shot["video_queries"][0] for shot in shots if shot.get("video_queries")]
            queries.extend(query for shot in shots for query in shot.get("video_queries", [])[1:])
            row.update({"intent": plan["core_meaning"], "broll_queries": queries, "visual_plan": {"editorial_function": plan["editorial_function"], "visual_mode": plan["visual_mode"], "avoid": plan["avoid"], "template_id": plan["template_id"]}})
        enriched["beats"].append(row)
    return enriched


def merge_visual_diagnostics(artifact: dict[str, Any], kind: str, rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    merged = json.loads(json.dumps(artifact))
    for chunk_id, diagnostics in rows.items():
        if chunk_id in merged.get("chunks", {}):
            merged["chunks"][chunk_id][f"{kind}_search"] = diagnostics
    return merged


def persist_visual_plan(path: Path, artifact: dict[str, Any]) -> None:
    _write_json(path, artifact)
