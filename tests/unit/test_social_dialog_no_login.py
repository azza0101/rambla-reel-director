import json
import re
import subprocess

from backend.app.curation_ui_v2 import _MANAGEMENT_JS


def test_find_social_opens_dialog_without_launching_provider_windows():
    function = re.search(r'async function prepareSocialV5\(.*?\n}', _MANAGEMENT_JS, re.S).group()
    script = '''
let shown=0,opened=[],synced=0,socialSearchScopeV5=null;
const state={run:null};
const $=()=>({showModal(){shown++}});
const openSocialCheckV5=async p=>opened.push(p);
const syncSocialStartV5=()=>synced++;
''' + function + '''
prepareSocialV5('beat_002').then(()=>console.log(JSON.stringify({shown,opened,scope:socialSearchScopeV5})));
'''
    result = subprocess.run(['node', '-e', script], capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == {'shown': 1, 'opened': [], 'scope': 'beat_002'}
