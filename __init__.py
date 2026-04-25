"""Hermes plugin entry point — re-exports register() from the package."""

from portfolio_manager import register

__all__ = ["register"]
