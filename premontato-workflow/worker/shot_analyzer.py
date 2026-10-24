"""Advisory shot scale from local frames; no face identity recognition."""
from pathlib import Path
import hashlib
import sys
from collections import Counter

ANALYZER_VERSION = "yunet640-v1-temporal"
MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"

def summarize_samples(samples):
    known = [s for s in samples if s["shot_size"] != "unknown"]
    if not known:
        return {"shot_size": "unknown", "confidence": 0.0, "face_boxes": []}
    label, count = Counter(s["shot_size"] for s in known).most_common(1)[0]
    best = next(s for s in known if s["shot_size"] == label)
    return {**best, "confidence": min(best["confidence"], count / len(samples))}

def model_path():
    candidates = [Path(sys.executable).parent / "models" / "yunet.onnx", Path(__file__).resolve().parents[1] / "runtime" / "models" / "yunet.onnx"]
    for path in candidates:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == MODEL_SHA256:
            return path
    raise RuntimeError("Modello YuNet mancante o danneggiato: reinstalla Premontato")


def classify_face_areas(areas):
    if not areas:
        return "unknown", 0.0
    area = max(areas)
    if area >= 0.18:
        return "close", min(0.95, 0.65 + area)
    if area >= 0.06:
        return "medium", min(0.88, 0.55 + area)
    return "wide", 0.55


def classify_face_heights(heights):
    """Estimate framing from face height within the frame.

    Face area alone is too strict: a face occupying 15% of frame height in
    16:9 footage is only ~1.3% of total image area and was incorrectly marked
    wide by the previous thresholds.
    """
    if not heights:
        return "unknown", 0.0
    height = max(heights)
    if height >= 0.28:
        return "close", min(0.9, 0.62 + height / 3)
    if height >= 0.13:
        return "medium", min(0.82, 0.55 + height / 3)
    return "wide", 0.55


def analyze_video(media, sample_fps=1.0, face_cascade_path=None, on_progress=None):
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV non installato nel runtime Python") from error
    path = Path(media["path"])
    if not path.is_file():
        raise ValueError("File media non disponibile")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError("OpenCV non riesce a leggere il media")
    try:
        detector = cv2.FaceDetectorYN.create(str(model_path()), "", (640, 360), 0.6, 0.3, 5000)
    except Exception:
        cap.release()
        raise
    fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(fps / max(0.1, sample_fps)))
    samples, previous = [], None
    for frame_number in range(0, count, step):
        if on_progress:
            on_progress(frame_number, count)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = cap.read()
        if not ok:
            continue
        small = cv2.resize(frame, (160, 90))
        hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
        cv2.normalize(hist, hist)
        cut = previous is not None and cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.62
        previous = hist
        width = 640
        height = max(1, round(frame.shape[0] * width / frame.shape[1]))
        resized = cv2.resize(frame, (width, height))
        detector.setInputSize((width, height))
        _, detections = detector.detect(resized)
        faces = [] if detections is None else detections[:, :4]
        face_heights = [float(h) / height for (x, y, w, h) in faces]
        label, confidence = classify_face_heights(face_heights)
        samples.append({"frame": frame_number, "cut": bool(cut), "shot_size": label, "confidence": confidence,
                        "face_boxes": [{"x": float(x) / width, "y": float(y) / height, "width": float(w) / width, "height": float(h) / height} for x, y, w, h in faces]})
    cap.release()
    boundaries = [0] + [sample["frame"] for sample in samples if sample["cut"]] + [count]
    boundaries = sorted(set(boundaries))
    output = []
    for start, end in zip(boundaries, boundaries[1:]):
        choices = [item for item in samples if start <= item["frame"] < end]
        middle = summarize_samples(choices)
        output.append({"segment_id": f"{media['media_id']}:{start}", "media_id": media["media_id"],
                       "start_frame": start, "end_frame": end, "shot_size": middle["shot_size"],
                       "visible_subjects": [], "face_boxes": middle["face_boxes"], "confidence": middle["confidence"],
                       "source": "automatic", "analyzer": ANALYZER_VERSION, "sample_count": len(choices)})
    return output


def apply_manual_overrides(segments, overrides, fingerprint):
    result = []
    for segment in segments:
        updated = dict(segment)
        for override in overrides:
            if override.get("fingerprint") == fingerprint and override.get("media_id") == segment.get("media_id") and override.get("start_frame", 0) < segment["end_frame"] and override.get("end_frame", 0) > segment["start_frame"]:
                updated.update({"shot_size": override["shot_size"], "visible_subjects": override.get("visible_subjects", []), "source": "manual"})
        result.append(updated)
    return result
