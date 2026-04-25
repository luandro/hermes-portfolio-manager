"""Custom error types for the Portfolio Manager plugin."""

from __future__ import annotations

import re


def redact_secrets(text: str) -> str:
    """Redact known secret/token patterns from a string.

    Replaces the secret value with ``***`` while preserving the token prefix
    (e.g. ``ghp_abc123`` → ``ghp_***``).

    Handled patterns:
    - GitHub personal access tokens: ``ghp_``, ``gho_``, ``ghu_``, ``ghs_``
    - GitHub fine-grained tokens: ``github_pat_``
    - Bearer tokens in headers: ``Bearer <token>``
    - Generic ``token=<value>`` patterns
    """
    patterns: list[tuple[str, str]] = [
        (r"(github_pat_)\S+", r"\1***"),
        (r"(gh[ousp]_)\S+", r"\1***"),
        (r"Bearer\s+\S+", "Bearer ***"),
        (r"(token=)\S+", r"\1***"),
    ]
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result
