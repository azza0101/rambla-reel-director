"""Optional dedicated GitHub token, protected for this Windows user by DPAPI.

The personal installer may provision a fine-grained token. Never import the
owner's existing GitHub OAuth/classic token, or pass a token in command lines.
"""
import ctypes
import os
from pathlib import Path
import re
import shutil


def credential_path(app_root):
    return Path(app_root).parent/'rambla-data/credentials/github-token.dpapi'


def _crypt(data, *, decrypt=False):
    if os.name!='nt':raise RuntimeError('Windows DPAPI required')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob()
    crypt=ctypes.windll.crypt32
    if decrypt:
        ok=crypt.CryptUnprotectData(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target))
    else:
        ok=crypt.CryptProtectData(ctypes.byref(source),'RMBL GitHub',None,None,None,1,ctypes.byref(target))
    if not ok:raise RuntimeError('GitHub credential protection unavailable for this Windows user')
    try:return ctypes.string_at(target.pbData,target.cbData)
    finally:
        free=ctypes.windll.kernel32.LocalFree
        free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(ctypes.cast(target.pbData,ctypes.c_void_p))


def validate_token(token):
    if not isinstance(token,str) or not re.fullmatch(r'github_pat_[a-zA-Z0-9_]{30,250}',token):
        raise ValueError('Serve un token fine-grained dedicato, non il token completo dell’account.')
    return token


def store_token(app_root,token):
    token=validate_token(token.strip())
    path=credential_path(app_root);path.parent.mkdir(parents=True,exist_ok=True)
    encrypted=_crypt(token.encode('utf-8'))
    if path.exists():shutil.copy2(path,path.with_suffix('.dpapi.bck'))
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_bytes(encrypted);os.replace(temporary,path)
    return path


def load_token(app_root):
    path=credential_path(app_root)
    if not path.is_file():return None
    return validate_token(_crypt(path.read_bytes(),decrypt=True).decode('utf-8'))


def github_environment(app_root,base_env=None):
    env=dict(os.environ if base_env is None else base_env)
    token=load_token(app_root)
    if token:env['GH_TOKEN']=token
    return env
