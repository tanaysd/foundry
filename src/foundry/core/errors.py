"""Custom exception types used by Foundry core utilities."""

from __future__ import annotations


class AdapterError(RuntimeError):
    """Raised when an adapter cannot fulfil a request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
