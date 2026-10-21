"""Install bundled Fusion templates without connecting to Resolve."""
from pathlib import Path
import os
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.resolve_title_templates import inspect_drfx,install_template

def install(destination):
    for path in (ROOT/'backend/assets/resolve_titles').glob('*.drfx'):
        row=install_template(inspect_drfx(path,bundled=True),destination)
        print('Fusion template:',path.name,row.status)

if __name__=='__main__':
    destination=Path(sys.argv[1]) if len(sys.argv)>1 else Path(os.environ['APPDATA'])/'Blackmagic Design/DaVinci Resolve/Support/Fusion/Templates'
    install(destination)
