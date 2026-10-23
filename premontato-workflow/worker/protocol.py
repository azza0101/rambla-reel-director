"""Local JSON Lines worker protocol. stdout is reserved for responses."""
import json
import sys
from script_parser import parse_script
from transcript_align import align_occurrences, propose_take_segments
from edit_selector import choose_latest_complete
from pdf_script import extract_pdf_text
from transcript_align import select_scene

PROTOCOL = 1
ACTIONS = {"ping", "parse_script", "extract_pdf_script", "select_scene", "align", "propose_take_segments", "choose_take", "build_plan", "analyze_shots"}


def dispatch(request):
    if request.get("protocol") != PROTOCOL or not isinstance(request.get("request_id"), str):
        raise ValueError("Richiesta protocollo non valida")
    action, payload = request.get("action"), request.get("payload", {})
    if action not in ACTIONS:
        raise ValueError("Azione sconosciuta")
    if action == "ping":
        result = {"ready": True}
    elif action == "parse_script":
        result = parse_script(payload.get("text", ""), payload.get("format", "auto"))
    elif action == "extract_pdf_script":
        result = {"text": extract_pdf_text(payload["path"])}
    elif action == "select_scene":
        result = select_scene(payload["scenes"], payload.get("transcript", []))
    elif action == "align":
        result = align_occurrences(payload["beats"], payload["transcript"], payload.get("options"))
    elif action == "propose_take_segments":
        if payload.get("beats"):
            from transcript_align import propose_take_segments_for_beats
            result = propose_take_segments_for_beats(payload["media"], payload["beats"], payload["transcript"], payload["fps"])
        else:
            result = propose_take_segments(payload["media"], payload["transcript"], payload["fps"])
    elif action == "choose_take":
        result = choose_latest_complete(payload["takes"])
    elif action == "analyze_shots":
        from shot_analyzer import analyze_video
        from cache import get_or_compute
        from pathlib import Path
        import os
        media = payload["media"]
        stat = Path(media["path"]).stat()
        options = {"sample_fps": float(payload.get("sample_fps", 2.0))}
        fingerprint = f"{media['media_id']}:{stat.st_size}:{stat.st_mtime_ns}"
        segments, cache_hit = get_or_compute(os.environ.get("PREMONTATO_CACHE_DIR", ".premontato-cache"),
                                              fingerprint, "haar-hist-v4-face-height-2fps-opencv4", options,
                                              lambda: analyze_video(media, options["sample_fps"]))
        result = {"segments": segments, "cache_hit": cache_hit}
    else:
        from transcript_align import similarity, phrase_candidates, beat_phrases, normalize
        beats, sources, fps = payload["beats"], payload["sources"], float(payload["fps"])
        decisions, unmatched = [], []
        shot_segments = payload.get("shots", [])
        previous_shot_size = None
        for beat in beats:
            if beat.get("kind") != "dialogue":
                continue
            candidates = []
            for source in sources:
                for segment in source.get("segments", []):
                    hits = []
                    for phrase in beat_phrases(beat):
                        hits.extend(phrase_candidates({**beat, "text": phrase}, segment))
                    # A script beat can contain several sentences. Keep the single
                    # strongest clause in each Resolve speaker turn, not every clause
                    # as a separate timeline insert.
                    if hits:
                        hit = max(hits, key=lambda row: (row["score"], -row["end_frame"] + row["start_frame"]))
                        shot = next((item for item in shot_segments if item.get("media_id") == source["media_id"] and item.get("start_frame", 0) <= hit["start_frame"] < item.get("end_frame", 0)), None)
                        candidates.append((source.get("take_index", 0), hit["score"], source, segment, hit, shot))
            if not candidates:
                unmatched.append(beat["beat_id"])
                continue
            # Prefer the latest take which actually contains this line; within that
            # take prefer the strongest phrase hit. Earlier takes remain alternatives.
            best_score = max(row[1] for row in candidates)
            credible = [row for row in candidates if row[1] >= best_score - 0.10]
            classified = [row for row in credible if row[5] and row[5].get("shot_size") in {"wide", "medium", "close"} and row[5].get("confidence", 0) >= 0.55]
            alternating = [row for row in classified if previous_shot_size and row[5]["shot_size"] != previous_shot_size]
            pool = alternating or classified or credible
            latest_index = max(row[0] for row in pool)
            latest = [row for row in pool if row[0] == latest_index]
            _, score, source, segment, hit, shot = max(latest, key=lambda row: (row[1], len(normalize(row[4].get("text", "")).split())))
            if shot and shot.get("shot_size") in {"wide", "medium", "close"} and shot.get("confidence", 0) >= 0.55:
                previous_shot_size = shot["shot_size"]
            decisions.append({"beat_id": beat["beat_id"], "take_id": source["take_id"], "media_id": source["media_id"],
                              "start_frame": max(source.get("start_frame", 0), hit["start_frame"] - round(0.15 * fps)),
                              "end_frame": min(source.get("end_frame", source["duration_frames"]), hit["end_frame"] + round(0.35 * fps)),
                              "camera_id": source.get("camera_id", "camera_1"), "shot_size": shot.get("shot_size", "unknown") if shot else "unknown",
                              "shot_confidence": shot.get("confidence", 0.0) if shot else 0.0,
                              "score": score, "confidence": score, "matched_text": hit["text"],
                              "rationale_codes": ["LATEST_MATCHING_TAKE", "LOCAL_TRANSCRIPT_MATCH"],
                              "warnings": ["inquadratura da verificare"], "alternatives": [
                                  {"take_id": row[2]["take_id"], "media_id": row[2]["media_id"], "start_frame": row[4]["start_frame"],
                                   "end_frame": row[4]["end_frame"], "score": row[1]} for row in candidates if row[2]["take_id"] != source["take_id"]]})
        cursor = 0
        for decision in decisions:
            decision["timeline_start_frame"] = cursor
            cursor += decision["end_frame"] - decision["start_frame"]
        shot_warnings = (["Le scale delle inquadrature sono stime automatiche: verifica le etichette suggerite."]
                         if shot_segments else ["Nessuna inquadratura è stata analizzata: verifica e correggi ogni taglio."])
        result = {"plan_id": payload.get("plan_id", "local-plan"), "scene_id": "scene-1", "fps": fps,
                  "decisions": decisions, "unmatched_beats": unmatched,
                  "warnings": shot_warnings}
    return {"protocol": PROTOCOL, "request_id": request["request_id"], "status": "ok", "result": result}


def main():
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = dispatch(request)
        except Exception as error:
            response = {"protocol": PROTOCOL, "request_id": request.get("request_id") if isinstance(locals().get("request"), dict) else None,
                        "status": "error", "error": {"code": "INVALID_REQUEST", "message": str(error)}}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
