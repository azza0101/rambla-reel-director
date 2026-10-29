"""Conservative acoustic evidence fusion; never infer a face or actor name."""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import math

from diarization import DiarizationError, NemotronDiarizer, source_clock

FALLBACK_BASIS = 'independent_diarization_cluster_consensus'
_ACOUSTIC_BASES = {'source_local_voice_embedding', 'single_profile_high_absolute_similarity',
                   'cross_source_profile_consensus'}
_DIARIZER = None


def get_diarizer():
    global _DIARIZER
    if _DIARIZER is None:
        _DIARIZER = NemotronDiarizer()
    return _DIARIZER


def eligible_for_face_enrollment(unit):
    evidence = unit.get('voice_evidence', {})
    return bool(unit.get('voice') and evidence.get('status') == 'identified' and
                evidence.get('basis') in _ACOUSTIC_BASES and
                evidence.get('enrollment_eligible', True) and
                not unit.get('diarization_evidence', {}).get('conflict'))


def _index_segments(segments, count):
    groups = defaultdict(list)
    for row in segments:
        lo, hi, cluster = (row.get(k) for k in ('start_frame', 'end_frame', 'cluster'))
        if (type(lo) is not int or type(hi) is not int or not 0 <= lo < hi <= count or
                not isinstance(cluster, str) or not 0 < len(cluster) <= 32):
            raise ValueError('Turni vocali non validi')
        groups[cluster].append((lo, hi))
    if len(groups) > 8:
        raise ValueError('Troppi cluster vocali')
    result = {}
    for cluster, rows in groups.items():
        merged = []
        for lo, hi in sorted(rows):
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        result[cluster] = ([a for a, _ in merged], [b for _, b in merged])
    return result


def _measure(unit, index):
    lo, hi = unit['start'], unit['end']
    durations = {}
    for cluster, (starts, ends) in index.items():
        first, last = bisect_right(ends, lo), bisect_left(starts, hi)
        overlap = sum(min(hi, ends[i]) - max(lo, starts[i]) for i in range(first, last))
        if overlap > 0:
            durations[cluster] = overlap
    ranked = sorted(durations, key=durations.get, reverse=True)
    if not ranked:
        return {'cluster': None, 'coverage': 0., 'dominance': 0., 'margin': 0., 'strong': False}
    best = ranked[0]
    top = durations[best]
    second = durations[ranked[1]] if len(ranked) > 1 else 0
    duration = hi - lo
    coverage, dominance, margin = top / duration, top / sum(durations.values()), (top - second) / duration
    return {'cluster': best, 'coverage': coverage, 'dominance': dominance, 'margin': margin,
            'strong': coverage >= .8 and dominance >= .8 and margin >= .5}


def _cluster_mapping(anchors, exclude=None):
    groups = defaultdict(list)
    for anchor in anchors:
        if exclude and max(anchor['start'], exclude['start']) < min(anchor['end'], exclude['end']):
            continue
        groups[anchor['cluster']].append(anchor)
    mapping, support = {}, {}
    for cluster, pool in groups.items():
        # A connected component of overlapping intervals supplies ONE vote.
        # Conflicting labels in that component supply no independent observation.
        components = []
        for anchor in sorted(pool, key=lambda a: (a['start'], a['end'])):
            if components and anchor['start'] < components[-1]['end']:
                component = components[-1]
                component['end'] = max(component['end'], anchor['end'])
                component['voices'].add(anchor['voice'])
            else:
                components.append({'end': anchor['end'], 'voices': {anchor['voice']}})
        votes = Counter(next(iter(c['voices'])) for c in components if len(c['voices']) == 1)
        if not votes:
            continue
        winner, number = votes.most_common(1)[0]
        if number >= 2 and number / sum(votes.values()) >= .8:
            mapping[cluster] = winner
            support[cluster] = {'independent_anchors': number, 'consensus': number / sum(votes.values())}
    return mapping, support


def fuse_voice_units(source, units, segments):
    fps, count = source_clock(source)
    if not isinstance(units, list) or not isinstance(segments, list):
        raise ValueError('Evidenze vocali non valide')
    index = _index_segments(segments, count)
    measures, anchors = [], []
    for unit in units:
        if (type(unit.get('start')) is not int or type(unit.get('end')) is not int or
                not 0 <= unit['start'] < unit['end'] <= count):
            raise ValueError('Intervallo battuta non valido')
        measure = _measure(unit, index)
        measures.append(measure)
        if (eligible_for_face_enrollment(unit) and measure['strong'] and
                unit['end'] - unit['start'] >= fps and len(unit.get('text', '').split()) >= 3):
            anchors.append({'voice': unit['voice'], 'cluster': measure['cluster'],
                            'start': unit['start'], 'end': unit['end']})
    rows, stats = [], Counter()
    mappings = {}
    for unit, measure in zip(units, measures):
        excluded = tuple(i for i, a in enumerate(anchors)
                         if max(a['start'], unit['start']) < min(a['end'], unit['end']))
        if excluded not in mappings:
            mappings[excluded] = _cluster_mapping(anchors, unit)
        mapping, support = mappings[excluded]
        candidate = (mapping.get(measure['cluster']) if measure['strong'] and
                     unit['end'] - unit['start'] >= math.ceil(.2 * fps) else None)
        primary = unit.get('voice')
        secondary = {**measure, 'candidate_voice': candidate,
                     'source_id': source.get('media_id'),
                     'support': support.get(measure['cluster']),
                     'conflict': bool(primary and candidate and primary != candidate)}
        row = {**unit, 'diarization_evidence': secondary}
        if primary:
            stats['primary_identified'] += 1
            stats['conflicts'] += secondary['conflict']
        elif candidate:
            row['voice'] = candidate
            row['voice_evidence'] = {'status': 'identified', 'voice': candidate,
                                     'basis': FALLBACK_BASIS, 'enrollment_eligible': False,
                                     'primary_evidence': dict(unit.get('voice_evidence', {}))}
            stats['fallback_identified'] += 1
        else:
            stats['remaining_unknown'] += 1
        rows.append(row)
    mapping, support = _cluster_mapping(anchors)
    summary = {key: stats[key] for key in ('primary_identified', 'fallback_identified',
                                         'remaining_unknown', 'conflicts')}
    return {'units': rows, 'summary': summary, 'cluster_mapping': mapping, 'cluster_support': support}


def enhance_source_voices(source, data, report=None, diarizer=None):
    def progress(current, status, reason=None):
        if report:
            report({'phase': 'voice_diarization', 'current': current, 'total': 1,
                    'label': 'Secondo controllo locale delle voci', 'status': status, 'reason': reason})
    progress(0, 'running')
    try:
        result = (diarizer or get_diarizer()).analyze(source)
        fused = fuse_voice_units(source, data['units'], result['segments'])
    except (DiarizationError, ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        code = error.code if isinstance(error, DiarizationError) else 'invalid_or_failed_secondary'
        status = 'unavailable' if code == 'runtime_or_model_missing' else 'failed'
        progress(1, status, code)
        return {**data, 'diarization': {'status': status, 'reason': code}}
    progress(1, 'ready')
    return {**data, 'units': fused['units'],
            'diarization': {**{k: v for k, v in result.items() if k != 'segments'},
                            'fusion': fused['summary'], 'cluster_mapping': fused['cluster_mapping'],
                            'cluster_support': fused['cluster_support']}}


def analyze_voice_evidence(payload, report=None):
    """Independent worker entry point; no storyboard, network or GUI required."""
    from voice_identity import source_voices
    mode = payload.get('voice_mode', 'hybrid')
    if mode not in ('wespeaker', 'hybrid'):
        raise ValueError('Modalita vocale non valida')
    data = source_voices(payload['source'], payload['units'], report)
    if mode == 'hybrid':
        data = enhance_source_voices(payload['source'], data, report)
    return {'engine': 'local_voice_evidence_v1', 'voice_mode': mode, **data}
