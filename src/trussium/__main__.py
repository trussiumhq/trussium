"""Trussium runtime entry point."""

from pydantic import ValidationError

from trussium.app import create_application
from trussium.app.bootstrap import (
    create_batch_capability_from_environment,
    create_chat_capability_from_environment,
    create_embeddings_capability_from_environment,
    create_image_generation_capability_from_environment,
    create_moderation_capability_from_environment,
    create_provider_health_check_from_environment,
    create_reranking_capability_from_environment,
    create_transcription_capability_from_environment,
    create_video_capability_from_environment,
)
from trussium.capabilities import (
    BATCHES_CAPABILITY_METADATA,
    BATCHES_CAPABILITY_NAME,
    CHAT_CAPABILITY_METADATA,
    CHAT_CAPABILITY_NAME,
    EMBEDDINGS_CAPABILITY_METADATA,
    EMBEDDINGS_CAPABILITY_NAME,
    IMAGE_GENERATION_CAPABILITY_METADATA,
    IMAGE_GENERATION_CAPABILITY_NAME,
    MODERATION_CAPABILITY_METADATA,
    MODERATION_CAPABILITY_NAME,
    RERANKING_CAPABILITY_METADATA,
    RERANKING_CAPABILITY_NAME,
    TRANSCRIPTION_CAPABILITY_METADATA,
    TRANSCRIPTION_CAPABILITY_NAME,
    VIDEO_CAPABILITY_METADATA,
    VIDEO_CAPABILITY_NAME,
    CapabilityRegistry,
)
from trussium.config.settings import get_settings
from trussium.observability import (
    RUNTIME_CONFIGURATION_INVALID,
    RuntimeTracing,
    configure_logging,
    get_logger,
)
from trussium.runtime.server import create_server


def main() -> None:
    """Start the Trussium runtime."""
    configure_logging()

    try:
        settings = get_settings()
    except ValidationError as error:
        get_logger("runtime").error(
            "Runtime configuration is invalid",
            extra={
                "event": RUNTIME_CONFIGURATION_INVALID,
                "error_code": "invalid_configuration",
                "error_count": error.error_count(),
                "error_type": type(error).__name__,
            },
        )
        raise SystemExit(2) from None

    configure_logging(
        debug=settings.runtime.debug,
    )
    tracing = RuntimeTracing(settings.observability)
    chat_capability = create_chat_capability_from_environment(
        provider=settings.provider,
        timeouts=settings.timeouts,
        tracer=tracing.tracer,
    )
    batch_capability = create_batch_capability_from_environment(provider=settings.provider)
    embeddings_capability = create_embeddings_capability_from_environment(
        provider=settings.provider,
    )
    image_generation_capability = create_image_generation_capability_from_environment(
        provider=settings.provider
    )
    moderation_capability = create_moderation_capability_from_environment(
        provider=settings.provider
    )
    reranking_capability = create_reranking_capability_from_environment(
        reranking=settings.reranking
    )
    transcription_capability = create_transcription_capability_from_environment(
        provider=settings.provider
    )
    video_capability = create_video_capability_from_environment(provider=settings.provider)
    dependency_health_check = create_provider_health_check_from_environment(
        provider=settings.provider,
        readiness=settings.readiness,
    )
    capability_registry = CapabilityRegistry()
    if chat_capability is not None:
        capability_registry.register(
            CHAT_CAPABILITY_NAME,
            chat_capability,
            metadata=CHAT_CAPABILITY_METADATA,
        )
    if batch_capability is not None:
        capability_registry.register(
            BATCHES_CAPABILITY_NAME,
            batch_capability,
            metadata=BATCHES_CAPABILITY_METADATA,
        )
    if embeddings_capability is not None:
        capability_registry.register(
            EMBEDDINGS_CAPABILITY_NAME,
            embeddings_capability,
            metadata=EMBEDDINGS_CAPABILITY_METADATA,
        )
    if image_generation_capability is not None:
        capability_registry.register(
            IMAGE_GENERATION_CAPABILITY_NAME,
            image_generation_capability,
            metadata=IMAGE_GENERATION_CAPABILITY_METADATA,
        )
    if moderation_capability is not None:
        capability_registry.register(
            MODERATION_CAPABILITY_NAME,
            moderation_capability,
            metadata=MODERATION_CAPABILITY_METADATA,
        )
    if reranking_capability is not None:
        capability_registry.register(
            RERANKING_CAPABILITY_NAME,
            reranking_capability,
            metadata=RERANKING_CAPABILITY_METADATA,
        )
    if transcription_capability is not None:
        capability_registry.register(
            TRANSCRIPTION_CAPABILITY_NAME,
            transcription_capability,
            metadata=TRANSCRIPTION_CAPABILITY_METADATA,
        )
    if video_capability is not None:
        capability_registry.register(
            VIDEO_CAPABILITY_NAME,
            video_capability,
            metadata=VIDEO_CAPABILITY_METADATA,
        )

    app = create_application(
        settings=settings,
        capability_registry=capability_registry,
        tracing=tracing,
        dependency_health_check=dependency_health_check,
    )

    server = create_server(
        app,
        settings=settings.runtime,
    )
    server.run()


if __name__ == "__main__":
    main()
