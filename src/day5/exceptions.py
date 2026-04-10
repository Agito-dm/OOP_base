from __future__ import annotations

from src.day1.exceptions.exceptions import InvalidOperationError


class HighRiskOperationError(InvalidOperationError):
    """Операция заблокирована из-за высокого риска."""
