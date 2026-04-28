"""Built-in maintenance skills — self-registering on import."""

from __future__ import annotations


def register_all() -> None:
    """Import all built-in skill modules so they self-register with REGISTRY."""
    from portfolio_manager.skills.builtin import (  # noqa: F401
        dependency_audit,
        health_check,
        license_compliance,
        security_advisory,
        stale_branches,
    )


register_all()
