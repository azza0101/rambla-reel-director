"""Launch the Windows updater only from registered installations."""
from pathlib import Path
import json
import subprocess


def installed_root(root: Path) -> bool:
    try:
        row=json.loads((root.parent/'install.json').read_text(encoding='utf-8-sig'))
        return Path(row['app_root']).resolve()==root.resolve() and not (root/'.git').exists()
    except (OSError, ValueError, KeyError, TypeError):
        return False


def launch_update(root: Path) -> dict:
    if not installed_root(root):
        raise RuntimeError('Copia di sviluppo: installa il setup separatamente per provare SEARCH UPDATE.')
    script=root/'SEARCH_UPDATE.ps1'
    if not script.is_file():
        raise RuntimeError('Updater mancante: ripara con il setup.')
    from .github_auth import github_environment
    subprocess.Popen(['powershell.exe','-NoExit','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-AppRoot',str(root)],cwd=str(root),env=github_environment(root),creationflags=getattr(subprocess,'CREATE_NEW_CONSOLE',0))
    return {'status':'started','message':'Controllo GitHub aperto nella finestra aggiornamento.'}
