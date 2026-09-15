"""Pytest runner for Windows sandboxes where mode=0700 temp directories are unreadable.

Uses ordinary workspace directories; no system ACL/configuration changes.
"""
from pathlib import Path
import sys
import uuid
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class WorkspaceTemps:
    @pytest.fixture
    def tmp_path(self):
        root = Path.cwd() / '.test-workspace' / uuid.uuid4().hex
        root.mkdir(parents=True)
        return root


if __name__ == '__main__':
    raise SystemExit(pytest.main(['-p','no:tmpdir','-p','no:cacheprovider','--import-mode=importlib',*sys.argv[1:]],plugins=[WorkspaceTemps()]))
