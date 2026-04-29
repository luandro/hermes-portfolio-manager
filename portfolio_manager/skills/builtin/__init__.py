"""Built-in maintenance skills — self-registering on import."""

from __future__ import annotations

import contextlib


def register_all() -> None:
    """Import all built-in skill modules so they self-register with REGISTRY."""
    from portfolio_manager.skills.builtin import (  # noqa: F401
        open_pr_health,
        repo_guidance_docs,
        stale_issue_digest,
        untriaged_issue_digest,
    )


with contextlib.suppress(ValueError):
    register_all()
