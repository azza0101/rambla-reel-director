"""Small deterministic parser for plain-text and Fountain dialogue pages."""
import hashlib
import re
import unicodedata

SCENE = re.compile(r"^(?:INT\.?|EXT\.?|INT\.?/EXT\.?|EST\.?)(?:\s|\.)", re.I)
SCENE_LABEL = re.compile(r"^SCENA\s+\d+[A-Z]?(?=\s|[.:)–—-]|$)", re.I)
CUE = re.compile(r"^[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ0-9 ._'’-]{0,39}(?:\s*\([^)]*\))?$", re.I)


def _is_scene_heading(line):
    return bool(SCENE.match(line) or SCENE_LABEL.match(line) or line.startswith(".") and SCENE.match(line[1:]))


def _stable(prefix, value):
    return prefix + "_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def parse_script(text, format="auto"):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Il copione è vuoto")
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    has_scene_headings = any(_is_scene_heading(line.strip()) for line in raw_lines)
    scenes, heading, rows, speaker = [], "SCENA 1", [], None
    speaker_indent = 0
    in_script = not has_scene_headings

    def flush():
        nonlocal rows, speaker, speaker_indent
        if not rows:
            return
        scene_id = _stable("scene", heading.casefold() + "|" + str(len(scenes)))
        beats = []
        for index, (kind, character, body) in enumerate(rows):
            norm = unicodedata.normalize("NFC", body)
            beat_id = _stable("beat", scene_id + f"|{index}|" + norm.casefold())
            tags = [tag for tag in ("pause", "reaction", "punchline", "setup", "detail") if tag in norm.casefold()]
            beats.append({"beat_id": beat_id, "scene_id": scene_id, "order": index, "kind": kind,
                          "character": character, "text": norm, "tags": tags})
        scenes.append({"scene_id": scene_id, "heading": heading, "beats": beats})
        rows, speaker, speaker_indent = [], None, 0

    for raw_line in raw_lines:
        indent = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()
        if not line:
            continue
        if _is_scene_heading(line):
            flush()
            heading = line.lstrip(".")
            in_script = True
            continue
        if not in_script or re.fullmatch(r"\d+\.?", line):
            continue
        if line.startswith("!"):
            rows.append(("action", None, line[1:].strip()))
        elif line.startswith("(") and line.endswith(")"):
            rows.append(("parenthetical", speaker, line[1:-1].strip()))
        elif CUE.fullmatch(line) and not line.endswith((".", "!", "?")) and (
                indent >= 24 or re.sub(r"\s*\([^)]*\)$", "", line).strip().isupper()):
            speaker = re.sub(r"\s*\([^)]*\)$", "", line).strip()
            speaker_indent = indent
        else:
            if speaker_indent >= 24 and indent == 0:
                speaker = None
            kind = "dialogue" if speaker else "action"
            body = line
            if rows and rows[-1][0] == kind and rows[-1][1] == speaker and kind in {"dialogue", "action"}:
                previous = rows[-1]
                rows[-1] = (kind, speaker, previous[2] + " " + body)
            else:
                rows.append((kind, speaker, body))
    flush()
    return {"scenes": scenes, "warnings": []}
