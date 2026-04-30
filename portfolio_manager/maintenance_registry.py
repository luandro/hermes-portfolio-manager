"""Maintenance skill registry for MVP 4."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from portfolio_manager.maintenance_models import (
        MaintenanceContext,
        MaintenanceSkillResult,
        MaintenanceSkillSpec,
    )

# Skill ID validation pattern
_SKILL_ID_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")

# Type alias for skill execute function
SkillExecuteFn = Callable[["MaintenanceContext"], "MaintenanceSkillResult"]


class _Registry:
    """In-memory registry of maintenance skills."""

    def __init__(self) -> None:
        self._specs: dict[str, MaintenanceSkillSpec] = {}
        self._executors: dict[str, SkillExecuteFn] = {}

    def register(
        self,
        spec: MaintenanceSkillSpec,
        execute_fn: SkillExecuteFn,
    ) -> None:
        if not _SKILL_ID_RE.match(spec.id):
            raise ValueError(f"Invalid skill ID {spec.id!r}. Must match ^[a-z][a-z0-9_]{{2,63}}$")
        if spec.id in self._specs:
            raise ValueError(f"Skill {spec.id!r} already registered")
        self._specs[spec.id] = spec
        self._executors[spec.id] = execute_fn

    def get_spec(self, skill_id: str) -> MaintenanceSkillSpec | None:
        return self._specs.get(skill_id)

    def list_specs(self) -> list[MaintenanceSkillSpec]:
        return sorted(self._specs.values(), key=lambda s: s.id)

    def execute(self, skill_id: str, ctx: MaintenanceContext) -> MaintenanceSkillResult:
        from portfolio_manager.maintenance_models import MaintenanceSkillResult

        if skill_id not in self._executors:
            return MaintenanceSkillResult(
                skill_id=skill_id,
                project_id=ctx.project.id,
                status="blocked",
                findings=[],
                summary=f"Unknown skill: {skill_id}",
                reason="skill_not_registered",
            )
        return self._executors[skill_id](ctx)


# Module-level singleton
REGISTRY = _Registry()


def get_registry() -> _Registry:
    """Return the global maintenance skill registry."""
    return REGISTRY
