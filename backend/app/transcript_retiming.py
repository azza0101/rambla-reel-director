"""Repair estimated word timing while preserving reviewed text and selections."""
from copy import deepcopy
from difflib import SequenceMatcher
import re
import unicodedata


def retime_chunks(chunks, measured, *, fps=25):
    if fps <= 0:
        raise ValueError('fps must be positive')
    result = deepcopy(chunks)
    old = [w for c in result for w in c['words']]
    new = [w for s in measured['segments'] for w in s['words']]
    def token(word):
        return re.sub(r'\W', '', unicodedata.normalize('NFKD', word['text'].casefold()).encode('ascii', 'ignore').decode())
    mapping = {}
    matcher = SequenceMatcher(None, list(map(token, old)), list(map(token, new)), autojunk=False)
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == 'equal' or (tag == 'replace' and b-a == d-c):
            mapping.update({i: new[c+i-a] for i in range(a, b)})
    if len(mapping) / max(1, len(old)) < .98:
        raise ValueError('Transcript changed too much for safe timing-only repair')
    unresolved = []
    for i, word in enumerate(old):
        if i in mapping:
            word.update(start=float(mapping[i]['start']), end=float(mapping[i]['end']))
        else:
            unresolved.append({'index': i, 'text': word['text']})
    # ASR may overlap neighboring words. Preserve text order and create a
    # monotonic, exclusive time interval for every displayed token.
    for i, word in enumerate(old):
        if i:
            word['start'] = max(float(word['start']), float(old[i-1]['start']) + 1 / fps)
        word['end'] = max(float(word['end']), float(word['start']) + 1 / fps)
    for a, b in zip(old, old[1:]):
        a['end'] = min(a['end'], b['start'])
    for chunk in result:
        chunk['start'] = chunk['words'][0]['start']
        chunk['end'] = chunk['words'][-1]['end']
        chunk['duration'] = chunk['end'] - chunk['start']
    return result, unresolved
