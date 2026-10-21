from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_root: Path = Path.cwd()
    data_root: Path = Path(r"Z:\RAMBLA-reel-data")

    def model_post_init(self, __context: object) -> None:
        self.repo_root = self.repo_root.resolve()
        self.data_root = self.data_root.resolve()
        if self.data_root == self.repo_root or self.repo_root in self.data_root.parents:
            raise ValueError("data_root must be outside repository")
