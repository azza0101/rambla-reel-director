"""Typed boundary between MAGICO orchestration and the existing product engines."""
from typing import Protocol, Callable
from .magic_models import MagicContext, MagicOptions


class MagicServices(Protocol):
    async def run_phase(self, phase: str, context: MagicContext, options: MagicOptions,
                        report: Callable[[int, int, str], None]) -> dict: ...


class MagicWaitingInput(RuntimeError):
    """An external verification or a supported source is needed to continue."""


class MagicBudgetReached(RuntimeError):
    """Return a partial, explicit result instead of making more paid calls."""
