"""Persistent contracts for the economical, non-agentic MAGICO workflow."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


Provider = Literal['pexels', 'youtube_shorts', 'youtube', 'tiktok', 'instagram', 'envato', 'google_images']


class MagicOptions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    pause_mode: Literal['soft', 'medium', 'strong'] = 'medium'
    end_margin_ms: int = Field(default=120, ge=0, le=400)
    providers: list[Provider] = Field(default_factory=lambda: ['pexels', 'youtube_shorts', 'google_images'])
    # Long source videos can need several small editorial batches.  Twenty
    # remains a bounded per-run allowance and prevents a completed CUT from
    # stopping before its own visual plan is published.
    max_cloud_requests: int = Field(default=20, ge=1, le=100)
    max_visual_requests: int = Field(default=4, ge=0, le=100)
    queries_per_provider: int = Field(default=2, ge=1, le=4)
    candidates_per_beat: int = Field(default=6, ge=1, le=12)
    # Stored with every run. A changed workflow must produce a fresh run
    # rather than silently delivering checkpoints from an earlier algorithm.
    workflow_revision: Literal['magic-v2'] = 'magic-v2'

    @model_validator(mode='after')
    def bounded_visual_budget(self):
        if self.max_visual_requests > self.max_cloud_requests:
            self.max_visual_requests = self.max_cloud_requests
        self.providers = list(dict.fromkeys(self.providers))
        return self


class MagicContext(BaseModel):
    source_project_id: str
    output_project_id: str | None = None
    source_signature: str
    cut_revision: str | None = None
    run_id: str


class MagicProgress(BaseModel):
    phase: str
    completed: int = Field(ge=0)
    total: int = Field(ge=0)
    message: str


class CoverageDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    beat_id: str
    asset_id: str
    provider: str
    role: Literal['coverage', 'fallback_image', 'generic'] = 'coverage'
    enabled: bool = True
    edited_in_frame: int = Field(ge=0)
    edited_out_frame: int = Field(gt=0)
    source_in_frame: int = Field(default=0, ge=0)
    source_out_frame: int = Field(gt=0)
    verdict: Literal['verified', 'uncertain', 'rejected']
    reason: str

    @model_validator(mode='after')
    def coherent_interval(self):
        if self.edited_out_frame <= self.edited_in_frame or self.source_out_frame <= self.source_in_frame:
            raise ValueError('Intervallo copertura non valido')
        if self.role == 'fallback_image' and self.enabled:
            raise ValueError('Le immagini alternative devono restare disattivate')
        if self.enabled and self.verdict != 'verified':
            raise ValueError('Copertura attiva senza verifica riuscita')
        return self
