"""Request and execution-scoped runtime context."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Metadata associated with an active runtime execution."""

    request_id: str | None = None
    execution_id: str | None = None
    capability: str | None = None
    provider: str | None = None
    model: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None


_execution_context: ContextVar[ExecutionContext | None] = ContextVar(
    "trussium_execution_context",
    default=None,
)


def get_execution_context() -> ExecutionContext:
    """Return the execution context active in the current scope.

    Returns:
        Active execution context.
    """
    return _execution_context.get() or ExecutionContext()


def get_request_id() -> str | None:
    """Return the active request identifier.

    Returns:
        Active request identifier, or ``None`` when no request
        context is active.
    """
    return get_execution_context().request_id


def generate_execution_id() -> str:
    """Generate a runtime execution identifier.

    Returns:
        UUID execution identifier.
    """
    return str(uuid4())


def set_execution_context(
    context: ExecutionContext,
) -> Token[ExecutionContext | None]:
    """Set the active execution context.

    Args:
        context: Context to make active.

    Returns:
        Token used to restore the previous context.
    """
    return _execution_context.set(context)


def reset_execution_context(
    token: Token[ExecutionContext | None],
) -> None:
    """Restore the previous execution context.

    Args:
        token: Token returned by :func:`set_execution_context`.
    """
    _execution_context.reset(token)


def set_request_id(
    request_id: str,
    *,
    execution_id: str | None = None,
    tenant_id: str | None = None,
    project_id: str | None = None,
) -> Token[ExecutionContext | None]:
    """Set request-level runtime context.

    Args:
        request_id: Request identifier to make active.
        execution_id: Optional execution identifier. A UUID is generated
            when one is not supplied.

    Returns:
        Token used to restore the previous context.
    """
    current_context = get_execution_context()

    context = replace(
        current_context,
        request_id=request_id,
        execution_id=execution_id or generate_execution_id(),
        tenant_id=tenant_id if tenant_id is not None else current_context.tenant_id,
        project_id=project_id if project_id is not None else current_context.project_id,
    )

    return set_execution_context(context)


def reset_request_id(
    token: Token[ExecutionContext | None],
) -> None:
    """Restore the runtime context active before request processing.

    Args:
        token: Token returned by :func:`set_request_id`.
    """
    reset_execution_context(token)


@contextmanager
def bind_execution_context(
    *,
    capability: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    execution_id: str | None = None,
    tenant_id: str | None = None,
    project_id: str | None = None,
) -> Iterator[ExecutionContext]:
    """Temporarily enrich the active execution context.

    Args:
        capability: Optional capability identifier.
        provider: Optional provider identifier.
        model: Optional model identifier.
        execution_id: Optional replacement execution identifier.

    Yields:
        Enriched execution context.
    """
    current_context = get_execution_context()

    bound_context = replace(
        current_context,
        execution_id=execution_id or current_context.execution_id,
        capability=(capability if capability is not None else current_context.capability),
        provider=(provider if provider is not None else current_context.provider),
        model=(model if model is not None else current_context.model),
        tenant_id=(tenant_id if tenant_id is not None else current_context.tenant_id),
        project_id=(project_id if project_id is not None else current_context.project_id),
    )

    token = set_execution_context(bound_context)

    try:
        yield bound_context
    finally:
        reset_execution_context(token)
