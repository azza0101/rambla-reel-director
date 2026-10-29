"""Optional local Nemotron speaker turns. No ASR, network, GUI or Resolve calls."""
from pathlib import Path
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import wave

from cache import cache_key, read_cache, write_cache

MODEL_SHA256 = '08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1'
VERSION = 'nemotron3-q8-nemo-speech-0.2.0-v1'
PRESET = 'v3-offline'  # Bounded offline-style streaming, NOT full-attention --offline.


class DiarizationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('Diarizzazione locale non disponibile: ' + code)


def source_clock(source):
    fps = source.get('fps')
    count = source.get('duration_frames')
    if (isinstance(fps, bool) or not isinstance(fps, (int, float)) or
            not math.isfinite(fps) or not 0 < fps <= 120 or
            type(count) is not int or count <= 0 or count / fps > 3600):
        raise ValueError('Clock sorgente non valido')
    return float(fps), count


def normalize_segments(rows, source):
    """Native seconds -> clipped half-open source frames; union duplicate spans."""
    fps, count = source_clock(source)
    if not isinstance(rows, list) or len(rows) > 100000:
        raise ValueError('Segmenti di diarizzazione non validi')
    groups = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Segmento di diarizzazione non valido')
        start, end, speaker = (row.get(k) for k in ('start', 'end', 'speaker'))
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or
                not math.isfinite(v) for v in (start, end)) or
                not 0 <= start < end <= count / fps + .08 or
                type(speaker) is not int or not 0 <= speaker <= 8):
            raise ValueError('Intervallo di diarizzazione non valido')
        lo, hi = max(0, math.floor(start * fps + 1e-8)), min(count, math.ceil(end * fps - 1e-8))
        if lo < hi:
            groups.setdefault(str(speaker), []).append((lo, hi))
    if len(groups) > 8:
        raise ValueError('Troppi cluster vocali')
    result = []
    for cluster, intervals in groups.items():
        merged = []
        for lo, hi in sorted(intervals):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        result.extend({'start_frame': lo, 'end_frame': hi, 'cluster': cluster} for lo, hi in merged)
    return sorted(result, key=lambda r: (r['start_frame'], r['end_frame'], r['cluster']))


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class NemotronDiarizer:
    def __init__(self, runtime=None, model=None, device=None, cache_root=None, cpu_runtime=None):
        runtime_root = Path(sys.executable).parent
        self.runtime = Path(runtime or os.environ.get('PREMONTATO_DIARIZATION_RUNTIME') or
                            runtime_root / 'native/nemo-speech/nemo-speech.exe')
        self.model = Path(model or os.environ.get('PREMONTATO_DIARIZATION_MODEL') or
                          runtime_root / 'models/diarization/Nemotron-3-Diarization.q8_0.gguf')
        self.device = device or os.environ.get('PREMONTATO_DIARIZATION_DEVICE', 'cpu')
        if self.device not in ('cpu', 'cuda', 'cuda:0'):
            raise ValueError('Backend di diarizzazione non valido')
        self.cpu_runtime = Path(cpu_runtime or os.environ.get('PREMONTATO_DIARIZATION_CPU_RUNTIME') or self.runtime)
        if not self.runtime.is_file() or not self.model.is_file():
            raise DiarizationError('runtime_or_model_missing')
        if _sha(self.model) != MODEL_SHA256:
            raise ValueError('Modello di diarizzazione non valido')
        self.runtime_sha = _sha(self.runtime)
        self.cpu_sha = _sha(self.cpu_runtime) if self.cpu_runtime.is_file() else None
        self.cache_root = Path(cache_root or os.environ.get('PREMONTATO_DIARIZATION_CACHE_DIR') or
                               Path(os.environ.get('PREMONTATO_CACHE_DIR', '.premontato-cache')) / 'diarization')

    def _invoke(self, wav, output, device, seconds):
        runtime = self.cpu_runtime if device == 'cpu' else self.runtime
        command = [str(runtime), 'diarize', str(wav), '--model', str(self.model),
                   '--device', device, '--preset', PRESET, '--format', 'json',
                   '--output', str(output), '--force']
        try:
            run = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                 timeout=min(300, max(20, seconds * .1 + 10)),
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise DiarizationError('native_timeout') from None
        except OSError:
            raise DiarizationError('native_start') from None
        if run.returncode:
            raise DiarizationError('native_exit')
        try:
            if not output.is_file() or output.stat().st_size > 32 * 1024 * 1024:
                raise ValueError('Output mancante o troppo grande')
            value = json.loads(output.read_text(encoding='utf-8-sig'))
            rows = value['segments']
            if not isinstance(rows, list):
                raise ValueError('Segmenti mancanti')
            return rows
        except (OSError, ValueError, KeyError, TypeError):
            raise DiarizationError('invalid_native_output') from None

    def analyze(self, source):
        from local_audio import load_pcm16
        started = time.perf_counter()
        fps, count = source_clock(source)
        path = Path(source['path'])
        stat = path.stat()
        fingerprint = [str(path.resolve()), stat.st_size, stat.st_mtime_ns,
                       source.get('media_id'), count, fps]
        key = cache_key(fingerprint, VERSION, MODEL_SHA256, self.runtime_sha, self.cpu_sha, self.device, PRESET)
        entry = read_cache(self.cache_root, key)
        if entry:
            try:
                cached = entry['value']
                rows = normalize_segments(cached['segments'], source)
                if (cached['device_used'] not in ('cpu', 'cuda', 'cuda:0') or
                        cached.get('fallback_reason') not in (None, 'native_timeout', 'native_start', 'native_exit', 'invalid_native_output')):
                    raise ValueError('Backend non valido')
                return {'status': 'ready', 'segments': rows, 'cache_hit': True,
                        'device_requested': self.device, 'device_used': cached['device_used'],
                        'fallback_reason': cached.get('fallback_reason'), 'model': VERSION,
                        'elapsed_seconds': time.perf_counter() - started}
            except (KeyError, TypeError, ValueError):
                pass
        self.cache_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.native-', dir=self.cache_root) as folder:
            wav, output = Path(folder) / 'input.wav', Path(folder) / 'segments.json'
            pcm, pcm_info = load_pcm16(source)
            if not len(pcm) or pcm.dtype.str not in ('<i2', '=i2') or pcm.ndim != 1:
                raise ValueError('PCM di diarizzazione non valido')
            with wave.open(str(wav), 'wb') as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(pcm[:round(count / fps * 16000)].tobytes())
            fallback = None
            used = self.device
            try:
                raw = self._invoke(wav, output, used, count / fps)
            except DiarizationError as error:
                if not used.startswith('cuda') or not self.cpu_runtime.is_file():
                    raise
                fallback, used = error.code, 'cpu'
                # Never read a stale GPU output when the CPU attempt fails.
                output.unlink(missing_ok=True)
                raw = self._invoke(wav, output, used, count / fps)
            try:
                rows = normalize_segments(raw, source)
            except ValueError:
                raise DiarizationError('invalid_native_output') from None
            write_cache(self.cache_root, key, {'segments': raw, 'device_used': used, 'fallback_reason': fallback})
        return {'status': 'ready', 'segments': rows, 'cache_hit': False,
                'pcm_cache_hit': bool(pcm_info.get('cache_hit')),
                'device_requested': self.device, 'device_used': used,
                'fallback_reason': fallback, 'model': VERSION,
                'elapsed_seconds': time.perf_counter() - started}
