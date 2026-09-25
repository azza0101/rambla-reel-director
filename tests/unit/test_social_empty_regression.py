import subprocess
import shutil
from pathlib import Path


def test_guesthouse_shot_does_not_contradict_its_own_hotel_query():
    from backend.app.editorial_relevance import build_retrieval_spec
    from backend.app.retrieval_quality import generic_prop_mismatches
    shot = {'description': 'A traveler inspecting a modest guesthouse exterior',
            'video_queries': ['traveler inspecting hotel room']}
    spec = build_retrieval_spec({'original_text': 'strutture locali', 'core_meaning': 'local structures, zero plastic'}, shot, 'video')
    assert not spec['generic_shot_demoted']
    assert shot['description'] not in spec['negatives']
    assert 'generic hotel room' not in spec['negatives']
    assert generic_prop_mismatches(shot['description'], 'hotel room tour') == []


def test_social_empty_explains_raw_hits_and_rejections():
    from backend.app.curation_ui_v2 import _MANAGEMENT_JS
    start = _MANAGEMENT_JS.index('function latestSocialAttemptV2(')
    end = _MANAGEMENT_JS.index('function socialStateV2(', start)
    script = _MANAGEMENT_JS[start:end] + '''
const assert=require('assert');
const chunk={assets:[],retrieval_diagnostics:{video_attempts:[{provider:'tiktok',hits:12}],video_rejections:[{source:'tiktok',id:'x',quality_reasons:['thumbnail does not match physical shot']} ]}};
const text=socialEmptyMessageV2(chunk,'tiktok');
assert(text.includes('grezzi') && text.includes('scartat') && text.includes('0 card'),text);
assert(socialEmptyMessageV2({retrieval_diagnostics:{}},'tiktok').includes('No Tiktok search attempt'));
'''
    subprocess.run([shutil.which('node'), '-e', script], check=True, capture_output=True)

