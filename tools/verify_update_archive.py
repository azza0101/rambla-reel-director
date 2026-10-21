"""Validate an authenticated release download before extraction/execution."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile


def verify(archive: Path, manifest: Path) -> dict:
    row=json.loads(manifest.read_text(encoding='utf-8-sig'))
    if not re.fullmatch(r'v\d{4}',str(row.get('version',''))):
        raise ValueError('Invalid version')
    if row.get('archive')!=archive.name:
        raise ValueError('Unexpected archive name')
    with archive.open('rb') as handle:
        digest=hashlib.file_digest(handle,'sha256').hexdigest()
    if digest!=row.get('sha256'):
        raise ValueError('SHA256 mismatch')
    with zipfile.ZipFile(archive) as z:
        if sum(i.file_size for i in z.infolist())>4*1024**3:
            raise ValueError('Archive too large')
        for info in z.infolist():
            p=PurePosixPath(info.filename.replace(chr(92),'/'))
            if p.is_absolute() or '..' in p.parts or ':' in info.filename or ((info.external_attr>>16)&0o170000)==0o120000:
                raise ValueError('Unsafe archive path')
        if z.read('RAMBLA_VERSION').decode().strip()!=row['version']:
            raise ValueError('Version mismatch')
        for name in ('INSTALL_RMBL_B_ROLL.ps1','launch_local_v5.py','SEARCH_UPDATE.ps1'):
            z.getinfo(name)
    return row

if __name__=='__main__':
    print(json.dumps(verify(Path(sys.argv[1]),Path(sys.argv[2]))))
