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


def sampled_frames(cap, count, step, on_progress=None):
    """Decode forward once; avoid repeated GOP seeks while preserving sample positions."""
    for index in range(count):
        if index % step:
            if not cap.grab(): break
            continue
        if on_progress: on_progress(index, count)
        ok, frame = cap.read()
        if not ok: break
        yield index, frame


def open_video_capture(cv2, filename):
    """Prefer the bundled Windows hardware decoder, with a portable CPU fallback.

    This accelerates video reading only; YuNet inference still uses the CPU.
    Report the mode actually selected, since ANY may itself fall back to CPU.
    """
    if sys.platform == 'win32':
        capture = None
        try:
            capture = cv2.VideoCapture(str(filename), cv2.CAP_FFMPEG,
                [cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY])
            if capture.isOpened():
                mode = int(capture.get(cv2.CAP_PROP_HW_ACCELERATION))
                backend = ('CPU' if mode == cv2.VIDEO_ACCELERATION_NONE else
                    'D3D11' if mode == cv2.VIDEO_ACCELERATION_D3D11 else 'Hardware')
                return capture, backend
        except Exception:
            pass
        if capture is not None:
            capture.release()
    return cv2.VideoCapture(str(filename)), 'CPU'


def analyze_video(media, sample_fps=1.0, face_cascade_path=None, on_progress=None):
    try:
        import cv2
    except ImportError as error:
        raise RuntimeError("OpenCV non installato nel runtime Python") from error
    path = Path(media["path"])
    if not path.is_file():
        raise ValueError("File media non disponibile")
    cap, decode_backend = open_video_capture(cv2, path)
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
    def frames():
        nonlocal decode_backend
        from video_reader import sampled_gpu_frames
        completed=-1
        try:
            for index,frame in sampled_gpu_frames(media,step):
                decode_backend='NVDEC'
                if on_progress:on_progress(index,count)
                completed=index
                yield index,frame
        except Exception:
            # Timestamp/codec failures resume with the original reader, without duplicates.
            for index,frame in sampled_frames(cap,count,step,on_progress):
                if index>completed:yield index,frame
    for frame_number, frame in frames():
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
                       "source": "automatic", "analyzer": ANALYZER_VERSION, "decode_backend": decode_backend, "sample_count": len(choices)})
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


SFACE_SHA256 = '2b0e941e6f16cc048c20aee0c8e31f569118f65d702914540f7bfdc14048d78a'
VISUAL_REVIEW_VERSION = 'sface-int8-v2-fullres-10s'

def recognition_model_path():
    for folder in (Path(sys.executable).parent, Path(__file__).resolve().parents[1] / 'runtime'):
        model = folder / 'models' / 'sface' / 'model.onnx'
        if model.is_file() and hashlib.sha256(model.read_bytes()).hexdigest() == SFACE_SHA256:
            return model
    raise RuntimeError('Modello SFace mancante o danneggiato: reinstalla Premontato')


def cluster_faces(observations, threshold=.55, margin=.08):
    '''Conservative complete-link suggestions. Co-occurring faces never share a cluster.
    Ambiguous observations stay unassigned; no transitive chaining through a weak match.
    '''
    import math
    clusters, result = [], []
    for item in observations:
        vector = item.get('embedding', [])
        norm = math.sqrt(sum(x*x for x in vector))
        updated = {k:v for k,v in item.items() if k != 'embedding'}
        if not norm:
            result.append({**updated, 'person_id':None, 'ambiguous':True})
            continue
        vector = [x/norm for x in vector]
        scores = []
        for index, group in enumerate(clusters):
            if any(member[0] == item['still_id'] for member in group):
                continue
            score = min(sum(a*b for a,b in zip(vector, member[1])) for member in group)
            scores.append((score,index))
        scores.sort(reverse=True)
        ambiguous = bool(len(scores)>1 and scores[0][0]>=threshold and scores[0][0]-scores[1][0]<margin)
        if ambiguous:
            person_id, score = None, scores[0][0]
        elif scores and scores[0][0]>=threshold:
            score,index=scores[0];clusters[index].append((item['still_id'],vector));person_id=f'person-{index+1}'
        else:
            clusters.append([(item['still_id'],vector)]);person_id=f'person-{len(clusters)}';score=None
        result.append({**updated,'person_id':person_id,'ambiguous':ambiguous,'similarity':score})
    return result


def speaker_coverage(shots, media_id, start, end, character):
    '''Only confirmed interval coverage can assert that a character is visible/absent.'''
    covered = [s for s in shots if s.get('media_id')==media_id and s.get('reviewed') and s['start_frame']<end and s['end_frame']>start]
    cursor=start; statuses=[]
    for shot in sorted(covered,key=lambda s:s['start_frame']):
        if shot['start_frame']>cursor: return 'unknown'
        subjects=[name.casefold().strip() for name in shot.get('visible_subjects',[])]
        statuses.append('visible' if character.casefold().strip() in subjects else 'absent' if subjects else 'unknown')
        cursor=max(cursor,shot['end_frame'])
    if cursor<end or not statuses: return 'unknown'
    return statuses[0] if len(set(statuses))==1 else 'unknown'


def visual_review_media(media, shots, on_progress=None):
    '''Sparse stills are local JPEG data URLs. Embeddings remain in the private worker cache.
    Each ten-second interval has two real frames, so a moving camera is not labelled from one opening frame.
    '''
    import cv2, base64
    cv2.setNumThreads(1)
    detector=cv2.FaceDetectorYN.create(str(model_path()),'',(640,360),.7,.3,5000)
    recognizer=None; recognition_error=None
    try: recognizer=cv2.FaceRecognizerSF.create(str(recognition_model_path()),'')
    except Exception as error: recognition_error=str(error)
    cap=cv2.VideoCapture(str(media['path']))
    if not cap.isOpened(): raise ValueError('Video non leggibile per la revisione visiva')
    fps=float(media.get('fps') or cap.get(cv2.CAP_PROP_FPS) or 25)
    count=int(media['duration_frames']); window=max(1,round(fps*10))
    boundaries={0,count}
    boundaries.update(s['start_frame'] for s in shots if s.get('media_id')==media['media_id'])
    boundaries.update(s['end_frame'] for s in shots if s.get('media_id')==media['media_id'])
    ordered=sorted(b for b in boundaries if 0<=b<=count); intervals=[];observations=[]
    for left,right in zip(ordered,ordered[1:]):
        for start in range(left,right,window):
            end=min(right,start+window)
            intervals.append({'segment_id':f"{media['media_id']}:{start}:{end}",'media_id':media['media_id'],
                'start_frame':start,'end_frame':end,'visible_subjects':[],'reviewed':False,'source':'automatic','stills':[]})
    extraction_errors=0
    try:
        for index,interval in enumerate(intervals):
            samples=[]
            for frame_number in sorted(set(interval['start_frame']+int((interval['end_frame']-interval['start_frame']-1)*fraction) for fraction in (.33,.67))):
                cap.set(cv2.CAP_PROP_POS_FRAMES,frame_number);ok,frame=cap.read()
                if not ok:
                    extraction_errors+=1
                    continue
                full_frame=frame
                frame=cv2.resize(frame,(640,max(1,round(frame.shape[0]*640/frame.shape[1]))));height,width=frame.shape[:2]
                detector.setInputSize((width,height));_,faces=detector.detect(frame)
                label,confidence=classify_face_heights([] if faces is None else [float(row[3])/height for row in faces])
                samples.append({'shot_size':label,'confidence':confidence,'face_boxes':[]})
                still_id=f"{interval['segment_id']}:{frame_number}";face_records=[]; annotated=frame.copy()
                for face_index,face in enumerate([] if faces is None else faces):
                    x,y,w,h=[int(v) for v in face[:4]]
                    crop=frame[max(0,y):min(height,y+h),max(0,x):min(width,x+w)]
                    if crop.size==0: continue
                    observation={'observation_id':f'{still_id}:{face_index}','still_id':still_id,'face_number':face_index+1,
                        'box':{'x':x/width,'y':y/height,'width':w/width,'height':h/height},'embedding':[]}
                    if recognizer is not None and min(w,h)>=24:
                        try:
                            full_face=face.copy()
                            full_face[:14:2]*=full_frame.shape[1]/width
                            full_face[1:14:2]*=full_frame.shape[0]/height
                            observation['embedding']=recognizer.feature(recognizer.alignCrop(full_frame,full_face)).flatten().tolist()
                        except cv2.error: pass
                    sx,sy=full_frame.shape[1]/width,full_frame.shape[0]/height
                    full_crop=full_frame[max(0,int(y*sy)):min(full_frame.shape[0],int((y+h)*sy)),max(0,int(x*sx)):min(full_frame.shape[1],int((x+w)*sx))]
                    crop=cv2.resize(full_crop if full_crop.size else crop,(96,112));encoded=cv2.imencode('.jpg',crop,[cv2.IMWRITE_JPEG_QUALITY,75])[1]
                    observation['thumbnail']='data:image/jpeg;base64,'+base64.b64encode(encoded).decode('ascii')
                    observations.append(observation);face_records.append(observation['observation_id'])
                    cv2.rectangle(annotated,(max(0,x),max(0,y)),(min(width-1,x+w),min(height-1,y+h)),(170,220,90),1)
                    cv2.putText(annotated,str(face_index+1),(max(0,x),max(15,y-3)),cv2.FONT_HERSHEY_SIMPLEX,.55,(170,220,90),1)
                jpeg=cv2.imencode('.jpg',annotated,[cv2.IMWRITE_JPEG_QUALITY,72])[1]
                interval['stills'].append({'still_id':still_id,'frame':frame_number,'image':'data:image/jpeg;base64,'+base64.b64encode(jpeg).decode('ascii'),'face_ids':face_records})
            summary=summarize_samples(samples);interval.update(shot_size=summary['shot_size'],confidence=summary['confidence'])
            if on_progress: on_progress(index+1,len(intervals))
    finally: cap.release()
    return {'intervals':intervals,'observations':observations,'recognition_error':recognition_error,'extraction_errors':extraction_errors}
