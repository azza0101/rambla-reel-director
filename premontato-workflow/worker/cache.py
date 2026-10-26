"""Atomic JSON cache keyed by stable input fingerprints."""
import hashlib
import json
import os
import tempfile
from pathlib import Path


def cache_key(*parts):
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_cache(root, key):
    path = Path(root) / (key + ".json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if value.get("key") == key else None
    except (OSError, ValueError, AttributeError):
        return None


def write_cache(root, key, value):
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".premontato-", suffix=".tmp", dir=path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump({"key": key, "value": value}, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path / (key + ".json"))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_cache(root, fingerprint, analyzer_version, options):
    key = cache_key(fingerprint, analyzer_version, options)
    entry = read_cache(root, key)
    return entry["value"] if entry else None


def get_or_compute(root, fingerprint, analyzer_version, options, compute):
    key = cache_key(fingerprint, analyzer_version, options)
    entry = read_cache(root, key)
    if entry:
        return entry["value"], True
    value = compute()
    write_cache(root, key, value)
    return value, False
