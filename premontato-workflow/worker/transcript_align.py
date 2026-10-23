"""Transcript matching keeps every occurrence; repeated lines are not deduplicated."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE).split())


def similarity(a, b):
    aa, bb = normalize(a), normalize(b)
    if not aa or not bb:
        return 0.0
    at, bt = set(aa.split()), set(bb.split())
    return len(at & bt) / max(1, len(at | bt))


_STOPWORDS = {"a", "ad", "al", "alla", "alle", "che", "chi", "ci", "con", "da", "dal", "de", "del", "della", "di", "e", "ed", "è", "il", "in", "io", "la", "le", "lo", "ma", "mi", "ne", "nel", "nella", "no", "non", "o", "per", "più", "poi", "qualche", "se", "si", "sì", "sono", "su", "ti", "tu", "un", "una", "uno", "va", "vabbè", "vi"}


def _stem_token(token):
    for suffix in ("ando", "endo", "ato", "ata", "ati", "ate", "uto", "uta", "uti", "ute", "oso", "osa", "osi", "ose", "mente", "zione", "are", "ere", "ire", "i", "e", "a", "o"):
        if len(token) - len(suffix) >= 4 and token.endswith(suffix):
            return token[:-len(suffix)]
    return token


def _same_content(left, right):
    a, b = _stem_token(left), _stem_token(right)
    return a == b or (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a)))


def phrase_candidates(beat, segment, fallback_threshold=0.35):
    """Find tight, word-timed matches inside a Resolve speaker turn."""
    beat_tokens = normalize(beat.get("text", "")).split()
    if not beat_tokens:
        return []
    words = segment.get("words") or []
    if not words:
        score = similarity(beat.get("text", ""), segment.get("text", ""))
        return [{"score": score, "start_frame": segment["start_frame"], "end_frame": segment["end_frame"], "text": segment.get("text", "")} ] if score >= fallback_threshold else []
    tokens = [normalize(word.get("text", "")).split() or [""] for word in words]
    tokens = [row[0] for row in tokens]
    target_content = [_stem_token(token) for token in beat_tokens if token not in _STOPWORDS]
    if not target_content:
        target_content = beat_tokens
    target_size = len(target_content)
    # Include ASR insertions/deletions while keeping the scan linear in the turn length.
    min_size, max_size = max(1, target_size - 1), min(len(words), target_size + 3)
    results = []
    for size in range(min_size, max_size + 1):
        for start in range(0, len(words) - size + 1):
            end = start + size
            observed = [token for token in tokens[start:end] if token]
            if not observed:
                continue
            observed_content = [_stem_token(token) for token in observed if token not in _STOPWORDS]
            if not observed_content:
                observed_content = observed
            # Content overlap prevents common function words from producing matches;
            # sequence similarity allows minor ASR substitutions and inflections.
            common = {target for target in target_content if any(_same_content(target, observed) for observed in observed_content)}
            if len(target_content) >= 2 and len(common) < 2:
                continue
            if len(target_content) == 1 and (len(target_content[0]) < 4 or target_content[0] not in common):
                continue
            overlap = len(common) / max(1, len(set(target_content) | set(observed_content)))
            sequence = SequenceMatcher(None, target_content, observed_content, autojunk=False).ratio()
            score = max(overlap, sequence * 0.75)
            if score >= fallback_threshold:
                results.append({"score": score, "start_frame": words[start]["start_frame"],
                                "end_frame": words[end - 1]["end_frame"],
                                "text": " ".join(word.get("text", "") for word in words[start:end])})
    # Keep the strongest non-overlapping phrase hit from each speaker turn.
    if results:
        top_score = max(row["score"] for row in results)
        # ASR may extend a hit with adjacent words. Keep a near-best shorter phrase
        # to avoid turning a correct dialogue match into a whole-speaker-turn cut.
        results = [row for row in results if row["score"] >= top_score - 0.08]
    results.sort(key=lambda row: (row["end_frame"] - row["start_frame"], -row["score"]))
    kept = []
    for result in results:
        if not any(result["start_frame"] < other["end_frame"] and other["start_frame"] < result["end_frame"] for other in kept):
            kept.append(result)
    return kept


def beat_phrases(beat):
    """Extract clauses from long script beats so a short ASR turn can match a clause."""
    text = beat.get("text", "")
    parts = re.split(r"(?<=[.!?])\s+|[,;:]\s*|…", text)
    phrases = [part.strip() for part in parts if len([token for token in normalize(part).split() if token not in _STOPWORDS]) >= 2 or
               (len(normalize(part).split()) >= 3 and len([token for token in normalize(part).split() if token not in _STOPWORDS]) == 1)]
    return phrases or [text]


def select_scene(scenes, transcript_segments, minimum_similarity=0.42, minimum_margin=0.08):
    """Identify one script scene from its spoken lines; abstain on weak/generic matches."""
    transcript = []
    for segment in transcript_segments:
        text = segment.get("text", "")
        # Resolve often groups an entire speaker turn into one segment. Split it
        # into sentence/phrase candidates so separate screenplay beats can match.
        parts = re.split(r"(?<=[.!?])\s+|,\s+", text)
        for part_index, part in enumerate(parts):
            if normalize(part) and normalize(part) != "":
                transcript.append({**segment, "segment_id": f"{segment.get('segment_id', 's')}:{part_index}", "text": part})
    ranked = []
    for scene in scenes:
        beats = []
        for beat in scene.get("beats", []):
            if beat.get("kind") != "dialogue":
                continue
            for part in re.split(r"(?<=[.!?])\s+|,\s+|…", beat.get("text", "")):
                if len(normalize(part).split()) >= 3:
                    beats.append({**beat, "text": part})
        candidates = sorted(
            ((similarity(beat.get("text", ""), segment.get("text", "")), beat_index, segment_index)
             for beat_index, beat in enumerate(beats)
             for segment_index, segment in enumerate(transcript)
             if similarity(beat.get("text", ""), segment.get("text", "")) >= minimum_similarity),
            reverse=True,
        )
        used_beats, used_segments, matches = set(), set(), []
        for score, beat_index, segment_index in candidates:
            if beat_index in used_beats or segment_index in used_segments:
                continue
            used_beats.add(beat_index); used_segments.add(segment_index); matches.append(score)
        count = len(matches)
        coverage = count / len(beats) if beats else 0.0
        mean_score = sum(matches) / count if count else 0.0
        ranked.append((count, coverage, mean_score, scene))
    ranked.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
    if not ranked or ranked[0][0] < 2:
        return {"scene": None, "confidence": 0.0, "candidates": [
            {"scene_id": row[3].get("scene_id"), "heading": row[3].get("heading"), "matched_lines": row[0],
             "coverage": row[1], "mean_similarity": row[2]} for row in ranked[:3]
        ]}
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else (0, 0.0, 0.0, None)
    confident = best[2] >= 0.48 and (best[0] > runner_up[0] or best[2] - runner_up[2] >= minimum_margin)
    evidence = min(1.0, best[0] / 5.0)
    separation = max(0.0, (best[0] - runner_up[0]) / max(1, best[0]))
    confidence = min(1.0, best[2] * 0.55 + evidence * 0.25 + separation * 0.20)
    return {"scene": best[3] if confident else None,
            "confidence": confidence if confident else 0.0,
            "candidates": [{"scene_id": row[3].get("scene_id"), "heading": row[3].get("heading"),
                            "matched_lines": row[0], "coverage": row[1], "mean_similarity": row[2]}
                           for row in ranked[:3]],
            "ambiguous": not confident}


def align_occurrences(beats, transcript_segments, options=None):
    matches, unmatched_beats, unmatched_segments = [], [], set(range(len(transcript_segments)))
    threshold = (options or {}).get("minimum_similarity", 0.35)
    for beat in beats:
        candidates = [(similarity(beat.get("text", ""), seg.get("text", "")), i, seg)
                      for i, seg in enumerate(transcript_segments)]
        candidates = [(score, i, seg) for score, i, seg in candidates if score >= threshold]
        if not candidates:
            unmatched_beats.append(beat["beat_id"])
            continue
        # Keep all transcript occurrences for this line, to expose retakes and repeated intent.
        for score, i, seg in candidates:
            matches.append({"beat_id": beat["beat_id"], "media_id": seg.get("media_id"),
                            "start_frame": seg["start_frame"], "end_frame": seg["end_frame"],
                            "similarity": score, "confidence": score, "segment_id": seg.get("segment_id")})
            unmatched_segments.discard(i)
    return {"matches": matches, "unmatched_beats": unmatched_beats,
            "unmatched_segments": [transcript_segments[i].get("segment_id") for i in sorted(unmatched_segments)]}


def propose_take_segments(media, transcript, fps, gap_seconds=2.5):
    if fps <= 0:
        raise ValueError("frame rate must be positive")
    items = sorted(transcript, key=lambda item: item["start_frame"])
    if not items:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    runs, run = [], [items[0]]
    for item in items[1:]:
        gap = item["start_frame"] - run[-1]["end_frame"]
        if gap > gap_seconds * fps and normalize(run[-1].get("text", "")) != normalize(item.get("text", "")):
            runs.append(run)
            run = [item]
        else:
            run.append(item)
    runs.append(run)
    if len(runs) == 1:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    result = []
    for index, current in enumerate(runs):
        start = 0 if index == 0 else (runs[index - 1][-1]["end_frame"] + current[0]["start_frame"]) // 2
        end = media["duration_frames"] if index == len(runs) - 1 else (current[-1]["end_frame"] + runs[index + 1][0]["start_frame"]) // 2
        result.append({"take_id": f"{media['media_id']}:take:{index+1}", "media_id": media["media_id"],
                       "start_frame": start, "end_frame": end, "take_index": index + 1,
                       "camera_id": "camera_1", "boundary_source": "suggested", "confirmed": False})
    return result


def propose_take_segments_for_beats(media, beats, transcript, fps, minimum_similarity=0.35):
    """Suggests boundaries only when transcript alignment returns to an earlier screenplay beat."""
    if not beats or not transcript:
        return propose_take_segments(media, transcript, fps, gap_seconds=10**9)
    ordered = sorted(transcript, key=lambda item: item["start_frame"])
    cursor, matched, boundaries = 0, [], []
    for segment in ordered:
        ranked = [(similarity(beat.get("text", ""), segment.get("text", "")), index)
                  for index, beat in enumerate(beats) if beat.get("kind", "dialogue") == "dialogue"]
        ranked = [(score, index) for score, index in ranked if score >= minimum_similarity]
        if not ranked:
            continue
        forward = [row for row in ranked if row[1] >= cursor]
        score, beat_index = max(forward or ranked, key=lambda row: (row[0], -row[1]))
        if matched and beat_index < cursor:
            previous = matched[-1]
            boundary = (previous["end_frame"] + segment["start_frame"]) // 2
            if 0 < boundary < media["duration_frames"] and (not boundaries or boundary > boundaries[-1]):
                boundaries.append(boundary)
        matched.append(segment)
        cursor = beat_index + 1
    if not boundaries:
        return [{"take_id": media["media_id"] + ":take:1", "media_id": media["media_id"],
                 "start_frame": 0, "end_frame": media["duration_frames"], "take_index": 1,
                 "camera_id": "camera_1", "boundary_source": "whole_clip", "confirmed": False}]
    edges = [0, *boundaries, media["duration_frames"]]
    return [{"take_id": f"{media['media_id']}:take:{index+1}", "media_id": media["media_id"],
             "start_frame": start, "end_frame": end, "take_index": index + 1,
             "camera_id": "camera_1", "boundary_source": "suggested", "confirmed": False}
            for index, (start, end) in enumerate(zip(edges, edges[1:])) if end > start]
