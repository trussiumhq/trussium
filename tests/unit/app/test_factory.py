import io
import json
from collections.abc import AsyncIterator
from typing import cast
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from trussium.app import create_application
from trussium.capabilities import (
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    CapabilityAvailabilityReporter,
    CapabilityContractMismatchError,
    CapabilityExecuteNext,
    CapabilityExecutionPipeline,
    CapabilityInvocation,
    CapabilityLifecycle,
    CapabilityLifecycleError,
    CapabilityMetadata,
    CapabilityMiddleware,
    CapabilityRegistry,
    CapabilityRegistrySealedError,
    CapabilityStreamNext,
)
from trussium.capabilities.chat import ChatCapability
from trussium.config.settings import RuntimeSettings, Settings
from trussium.observability import (
    LoggingChatCapability,
    RuntimeTracing,
    configure_logging,
)
from trussium.runtime import (
    DependencyHealth,
    DependencyStatus,
    RuntimeComponentHealthReporter,
    RuntimeServiceLifecycle,
    RuntimeServiceLifecycleError,
    RuntimeServiceRegistry,
    RuntimeServiceRegistrySealedError,
)
from trussium.workflows import WorkflowLifecycle, WorkflowLifecycleState


class StubRuntimeService:
    """Application-scoped service used to verify lifespan integration."""

    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        startup_error: Exception | None = None,
        shutdown_error: Exception | None = None,
    ) -> None:
        """Initialize controllable hook behavior."""
        self.name = name
        self.events = events
        self.startup_error = startup_error
        self.shutdown_error = shutdown_error

    async def startup(self) -> None:
        """Record application startup."""
        self.events.append(f"start:{self.name}")
        if self.startup_error is not None:
            raise self.startup_error

    async def shutdown(self) -> None:
        """Record application shutdown."""
        self.events.append(f"stop:{self.name}")
        if self.shutdown_error is not None:
            raise self.shutdown_error


class StubLifecycleCapability:
    """Registered capability that records application lifecycle ownership."""

    def __init__(
        self,
        name: str,
        events: list[str],
        *,
        startup_error: Exception | None = None,
        shutdown_error: Exception | None = None,
    ) -> None:
        """Initialize controllable hook behavior."""
        self.name = name
        self.events = events
        self.startup_error = startup_error
        self.shutdown_error = shutdown_error

    async def startup(self) -> None:
        """Record capability startup."""
        self.events.append(f"start:{self.name}")
        if self.startup_error is not None:
            raise self.startup_error

    async def shutdown(self) -> None:
        """Record capability shutdown."""
        self.events.append(f"stop:{self.name}")
        if self.shutdown_error is not None:
            raise self.shutdown_error


class StubDependencyHealthCheck:
    """Dependency check that records app-owned resource cleanup."""

    name = "provider"
    provider = "openai"
    model = None

    def __init__(self, events: list[str]) -> None:
        """Initialize cleanup event recording."""
        self.events = events

    async def check(self) -> DependencyHealth:
        """Return a healthy result when evaluated."""
        return DependencyHealth(
            name=self.name,
            status=DependencyStatus.OK,
            provider=self.provider,
            model=self.model,
        )

    async def close(self) -> None:
        """Record dependency resource cleanup."""
        self.events.append("stop:dependency")


class PassThroughCapabilityMiddleware:
    """Continue both capability execution modes without changing values."""

    async def execute(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityExecuteNext,
    ) -> object:
        """Continue non-streaming execution."""
        _ = invocation
        return await call_next()

    def stream(
        self,
        invocation: CapabilityInvocation,
        call_next: CapabilityStreamNext,
    ) -> AsyncIterator[object]:
        """Continue streaming execution."""
        _ = invocation
        return call_next()


def test_create_application_returns_fastapi() -> None:
    app = create_application()

    assert isinstance(app, FastAPI)


def test_application_contains_settings() -> None:
    app = create_application()

    assert isinstance(app.state.settings, Settings)


def test_application_debug_matches_settings() -> None:
    settings = Settings()

    app = create_application(settings)

    assert app.debug is settings.runtime.debug


def test_application_title() -> None:
    app = create_application()

    assert app.title == "Trussium"


def test_application_lifespan_manages_ordered_runtime_services() -> None:
    """The app factory should expose and execute its immutable lifecycle plan."""
    events: list[str] = []
    first = StubRuntimeService("first", events)
    second = StubRuntimeService("second", events)
    settings = Settings(
        runtime=RuntimeSettings(
            service_cleanup_seconds=2.5,
            component_health_timeout_seconds=0.75,
        )
    )

    app = create_application(
        settings,
        runtime_services=(first, second),
    )

    assert isinstance(app.state.runtime_service_lifecycle, RuntimeServiceLifecycle)
    assert isinstance(app.state.runtime_service_registry, RuntimeServiceRegistry)
    assert app.state.runtime_service_registry.sealed is True
    assert app.state.runtime_service_registry.services == (first, second)
    assert isinstance(
        app.state.runtime_component_health_reporter,
        RuntimeComponentHealthReporter,
    )
    assert app.state.runtime_component_health_reporter.registry is (
        app.state.runtime_service_registry
    )
    assert app.state.runtime_component_health_reporter.timeout_seconds == 0.75
    assert app.state.runtime_service_lifecycle.services == (first, second)
    assert app.state.runtime_service_lifecycle.cleanup_timeout_seconds == 2.5

    with TestClient(app) as client:
        assert app.state.runtime_service_lifecycle.state.value == "started"
        assert client.get("/health/live").status_code == 200

    assert app.state.runtime_service_lifecycle.state.value == "stopped"
    assert events == ["start:first", "start:second", "stop:second", "stop:first"]


def test_application_drains_workflows_before_lifespan_shutdown() -> None:
    workflow_lifecycle = WorkflowLifecycle()
    app = create_application(workflow_lifecycle=workflow_lifecycle)

    assert app.state.workflow_lifecycle is workflow_lifecycle
    assert workflow_lifecycle.state is WorkflowLifecycleState.RUNNING
    with TestClient(app):
        assert workflow_lifecycle.state is WorkflowLifecycleState.RUNNING
    assert workflow_lifecycle.state.value == WorkflowLifecycleState.STOPPED.value


def test_application_uses_injected_runtime_service_registry() -> None:
    """An injected registry should be sealed and own the lifecycle snapshot."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    registry = RuntimeServiceRegistry((service,))

    app = create_application(runtime_service_registry=registry)

    assert app.state.runtime_service_registry is registry
    assert registry.sealed is True
    assert app.state.runtime_service_lifecycle.services == (service,)
    with pytest.raises(RuntimeServiceRegistrySealedError):
        registry.register(StubRuntimeService("later", events))

    with TestClient(app):
        pass

    assert events == ["start:service", "stop:service"]


def test_application_manages_capabilities_between_services_and_resources() -> None:
    """Capabilities should occupy a deterministic application ownership layer."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    first = StubLifecycleCapability("first", events)
    second = StubLifecycleCapability("second", events)
    ordinary = object()
    registry = CapabilityRegistry()
    registry.register("first", first)
    registry.register("ordinary", ordinary)
    registry.register("second", second)
    dependency_check = StubDependencyHealthCheck(events)
    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    tracing.shutdown.side_effect = lambda: events.append("stop:tracing")
    settings = Settings(
        runtime=RuntimeSettings(
            service_cleanup_seconds=2.5,
            capability_availability_timeout_seconds=0.625,
            capability_health_timeout_seconds=0.5,
        )
    )

    app = create_application(
        settings,
        capability_registry=registry,
        runtime_services=(service,),
        dependency_health_check=dependency_check,
        tracing=cast(RuntimeTracing, tracing),
    )

    assert isinstance(app.state.capability_lifecycle, CapabilityLifecycle)
    assert isinstance(
        app.state.capability_availability_reporter,
        CapabilityAvailabilityReporter,
    )
    assert app.state.capability_availability_reporter.registry is registry
    assert app.state.capability_availability_reporter.timeout_seconds == 0.625
    assert app.state.capability_health_reporter.registry is registry
    assert app.state.capability_health_reporter.timeout_seconds == 0.5
    assert app.state.capability_lifecycle.names == ("first", "second")
    assert app.state.capability_lifecycle.cleanup_timeout_seconds == 2.5
    assert tuple(
        registration.capability for registration in app.state.capability_lifecycle.registrations
    ) == (first, second)

    with TestClient(app):
        assert app.state.capability_lifecycle.state.value == "started"

    assert app.state.capability_lifecycle.state.value == "stopped"
    assert events == [
        "start:service",
        "start:first",
        "start:second",
        "stop:second",
        "stop:first",
        "stop:service",
        "stop:dependency",
        "stop:tracing",
    ]


def test_capability_startup_failure_still_stops_started_runtime_services() -> None:
    """A failed capability startup must not leak earlier application resources."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    first = StubLifecycleCapability("first", events)
    failed = StubLifecycleCapability(
        "failed",
        events,
        startup_error=RuntimeError("private capability startup detail"),
    )
    registry = CapabilityRegistry()
    registry.register("first", first)
    registry.register("failed", failed)

    app = create_application(
        capability_registry=registry,
        runtime_services=(service,),
    )

    with pytest.raises(CapabilityLifecycleError), TestClient(app):
        pass

    assert events == [
        "start:service",
        "start:first",
        "start:failed",
        "stop:first",
        "stop:service",
    ]
    assert app.state.capability_lifecycle.state.value == "failed"
    assert app.state.runtime_service_lifecycle.state.value == "stopped"


def test_capability_shutdown_failure_does_not_skip_remaining_cleanup() -> None:
    """A capability hook failure should surface after all resource cleanup."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    failed = StubLifecycleCapability(
        "failed",
        events,
        shutdown_error=RuntimeError("private capability shutdown detail"),
    )
    registry = CapabilityRegistry()
    registry.register("failed", failed)
    dependency_check = StubDependencyHealthCheck(events)
    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    tracing.shutdown.side_effect = lambda: events.append("stop:tracing")
    app = create_application(
        capability_registry=registry,
        runtime_services=(service,),
        dependency_health_check=dependency_check,
        tracing=cast(RuntimeTracing, tracing),
    )

    with pytest.raises(CapabilityLifecycleError), TestClient(app):
        pass

    assert events == [
        "start:service",
        "start:failed",
        "stop:failed",
        "stop:service",
        "stop:dependency",
        "stop:tracing",
    ]
    assert app.state.capability_lifecycle.state.value == "failed"
    assert app.state.runtime_service_lifecycle.state.value == "stopped"


def test_application_rejects_registry_and_raw_services_before_sealing() -> None:
    """Ambiguous composition must not mutate a caller-owned registry."""
    events: list[str] = []
    configured = StubRuntimeService("configured", events)
    supplied = StubRuntimeService("supplied", events)
    registry = RuntimeServiceRegistry((configured,))

    with pytest.raises(ValueError, match="mutually exclusive"):
        create_application(
            runtime_services=(supplied,),
            runtime_service_registry=registry,
        )

    assert registry.sealed is False
    assert registry.services == (configured,)


def test_application_default_registries_are_isolated() -> None:
    """Separate application composition roots must not share registry state."""
    first_app = create_application()
    second_app = create_application()

    assert first_app.state.runtime_service_registry is not second_app.state.runtime_service_registry
    assert first_app.state.runtime_service_registry.services == ()
    assert second_app.state.runtime_service_registry.services == ()
    assert first_app.state.capability_registry is not second_app.state.capability_registry
    assert first_app.state.capability_registry.registrations == ()
    assert second_app.state.capability_registry.registrations == ()
    assert first_app.state.capability_registry.sealed is True
    assert second_app.state.capability_registry.sealed is True
    assert first_app.state.capability_availability_reporter is not (
        second_app.state.capability_availability_reporter
    )
    assert isinstance(
        first_app.state.capability_execution_pipeline,
        CapabilityExecutionPipeline,
    )
    assert isinstance(
        second_app.state.capability_execution_pipeline,
        CapabilityExecutionPipeline,
    )
    assert first_app.state.capability_execution_pipeline is not (
        second_app.state.capability_execution_pipeline
    )
    assert first_app.state.capability_execution_pipeline.registry is (
        first_app.state.capability_registry
    )
    assert second_app.state.capability_execution_pipeline.registry is (
        second_app.state.capability_registry
    )
    assert first_app.state.capability_execution_pipeline.middleware == ()
    assert second_app.state.capability_execution_pipeline.middleware == ()


def test_application_composes_an_isolated_capability_middleware_snapshot() -> None:
    """Application pipelines should retain only their configured middleware."""
    middleware = PassThroughCapabilityMiddleware()
    configured: list[CapabilityMiddleware] = [middleware]

    first_app = create_application(capability_middleware=configured)
    configured.clear()
    second_app = create_application()

    assert first_app.state.capability_execution_pipeline.middleware == (middleware,)
    assert second_app.state.capability_execution_pipeline.middleware == ()
    assert first_app.state.capability_execution_pipeline is not (
        second_app.state.capability_execution_pipeline
    )


def test_application_startup_failure_runs_runtime_resource_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed service startup should still close app-scoped tracing safely."""
    output = io.StringIO()

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    events: list[str] = []
    service = StubRuntimeService(
        "failed",
        events,
        startup_error=RuntimeError("private startup detail"),
    )
    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    monkeypatch.setattr(
        "trussium.app.factory.configure_logging",
        configure_test_logging,
    )
    app = create_application(
        Settings(),
        tracing=cast(RuntimeTracing, tracing),
        runtime_services=(service,),
    )

    with pytest.raises(RuntimeServiceLifecycleError), TestClient(app):
        pass

    tracing.shutdown.assert_called_once_with()
    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert "runtime.started" not in [payload.get("event") for payload in payloads]
    stopped = next(payload for payload in payloads if payload.get("event") == "runtime.stopped")
    assert stopped["outcome"] == "failed"
    assert "private startup detail" not in output.getvalue()


def test_runtime_services_preserve_dependency_then_tracing_cleanup_order() -> None:
    """New hooks should run before the established app resource shutdown order."""
    events: list[str] = []
    service = StubRuntimeService("service", events)
    dependency_check = StubDependencyHealthCheck(events)
    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    tracing.shutdown.side_effect = lambda: events.append("stop:tracing")
    app = create_application(
        Settings(),
        tracing=cast(RuntimeTracing, tracing),
        dependency_health_check=dependency_check,
        runtime_services=(service,),
    )

    with TestClient(app):
        pass

    assert events == [
        "start:service",
        "stop:service",
        "stop:dependency",
        "stop:tracing",
    ]


def test_application_wraps_configured_chat_capability_with_logging() -> None:
    capability = cast(
        ChatCapability,
        MagicMock(spec=ChatCapability),
    )

    app = create_application(
        chat_capability=capability,
    )

    assert isinstance(
        app.state.chat_capability,
        LoggingChatCapability,
    )
    assert app.state.capability_registry.sealed is True
    assert app.state.capability_registry.names == (CHAT_CAPABILITY_NAME,)
    assert app.state.capability_registry.metadata == (CHAT_CAPABILITY_METADATA,)
    assert app.state.capability_registry.get(CHAT_CAPABILITY_NAME) is (app.state.chat_capability)
    assert app.state.capability_execution_pipeline.registry is app.state.capability_registry


def test_application_does_not_wrap_logging_capability_twice() -> None:
    capability = cast(
        ChatCapability,
        MagicMock(spec=ChatCapability),
    )
    logging_capability = LoggingChatCapability(capability)

    app = create_application(
        chat_capability=logging_capability,
    )

    assert app.state.chat_capability is logging_capability
    assert app.state.capability_registry.get(CHAT_CAPABILITY_NAME) is logging_capability


def test_application_composes_an_injected_capability_registry() -> None:
    """Registered capabilities should become one sealed application-owned snapshot."""
    future_capability = object()
    future_metadata = CapabilityMetadata(
        name="future.embeddings",
        version="v1",
        description="Create normalized embeddings.",
        supports_streaming=False,
    )
    chat_capability = cast(ChatCapability, MagicMock(spec=ChatCapability))
    registry = CapabilityRegistry()
    registry.register(
        "future.embeddings",
        future_capability,
        metadata=future_metadata,
    )
    registry.register(CHAT_CAPABILITY_NAME, chat_capability)

    app = create_application(capability_registry=registry)

    assert registry.sealed is True
    assert app.state.capability_availability_reporter.registry is registry
    assert app.state.capability_availability_reporter.timeout_seconds == 1.0
    assert app.state.capability_registry is not registry
    assert app.state.capability_registry.sealed is True
    assert app.state.capability_registry.names == (
        "future.embeddings",
        CHAT_CAPABILITY_NAME,
    )
    assert app.state.capability_registry.get("future.embeddings") is future_capability
    assert app.state.capability_registry.metadata == (
        future_metadata,
        CHAT_CAPABILITY_METADATA,
    )
    resolved_chat = app.state.capability_registry.get(CHAT_CAPABILITY_NAME)
    assert isinstance(resolved_chat, LoggingChatCapability)
    assert app.state.chat_capability is resolved_chat
    assert app.state.capability_execution_pipeline.registry is app.state.capability_registry

    with pytest.raises(CapabilityRegistrySealedError):
        registry.register("later", object())
    with pytest.raises(CapabilityRegistrySealedError):
        app.state.capability_registry.register("later", object())


def test_application_rejects_ambiguous_capability_composition_before_sealing() -> None:
    """Legacy and registry inputs should not silently compete for chat identity."""
    registry = CapabilityRegistry()
    chat_capability = cast(ChatCapability, MagicMock(spec=ChatCapability))

    with pytest.raises(ValueError, match="mutually exclusive"):
        create_application(
            chat_capability=chat_capability,
            capability_registry=registry,
        )

    assert registry.sealed is False
    assert registry.registrations == ()


def test_application_rejects_registered_chat_contract_mismatch_safely() -> None:
    """A known identity must implement its public provider-neutral protocol."""
    private_capability = object()
    registry = CapabilityRegistry()
    registry.register(CHAT_CAPABILITY_NAME, private_capability)

    with pytest.raises(CapabilityContractMismatchError) as captured:
        create_application(capability_registry=registry)

    error = captured.value
    assert registry.sealed is True
    assert error.capability_name == CHAT_CAPABILITY_NAME
    assert error.code == "capability_contract_mismatch"
    assert "object at" not in error.message


def test_application_lifespan_emits_ordered_operational_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Application startup and shutdown should expose the stable event contract."""
    output = io.StringIO()

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    monkeypatch.setattr(
        "trussium.app.factory.configure_logging",
        configure_test_logging,
    )
    app = create_application(Settings())

    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    events = [payload.get("event") for payload in payloads]
    lifecycle_events = [
        event
        for event in events
        if event
        in {
            "runtime.configuration.loaded",
            "provider.configuration.unavailable",
            "observability.configuration.loaded",
            "runtime.started",
            "runtime.stopping",
            "observability.tracing.shutdown.completed",
            "runtime.stopped",
        }
    ]

    assert lifecycle_events == [
        "runtime.configuration.loaded",
        "provider.configuration.unavailable",
        "observability.configuration.loaded",
        "runtime.started",
        "runtime.stopping",
        "observability.tracing.shutdown.completed",
        "runtime.stopped",
    ]
    stopped = next(payload for payload in payloads if payload.get("event") == "runtime.stopped")
    assert stopped["outcome"] == "completed"
    assert isinstance(stopped["duration_ms"], float)


def test_tracing_shutdown_failure_is_bounded_and_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shutdown exception should be logged safely and still reach the caller."""
    output = io.StringIO()

    def configure_test_logging(**_: object) -> None:
        configure_logging(stream=output)

    tracing = MagicMock(spec=RuntimeTracing)
    tracing.enabled = False
    tracing.shutdown.side_effect = RuntimeError("secret shutdown detail")
    monkeypatch.setattr(
        "trussium.app.factory.configure_logging",
        configure_test_logging,
    )
    app = create_application(
        Settings(),
        tracing=cast(RuntimeTracing, tracing),
    )

    with pytest.raises(RuntimeError, match="secret shutdown detail"), TestClient(app) as client:
        assert client.get("/health/live").status_code == 200

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    failure = next(
        payload
        for payload in payloads
        if payload.get("event") == "observability.tracing.shutdown.failed"
    )
    stopped = next(payload for payload in payloads if payload.get("event") == "runtime.stopped")
    assert failure["error_code"] == "tracing_shutdown_failed"
    assert failure["error_type"] == "RuntimeError"
    assert "exception" not in failure
    assert stopped["outcome"] == "failed"
    assert "secret shutdown detail" not in output.getvalue()
