from __future__ import annotations


def describe_exception(exc: BaseException | None) -> str:
    """예외를 오류 메시지와 로그 양쪽에 쓸 짧은 한 줄로 만든다.

    ValueError는 우리가 직접 만든 검증 메시지라 본문까지 붙이고, 그 외에는 타입
    이름만 남긴다. 특히 pydantic ValidationError는 모델 출력을 통째로 덤프하므로
    그대로 노출하면 안 된다(ValueError의 하위 타입이라 정확한 타입으로 비교한다).
    """
    if exc is None:
        return "알 수 없는 오류"
    name = type(exc).__name__
    if type(exc) is ValueError and str(exc):
        return f"{name}: {exc}"
    return name


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
