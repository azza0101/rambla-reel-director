"""Versioned project-local caches. Never committed or shared between clients."""
import hashlib
import json
import time
from pathlib import Path
from .atomic_io import write_json


class JsonCache:
    def __init__(self, root, version):
        self.root = Path(root)
        self.version = version

    def path(self, key):
        token = json.dumps([self.version, key], sort_keys=True, default=str)
        return self.root / (hashlib.sha256(token.encode()).hexdigest() + '.json')

    def get(self, key, ttl):
        try:
            row = json.loads(self.path(key).read_text(encoding='utf-8'))
            if time.time() - row['saved_at'] <= ttl:
                return row['value']
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def put(self, key, value):
        self.root.mkdir(parents=True, exist_ok=True)
        write_json(self.path(key), {'saved_at': time.time(), 'value': value})
