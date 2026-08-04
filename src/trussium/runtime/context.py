"""Request-scoped runtime context."""

from contextvars import ContextVar, Token

_request_id_context: ContextVar[str | None] = ContextVar(
    "trussium_request_id",
    default=None,
)


def get_request_id() -> str | None:
    """Return the request identifier active in the current context.

    Returns:
        The active request identifier, or ``None`` when no request
        context is active.
    """
    return _request_id_context.get()


def set_request_id(
    request_id: str,
) -> Token[str | None]:
    """Set the request identifier for the current context.

    Args:
        request_id: Request identifier to make active.

    Returns:
        Context token used to restore the previous value.
    """
    return _request_id_context.set(request_id)


def reset_request_id(
    token: Token[str | None],
) -> None:
    """Restore the previous request identifier context.

    Args:
        token: Token returned by :func:`set_request_id`.
    """
    _request_id_context.reset(token)
