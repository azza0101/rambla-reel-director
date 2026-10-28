"""Local JSON Lines worker protocol. stdout is reserved for responses."""
import json
import sys
from script_parser import parse_script
from transcript_align import align_occurrences, propose_take_segments
from edit_selector import choose_latest_complete
from pdf_script import extract_pdf_text
from transcript_align import select_scene

PROTOCOL = 1
ACTIONS = {"audit_observed_edit", "build_observed_excerpt", "expand_scene_edits", "route_scene_edits", "catalog_preview_frames", "catalog_frames", "render_scene_debug_titles", "catalog_scenes", "ping", "parse_script", "extract_pdf_script", "select_scene", "align", "propose_take_segments", "choose_take", "build_plan", "analyze_shots", "analyze_audio", "pace_plan", "visual_review", "prepare_dialogue", "build_staged"}


def dispatch(request):
    if request.get("protocol") != PROTOCOL or not isinstance(request.get("request_id"), str):
        raise ValueError("Richiesta protocollo non valida")
    action, payload = request.get("action"), request.get("payload", {})
    if action not in ACTIONS:
        raise ValueError("Azione sconosciuta")
    if action == "audit_observed_edit":
        from observed_camera import audit_edit
        result=audit_edit(payload['decisions'],payload.get('covers',[]),payload['event_ids'],payload['fps'])
    elif action == "build_observed_excerpt":
        from observed_editor import build_observed_excerpt
        def report(event):
            sys.stdout.write(json.dumps({'protocol':1,'request_id':request['request_id'],'status':'progress','result':event})+'\n');sys.stdout.flush()
        result=build_observed_excerpt(payload,report)
    elif action == "expand_scene_edits":
        from scene_edit_jobs import expand_missing
        result=expand_missing(payload)
    elif action == "route_scene_edits":
        from scene_edit_jobs import route_scenes
        result=route_scenes(payload)
    elif action == "ping":
        result = {"ready": True}
    elif action == "render_scene_debug_titles":
        from local_audio import render_scene_debug_titles
        result=render_scene_debug_titles(payload)
    elif action == "catalog_preview_frames":
        from scene_visual import preview_catalog_frames
        result=preview_catalog_frames(payload)
    elif action == "catalog_frames":
        from scene_visual import extract_catalog_frames
        result=extract_catalog_frames(payload)
    elif action == "catalog_scenes":
        from scene_catalog import catalog_scenes
        result=catalog_scenes(payload)
    elif action == "prepare_dialogue":
        from staged_dialogue import prepare_dialogue
        result=prepare_dialogue(payload)
    elif action == "build_staged":
        from staged_dialogue import build_staged
        def report(event):
            sys.stdout.write(json.dumps({'protocol':1,'request_id':request['request_id'],'status':'progress','result':event})+'\n');sys.stdout.flush()
        result=build_staged(payload,report)
    elif action == "parse_script":
        result = parse_script(payload.get("text", ""), payload.get("format", "auto"))
    elif action == "extract_pdf_script":
        result = {"text": extract_pdf_text(payload["path"], payload.get("page_start"), payload.get("page_end"))}
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
        from edit_selector import cached_audio
        result=cached_audio(payload['media'])
    elif action == "pace_plan":
        if payload['plan'].get('engine')=='groq_staged_v1':
            import copy
            result=copy.deepcopy(payload['plan']);settings=payload.get('settings') or {}
            result['pacing_settings']=settings
            decisions=result['decisions']
            for d in decisions:
                if d.get('reaction_enabled') is False:
                    d.pop('reaction_before',None)
                    if 'return_to_speaker' in d.get('reaction_overlay',{}):d.pop('reaction_overlay',None)
            for i,d in enumerate(decisions):
                if 'return_to_speaker' not in d.get('reaction_overlay',{}) and i+1<len(decisions) and decisions[i+1].get('reaction_enabled') is False:d.pop('reaction_overlay',None)
            cursor=0
            for d in decisions:
                d['timeline_start_frame']=cursor;cursor+=sum(r['end_frame']-r['start_frame'] for r in d.get('source_ranges',[d]))+sum(a['end_frame']-a['start_frame'] for a in d.get('action_after',[]))
            return {"protocol":PROTOCOL,"request_id":request['request_id'],"status":"ok","result":result}
        from edit_selector import pace_plan
        result=pace_plan(payload['plan'],payload.get('sources',[]),payload.get('audio',{}),payload.get('beats',[]),float(payload['fps']),payload.get('settings'),shots=payload.get('shots',[]))
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
        result = {"segments": segments, "cache_hit": cache_hit, "decode_backend": next((s.get("decode_backend") for s in segments if s.get("decode_backend")), None)}
    else:
        from transcript_align import similarity, phrase_candidates, beat_phrases, normalize, complete_beat_candidates, safe_dialogue_handles
        beats, sources, fps = payload["beats"], payload["sources"], float(payload["fps"])
        decisions, unmatched = [], []
        shot_segments = payload.get("shots", [])
        semantic_hits = {}
        if payload.get("semantic"):
            from transcript_align import semantic_scene_hits
            semantic_hits = semantic_scene_hits(beats, sources, fps)
        from shot_analyzer import speaker_coverage
        automatic = bool(payload.get('active_speaker'))
        asd_stats = {'checked':0,'cache_hits':0,'warnings':[]}
        from automatic_editor import narrative_roles, evaluate_candidates, choose_automatic_pool, context_return_due
        auto_roles = narrative_roles(beats, payload.get('directions') or {}) if automatic else {}
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
            if automatic: role = auto_roles[beat['beat_id']]['role']
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
            if automatic:
                # Automatic framing cannot make a weak transcript match credible.
                # Semantic paraphrases need a score gate, not literal-word overlap.
                best_match=max(row[1] for row in candidates)
                best_words=max(row[4].get('coverage',1.0) for row in candidates)
                quality=[row for row in candidates if (row[1]>=best_match-.12 and (payload.get('semantic') or row[4].get('coverage',1.0)>=best_words-.08)) or speaker_coverage(shot_segments,row[2]['media_id'],row[4]['start_frame'],row[4]['end_frame'],beat.get('character',''))=='visible']
                candidates=quality or [row for row in candidates if row[4].get('coverage',1.0)>=best_words-.08] or candidates
            # Prefer the latest take which actually contains this line; within that
            # take prefer the strongest phrase hit. Earlier takes remain alternatives.
            # The ASR score ranks reliable views of the speaker; it must not remove
            # the only confirmed view before visibility is evaluated.
            evidence = {}
            def speaker_progress(row, done):
                sys.stdout.write(json.dumps({'protocol':1,'request_id':request['request_id'],'status':'progress','result':{'beat':len(decisions)+1,'total':sum(b.get('kind')=='dialogue' for b in beats),'name':row[2].get('name','clip'),'done':done,'checked':asd_stats['checked'],'cache_hits':asd_stats['cache_hits']}})+'\n');sys.stdout.flush()
            if automatic:
                long_exchange=context_return_due(decisions,role,fps,beat.get('character'))
                statuses,evidence=evaluate_candidates(candidates,shot_segments,beat,not decisions,role,asd_stats,speaker_progress,long_exchange)
            else:
                statuses = {id(row):speaker_coverage(shot_segments,row[2]['media_id'],row[4]['start_frame'],row[4]['end_frame'],beat.get('character','')) for row in candidates}
            visible = [row for row in candidates if statuses[id(row)]=='visible']
            unknown = [row for row in candidates if statuses[id(row)]=='unknown']
            scoped = visible or unknown or candidates
            if automatic:
                scoped = choose_automatic_pool(candidates,statuses,role,not decisions,decisions,fps,beat.get('character'))
            best_score = max(row[1] for row in scoped)
            best_coverage = max(row[4].get('coverage',1.0) for row in scoped)
            credible = [row for row in scoped if row[1] >= best_score - (0.025 if payload.get('semantic') else 0.10) and (payload.get('semantic') or row[4].get('coverage',1.0) >= best_coverage - 0.08)]
            classified = [row for row in credible if row[5] and row[5].get("shot_size") in {"wide", "medium", "close"} and row[5].get("confidence", 0) >= 0.55]
            alternating = [row for row in classified if previous_shot_size and row[5]["shot_size"] != previous_shot_size]
            opening = [row for row in classified if row[5]["shot_size"] == "wide"] if not decisions else []
            desired = "close" if role == "tension" else "wide" if role == "resolution" else None
            narrative = [row for row in classified if row[5]["shot_size"] == desired] if desired else []
            pool = choose_automatic_pool(credible,statuses,role,not decisions,decisions,fps,beat.get('character')) if automatic else (narrative or opening or alternating or classified or credible)
            latest_index = max(row[0] for row in pool)
            latest = [row for row in pool if row[0] == latest_index]
            _, score, source, segment, hit, shot = max(latest, key=lambda row: (row[4]["start_frame"], row[1]))
            if shot and shot.get("shot_size") in {"wide", "medium", "close"} and shot.get("confidence", 0) >= 0.55:
                previous_shot_size = shot["shot_size"]
            selected_row = next(row for row in candidates if row[2] is source and row[4] is hit)
            handle_start,handle_end=safe_dialogue_handles(hit,source,fps)
            decisions.append({"beat_id": beat["beat_id"], "take_id": source["take_id"], "media_id": source["media_id"],
                              "start_frame": handle_start,
                              "end_frame": handle_end,
                              "matched_start_frame": hit["start_frame"], "matched_end_frame": hit["end_frame"],
                              "narrative_role": role, "style_satisfied": bool(narrative) if desired else None,
                              "dialogue_character": beat.get("character"), "camera_id": source.get("camera_id", "camera_1"), "shot_size": shot.get("shot_size", "unknown") if shot else "unknown",
                              "speaker_coverage": statuses[id(selected_row)],
                              "speaker_coverage_source": "audio_visual" if id(selected_row) in evidence else "manual" if statuses[id(selected_row)]!='unknown' else "unverified",
                              "active_speaker": evidence.get(id(selected_row)),
                              "visible_subjects": shot.get('visible_subjects',[]) if shot else [],
                              "shot_confidence": shot.get("confidence", 0.0) if shot else 0.0,
                              "match_method": hit.get("match_method", "lexical"), "semantic_score": hit.get("semantic_score"), "opening_checked": hit.get("opening_checked", False),
                              "score": score, "confidence": score, "coverage": hit.get("coverage", 1.0), "matched_text": hit["text"],
                              "rationale_codes": ["LATEST_MATCHING_TAKE", "LOCAL_TRANSCRIPT_MATCH"] + (["MASTER_LONG_EXCHANGE"] if automatic and long_exchange and shot and shot.get("shot_size")=="wide" else []),
                              "warnings": (["Abbinamento per significato da verificare"] if hit.get("semantic_score", 1.0) < .7 else []) if payload.get("semantic") else (["Battuta parziale: verificare le parole mancanti"] if hit.get("coverage", 1.0) < .75 else []) + (["inquadratura da verificare"] if not shot else []), "alternatives": [
                                  {"take_id": row[2]["take_id"], "media_id": row[2]["media_id"], "start_frame": row[4]["start_frame"],
                                   "end_frame": row[4]["end_frame"], "score": row[1], "coverage": row[4].get("coverage", 0.0),
                                   "speaker_coverage":statuses[id(row)],"speaker_coverage_source":"audio_visual" if id(row) in evidence else "manual" if statuses[id(row)]!='unknown' else "unverified","active_speaker":evidence.get(id(row)),
                                   "matched_text": row[4]["text"], "semantic_score": row[4].get("semantic_score"), "match_method": row[4].get("match_method", "lexical"), "shot_size": row[5].get("shot_size", "unknown") if row[5] else "unknown"} for row in candidates if row[2]["take_id"] != source["take_id"] or row[4]["start_frame"] != hit["start_frame"]]})
        for decision in decisions:
            if payload.get("semantic") and decision.get("coverage", 1) < .5:
                decision["warnings"].append("Controlla la completezza: poche parole del copione ritrovate; può essere una parafrasi o una battuta parziale")
            if decision.get("speaker_coverage")=="absent":
                decision["warnings"].append("Parlante fuori campo: nessuna alternativa affidabile con visibilità confermata; verifica la scelta")
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
        if automatic:
            shot_warnings.extend(dict.fromkeys(asd_stats['warnings']))
            shot_warnings.append(f"Parlante verificato su {asd_stats['checked']} campioni audio/video; {asd_stats['cache_hits']} riusati dalla cache. Le stime non sono identificazioni personali.")
        partial_count = sum(d.get("coverage", 0) < .75 for d in decisions) if not payload.get("semantic") else 0
        if partial_count:
            shot_warnings.append(f"{partial_count} battute hanno corrispondenza parziale: controlla il parlato trovato e correggi gli intervalli prima della timeline.")
        result = {"plan_id": payload.get("plan_id", "local-plan"), "scene_id": "scene-1", "fps": fps,
                  "decisions": decisions, "unmatched_beats": unmatched,
                  "warnings": shot_warnings, "active_speaker_summary": asd_stats if automatic else None}
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
