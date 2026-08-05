"""Tests for request and execution-scoped runtime context."""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from trussium.runtime import (
    ExecutionContext,
    bind_execution_context,
    generate_execution_id,
    get_execution_context,
    get_request_id,
    reset_execution_context,
    reset_request_id,
    set_execution_context,
    set_request_id,
)


def test_execution_context_defaults_to_empty_metadata() -> None:
    """The default context should not contain execution metadata."""
    assert get_execution_context() == ExecutionContext()
    assert get_request_id() is None


def test_execution_context_is_immutable() -> None:
    """Execution metadata should not be mutable after construction."""
    context = ExecutionContext(
        request_id="request-123",
    )

    with pytest.raises(FrozenInstanceError):
        context.__setattr__("request_id", "request-456")


def test_generate_execution_id_returns_uuid() -> None:
    """Generated execution identifiers should be unique UUID values."""
    first_execution_id = generate_execution_id()
    second_execution_id = generate_execution_id()

    assert str(UUID(first_execution_id)) == first_execution_id
    assert str(UUID(second_execution_id)) == second_execution_id
    assert first_execution_id != second_execution_id


def test_execution_context_can_be_set_and_reset() -> None:
    """The previous execution context should be restored by its token."""
    context = ExecutionContext(
        request_id="request-123",
        execution_id="execution-123",
        capability="chat.completions",
        provider="openai",
        model="gpt-5.6",
    )
    token = set_execution_context(context)

    try:
        assert get_execution_context() is context
    finally:
        reset_execution_context(token)

    assert get_execution_context() == ExecutionContext()


def test_set_request_id_generates_execution_id() -> None:
    """Request context should include an automatically generated execution ID."""
    token = set_request_id("request-123")

    try:
        context = get_execution_context()

        assert get_request_id() == "request-123"
        assert context.request_id == "request-123"
        assert context.execution_id is not None
        assert str(UUID(context.execution_id)) == context.execution_id
    finally:
        reset_request_id(token)

    assert get_execution_context() == ExecutionContext()


def test_set_request_id_accepts_execution_id() -> None:
    """A supplied execution identifier should be preserved."""
    token = set_request_id(
        "request-123",
        execution_id="execution-123",
    )

    try:
        assert get_execution_context().execution_id == "execution-123"
    finally:
        reset_request_id(token)


def test_set_request_id_preserves_bound_metadata() -> None:
    """Setting a request ID should retain metadata from the parent context."""
    with bind_execution_context(
        capability="chat.completions",
        provider="openai",
        model="gpt-5.6",
    ):
        token = set_request_id(
            "request-123",
            execution_id="execution-123",
        )

        try:
            assert get_execution_context() == ExecutionContext(
                request_id="request-123",
                execution_id="execution-123",
                capability="chat.completions",
                provider="openai",
                model="gpt-5.6",
            )
        finally:
            reset_request_id(token)


def test_bind_execution_context_enriches_and_restores_context() -> None:
    """Bound metadata should preserve request fields and restore its parent."""
    parent_context = ExecutionContext(
        request_id="request-123",
        execution_id="execution-123",
    )
    token = set_execution_context(parent_context)

    try:
        with bind_execution_context(
            capability="chat.completions",
            provider="openai",
            model="gpt-5.6",
        ) as bound_context:
            assert bound_context == ExecutionContext(
                request_id="request-123",
                execution_id="execution-123",
                capability="chat.completions",
                provider="openai",
                model="gpt-5.6",
            )
            assert get_execution_context() is bound_context

        assert get_execution_context() is parent_context
    finally:
        reset_execution_context(token)


def test_nested_execution_context_inherits_unspecified_fields() -> None:
    """Nested bindings should inherit fields that they do not replace."""
    with bind_execution_context(
        capability="chat.completions",
        provider="openai",
        model="gpt-5.6",
        execution_id="execution-parent",
    ):
        with bind_execution_context(
            model="gpt-5.6-mini",
            execution_id="execution-child",
        ) as child_context:
            assert child_context == ExecutionContext(
                execution_id="execution-child",
                capability="chat.completions",
                provider="openai",
                model="gpt-5.6-mini",
            )

        assert get_execution_context().execution_id == "execution-parent"
        assert get_execution_context().model == "gpt-5.6"


def test_execution_context_is_restored_after_exception() -> None:
    """A binding should restore its parent when execution raises."""
    parent_context = get_execution_context()

    with (
        pytest.raises(RuntimeError, match="test failure"),
        bind_execution_context(
            capability="chat.completions",
        ),
    ):
        raise RuntimeError("test failure")

    assert get_execution_context() == parent_context


def test_execution_context_propagates_across_await_boundaries() -> None:
    """The active context should remain available after awaiting."""

    async def read_context() -> ExecutionContext:
        await asyncio.sleep(0)
        return get_execution_context()

    async def run() -> ExecutionContext:
        with bind_execution_context(
            capability="chat.completions",
            execution_id="execution-123",
        ):
            return await read_context()

    assert asyncio.run(run()) == ExecutionContext(
        execution_id="execution-123",
        capability="chat.completions",
    )


def test_execution_context_propagates_to_created_tasks() -> None:
    """Tasks created within a binding should inherit its execution context."""

    async def read_context() -> ExecutionContext:
        await asyncio.sleep(0)
        return get_execution_context()

    async def run() -> ExecutionContext:
        with bind_execution_context(
            provider="openai",
            execution_id="execution-123",
        ):
            task = asyncio.create_task(read_context())

        return await task

    assert asyncio.run(run()) == ExecutionContext(
        execution_id="execution-123",
        provider="openai",
    )
    assert get_execution_context() == ExecutionContext()


def test_execution_context_propagates_through_async_generators() -> None:
    """Async generators should retain context across yield and await boundaries."""

    async def generate_contexts() -> list[ExecutionContext]:
        contexts: list[ExecutionContext] = []

        async def generate() -> AsyncIterator[ExecutionContext]:
            yield get_execution_context()
            await asyncio.sleep(0)
            yield get_execution_context()

        with bind_execution_context(
            model="gpt-5.6",
            execution_id="execution-123",
        ):
            async for context in generate():
                assert isinstance(context, ExecutionContext)
                contexts.append(context)

        return contexts

    expected_context = ExecutionContext(
        execution_id="execution-123",
        model="gpt-5.6",
    )

    assert asyncio.run(generate_contexts()) == [
        expected_context,
        expected_context,
    ]
