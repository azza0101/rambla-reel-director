from pathlib import Path

from backend.app.config import Settings


def test_data_root_is_external_to_repository(tmp_path: Path):
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    repo.mkdir()
    data.mkdir()
    settings = Settings(repo_root=repo, data_root=data)
    assert settings.data_root == data.resolve()
