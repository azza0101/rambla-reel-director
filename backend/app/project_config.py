"""Read only allowlisted local provider settings. Never serialize credentials."""
import os
from pathlib import Path

KEYS={'PEXELS_API_KEY','GOOGLE_API_KEY','GOOGLE_CSE_ID','GEMINI_API_KEY','GROQ_API_KEY'}


def load_project_credentials(root=None):
    root=Path(root) if root else Path(__file__).resolve().parents[2]
    # Exact-build launchers use .acceptance-builds/<sha>-runtime under the project.
    if root.parent.name=='.acceptance-builds': root=root.parent.parent
    path=root/'.env.local'
    if not path.is_file(): return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip() in KEYS:
            os.environ.setdefault(key.strip(),value.strip().strip('"').strip("'"))


def provider_status():
    p=bool(os.environ.get('PEXELS_API_KEY','').strip())
    g=bool(os.environ.get('GOOGLE_API_KEY','').strip() and os.environ.get('GOOGLE_CSE_ID','').strip())
    return {'pexels_configured':p,'google_images_configured':g,
        'image_priority':(['pexels'] if p else [])+(['google'] if g else [])+['wikimedia (fallback)'],
        'warnings':[] if p else ['Pexels key missing: stock shelf unavailable; image search uses configured secondary/fallback providers.']}
