"""Overlay current worker evidence without publishing unfinished candidates."""
from copy import deepcopy


def overlay_live_rows(rows, events):
    result = deepcopy(rows)
    for event in events:
        data = event.get('data') or {}
        slot = data.get('slot_id')
        if not slot or 'search_attempts' not in data:
            continue
        row = next((r for r in result if (r.get('coverage_slot_id') or r.get('beat_id')) == slot), None)
        if row is None:
            row = {'beat_id': slot, 'parent_beat_id': slot.split(':shot:')[0]}
            result.append(row)
        row['search_attempts'] = deepcopy(data['search_attempts'])
        if 'rejected_candidates' in data:
            row['rejected_candidates'] = deepcopy(data['rejected_candidates'])
    return result
