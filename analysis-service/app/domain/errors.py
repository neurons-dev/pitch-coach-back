from __future__ import annotations


class AnalysisError(Exception):
    def __init__(self, *, code: str, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class IdempotencyKeyConflictError(ValueError):
    """The same idempotency key was reused for a different request."""


class RepositoryTimeoutError(TimeoutError):
    """A repository operation exhausted its caller-provided time budget."""
