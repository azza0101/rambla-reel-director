"""Advisory shot scale from local frames; no face identity recognition."""
from pathlib import Path


def classify_face_areas(areas):
    if not areas:
        return "unknown", 0.0
    area = max(areas)
    if area >= 0.18:
        return "close", min(0.95, 0.65 + area)
    if area >= 0.06:
        return "medium", min(0.88, 0.55 + area)
    return "wide", 0.55


def analyze_video(media, sample_fps=1.0, face_cascade_path=None):
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
    cascade_path = face_cascade_path or (Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    detector = cv2.CascadeClassifier(str(cascade_path))
    if detector.empty():
        cap.release()
        raise RuntimeError("Modello face detector OpenCV non disponibile")
    fps, count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(fps / max(0.1, sample_fps)))
    samples, previous = [], None
    for frame_number in range(0, count, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ok, frame = cap.read()
        if not ok:
            continue
        small = cv2.resize(frame, (160, 90))
        hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256] * 3)
        cv2.normalize(hist, hist)
        cut = previous is not None and cv2.compareHist(previous, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.62
        previous = hist
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(30, 30))
        areas = [float(w * h) / float(frame.shape[0] * frame.shape[1]) for (x, y, w, h) in faces]
        label, confidence = classify_face_areas(areas)
        samples.append({"frame": frame_number, "cut": bool(cut), "shot_size": label, "confidence": confidence,
                        "face_boxes": [{"x": x / frame.shape[1], "y": y / frame.shape[0], "width": w / frame.shape[1], "height": h / frame.shape[0]} for x, y, w, h in faces]})
    cap.release()
    boundaries = [0] + [sample["frame"] for sample in samples if sample["cut"]] + [count]
    boundaries = sorted(set(boundaries))
    output = []
    for start, end in zip(boundaries, boundaries[1:]):
        choices = [item for item in samples if start <= item["frame"] < end]
        middle = choices[len(choices) // 2] if choices else {"shot_size": "unknown", "confidence": 0, "face_boxes": []}
        output.append({"segment_id": f"{media['media_id']}:{start}", "media_id": media["media_id"],
                       "start_frame": start, "end_frame": end, "shot_size": middle["shot_size"],
                       "visible_subjects": [], "face_boxes": middle["face_boxes"], "confidence": middle["confidence"],
                       "source": "automatic"})
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
