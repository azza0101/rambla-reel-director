"""Local JSON Lines worker protocol. stdout is reserved for responses."""
import json
import sys
from script_parser import parse_script
from transcript_align import align_occurrences, propose_take_segments
from edit_selector import choose_latest_complete
from pdf_script import extract_pdf_text
from transcript_align import select_scene

PROTOCOL = 1
ACTIONS = {"ping", "parse_script", "extract_pdf_script", "select_scene", "align", "propose_take_segments", "choose_take", "build_plan", "analyze_shots", "analyze_audio", "pace_plan", "visual_review"}


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
    elif action == "analyze_audio":
        from edit_selector import analyze_audio
        from cache import get_cache, cache_key, write_cache
        from pathlib import Path
        import os
        media=payload['media'];stat=Path(media['path']).stat()
        fingerprint=f"{media['media_id']}:{stat.st_size}:{stat.st_mtime_ns}"
        options={'fps':media.get('fps',25),'duration_frames':media['duration_frames']}
        cache_root=os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache')
        cached=get_cache(cache_root,fingerprint,'audio-rms-v1',options)
        result=cached or analyze_audio(media)
        if not cached and result.get('status')=='ok':
            write_cache(cache_root,cache_key(fingerprint,'audio-rms-v1',options),result)
        result={**result,'cache_hit':cached is not None}
    elif action == "pace_plan":
        from edit_selector import pace_plan
        result=pace_plan(payload['plan'],payload.get('sources',[]),payload.get('audio',{}),payload.get('beats',[]),float(payload['fps']),payload.get('settings'))
    elif action == "visual_review":
        from shot_analyzer import visual_review_media, cluster_faces, VISUAL_REVIEW_VERSION
        from cache import get_cache, cache_key, write_cache
        from pathlib import Path
        import os
        intervals=[]; observations=[]; warnings=[]; hits=0
        media_list=payload.get('media',[])
        for index, media in enumerate(media_list):
            stat=Path(media['path']).stat()
            fingerprint=f"{media['media_id']}:{stat.st_size}:{stat.st_mtime_ns}"
            bounds=[(s['start_frame'],s['end_frame']) for s in payload.get('shots',[]) if s.get('media_id')==media['media_id']]
            def report(current,total):
                sys.stdout.write(json.dumps({'protocol':1,'request_id':request['request_id'],'status':'progress','result':{'current':current,'total':total,'clip_index':index,'clip_total':len(media_list),'name':media.get('name','')}})+'\n');sys.stdout.flush()
            try:
                cache_root=os.environ.get('PREMONTATO_CACHE_DIR','.premontato-cache'); options={'bounds':bounds}
                def reusable(value):
                    return bool(value and not value.get('recognition_error') and not value.get('extraction_errors') and value.get('intervals') and all(s.get('stills') for s in value['intervals']))
                data=get_cache(cache_root,fingerprint,VISUAL_REVIEW_VERSION,options);cached=reusable(data)
                if not cached:
                    data=visual_review_media(media,payload.get('shots',[]),report)
                    if reusable(data): write_cache(cache_root,cache_key(fingerprint,VISUAL_REVIEW_VERSION,options),data)
                hits+=int(cached); intervals.extend(data['intervals']);observations.extend(data['observations'])
                if data.get('recognition_error'): warnings.append(data['recognition_error'])
                if data.get('extraction_errors'): warnings.append(f"{media.get('name','clip')}: {data['extraction_errors']} still non leggibili; ripeti l’analisi")
            except Exception as error: warnings.append(f"Revisione visiva non disponibile per {media.get('name','clip')}: {error}")
            report(1,1)
        faces=cluster_faces(observations)
        result={'intervals':intervals,'faces':faces,'warnings':warnings,'cache_hits':hits,'confirmed':False}
    elif action == "analyze_shots":
        from shot_analyzer import analyze_video, ANALYZER_VERSION
        from cache import get_or_compute
        from pathlib import Path
        import os
        media = payload["media"]
        stat = Path(media["path"]).stat()
        options = {"sample_fps": float(payload.get("sample_fps", 2.0))}
        fingerprint = f"{media['media_id']}:{stat.st_size}:{stat.st_mtime_ns}"
        def report(frame, total):
            sys.stdout.write(json.dumps({"protocol": 1, "request_id": request["request_id"], "status": "progress", "result": {"frame": frame, "total": total}}) + "\n")
            sys.stdout.flush()
        segments, cache_hit = get_or_compute(os.environ.get("PREMONTATO_CACHE_DIR", ".premontato-cache"),
                                              fingerprint, ANALYZER_VERSION, options,
                                              lambda: analyze_video(media, options["sample_fps"], on_progress=report))
        result = {"segments": segments, "cache_hit": cache_hit}
    else:
        from transcript_align import similarity, phrase_candidates, beat_phrases, normalize, complete_beat_candidates
        beats, sources, fps = payload["beats"], payload["sources"], float(payload["fps"])
        decisions, unmatched = [], []
        shot_segments = payload.get("shots", [])
        semantic_hits = {}
        if payload.get("semantic"):
            from transcript_align import semantic_scene_hits
            semantic_hits = semantic_scene_hits(beats, sources, fps)
        from shot_analyzer import speaker_coverage
        previous_shot_size = None
        directions = payload.get("directions") or {}
        markers = directions.get("markers", {}) if directions.get("profile") == "VIDEO COLICHE" else {}
        tension = False
        for beat in beats:
            if beat.get("kind") != "dialogue":
                continue
            marker = markers.get(beat["beat_id"])
            if marker == "tension": tension = True
            elif marker in {"resolution", "free"}: tension = False
            role = "resolution" if marker == "resolution" else "tension" if tension else "free"
            candidates = []
            for source in sources:
                segments = source.get("segments", [])
                hits = (semantic_hits.get((source["take_id"], beat["beat_id"]), []) if payload.get("semantic") else complete_beat_candidates(beat, segments, fps))
                for hit in hits:
                    if hit["start_frame"] < source.get("start_frame", 0) or hit["end_frame"] > source.get("end_frame", source["duration_frames"]):
                        continue
                    if any(d["media_id"] == source["media_id"] and hit["start_frame"] < d.get("matched_end_frame", d["end_frame"]) and d.get("matched_start_frame", d["start_frame"]) < hit["end_frame"] for d in decisions):
                        continue
                    shot = next((item for item in shot_segments if item.get("media_id") == source["media_id"] and item.get("start_frame", 0) <= hit["start_frame"] < item.get("end_frame", 0)), None)
                    candidates.append((source.get("take_index", 0), hit["score"], source, {}, hit, shot))
            if not candidates:
                unmatched.append(beat["beat_id"])
                continue
            # Prefer the latest take which actually contains this line; within that
            # take prefer the strongest phrase hit. Earlier takes remain alternatives.
            best_score = max(row[1] for row in candidates)
            best_coverage = max(row[4].get("coverage", 1.0) for row in candidates)
            credible = [row for row in candidates if row[1] >= best_score - (0.025 if payload.get("semantic") else 0.10) and (payload.get("semantic") or row[4].get("coverage", 1.0) >= best_coverage - 0.08)]
            statuses = {id(row):speaker_coverage(shot_segments,row[2]['media_id'],row[4]['start_frame'],row[4]['end_frame'],beat.get('character','')) for row in credible}
            visible = [row for row in credible if statuses[id(row)]=='visible']
            unknown = [row for row in credible if statuses[id(row)]=='unknown']
            credible = visible or unknown or credible
            classified = [row for row in credible if row[5] and row[5].get("shot_size") in {"wide", "medium", "close"} and row[5].get("confidence", 0) >= 0.55]
            alternating = [row for row in classified if previous_shot_size and row[5]["shot_size"] != previous_shot_size]
            opening = [row for row in classified if row[5]["shot_size"] == "wide"] if not decisions else []
            desired = "close" if role == "tension" else "wide" if role == "resolution" else None
            narrative = [row for row in classified if row[5]["shot_size"] == desired] if desired else []
            pool = narrative or opening or alternating or classified or credible
            latest_index = max(row[0] for row in pool)
            latest = [row for row in pool if row[0] == latest_index]
            _, score, source, segment, hit, shot = max(latest, key=lambda row: (row[4]["start_frame"], row[1]))
            if shot and shot.get("shot_size") in {"wide", "medium", "close"} and shot.get("confidence", 0) >= 0.55:
                previous_shot_size = shot["shot_size"]
            decisions.append({"beat_id": beat["beat_id"], "take_id": source["take_id"], "media_id": source["media_id"],
                              "start_frame": max(source.get("start_frame", 0), hit["start_frame"] - round(0.15 * fps)),
                              "end_frame": min(source.get("end_frame", source["duration_frames"]), hit["end_frame"] + round(0.35 * fps)),
                              "matched_start_frame": hit["start_frame"], "matched_end_frame": hit["end_frame"],
                              "narrative_role": role, "style_satisfied": bool(narrative) if desired else None,
                              "camera_id": source.get("camera_id", "camera_1"), "shot_size": shot.get("shot_size", "unknown") if shot else "unknown",
                              "speaker_coverage": speaker_coverage(shot_segments,source['media_id'],hit['start_frame'],hit['end_frame'],beat.get('character','')),
                              "visible_subjects": shot.get('visible_subjects',[]) if shot else [],
                              "shot_confidence": shot.get("confidence", 0.0) if shot else 0.0,
                              "match_method": hit.get("match_method", "lexical"), "semantic_score": hit.get("semantic_score"),
                              "score": score, "confidence": score, "coverage": hit.get("coverage", 1.0), "matched_text": hit["text"],
                              "rationale_codes": ["LATEST_MATCHING_TAKE", "LOCAL_TRANSCRIPT_MATCH"],
                              "warnings": (["Abbinamento per significato da verificare"] if hit.get("semantic_score", 1.0) < .7 else []) if payload.get("semantic") else (["Battuta parziale: verificare le parole mancanti"] if hit.get("coverage", 1.0) < .75 else []) + (["inquadratura da verificare"] if not shot else []), "alternatives": [
                                  {"take_id": row[2]["take_id"], "media_id": row[2]["media_id"], "start_frame": row[4]["start_frame"],
                                   "end_frame": row[4]["end_frame"], "score": row[1], "coverage": row[4].get("coverage", 0.0),
                                   "speaker_coverage":speaker_coverage(shot_segments,row[2]['media_id'],row[4]['start_frame'],row[4]['end_frame'],beat.get('character','')),
                                   "matched_text": row[4]["text"], "semantic_score": row[4].get("semantic_score"), "match_method": row[4].get("match_method", "lexical"), "shot_size": row[5].get("shot_size", "unknown") if row[5] else "unknown"} for row in candidates if row[2]["take_id"] != source["take_id"] or row[4]["start_frame"] != hit["start_frame"]]})
        for decision in decisions:
            if decision.get("narrative_role") != "free":
                decision["rationale_codes"].append("NARRATIVE_" + decision["narrative_role"].upper())
                if not decision.get("style_satisfied"):
                    decision["rationale_codes"].append("STYLE_COVERAGE_UNAVAILABLE")
                    decision["warnings"].append("Direzione narrativa: copertura richiesta non disponibile tra le alternative affidabili; verifica il campo")
        for left, right in zip(decisions, decisions[1:]):
            if left["media_id"] == right["media_id"] and left["matched_end_frame"] <= right["matched_start_frame"] and left["end_frame"] > right["start_frame"]:
                boundary = (left["matched_end_frame"] + right["matched_start_frame"]) // 2
                left["end_frame"] = min(left["end_frame"], boundary)
                right["start_frame"] = max(right["start_frame"], boundary)
        cursor = 0
        for decision in decisions:
            decision["timeline_start_frame"] = cursor
            cursor += decision["end_frame"] - decision["start_frame"]
        shot_warnings = (["Le scale delle inquadrature sono stime automatiche: verifica le etichette suggerite."]
                         if shot_segments else ["Nessuna inquadratura è stata analizzata: verifica e correggi ogni taglio."])
        partial_count = sum(d.get("coverage", 0) < .75 for d in decisions) if not payload.get("semantic") else 0
        if partial_count:
            shot_warnings.append(f"{partial_count} battute hanno corrispondenza parziale: controlla il parlato trovato e correggi gli intervalli prima della timeline.")
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
