"""Install only the dedicated GitHub credential from a personal setup."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.github_auth import store_token

if __name__=='__main__':
    payload=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    if payload.get('github_distribution_token'):
        store_token(ROOT,payload['github_distribution_token'])
        print('Accesso tecnico GitHub preconfigurato e protetto per questo utente Windows.')
