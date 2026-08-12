"""OpenAI-compatible provider dependency health checking."""

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
)

from trussium.runtime import (
    DependencyFailureReason,
    DependencyHealth,
    DependencyStatus,
)


class OpenAICompatibleProviderHealthCheck:
    """Validate provider metadata access without executing inference."""

    name = "provider"

    def __init__(
        self,
        client: AsyncOpenAI,
        *,
        provider: str,
        model: str | None = None,
    ) -> None:
        """Initialize the provider client and bounded identity."""
        self._client = client
        self._provider = provider
        self._model = model

    @property
    def provider(self) -> str:
        """Return the configured provider identifier."""
        return self._provider

    @property
    def model(self) -> str | None:
        """Return the optional required model."""
        return self._model

    async def check(self) -> DependencyHealth:
        """Validate model metadata access and normalize every provider failure."""
        try:
            if self.model is None:
                await self._client.models.list()
            else:
                await self._client.models.retrieve(self.model)
        except AuthenticationError:
            return self._unavailable(DependencyFailureReason.PROVIDER_AUTHENTICATION_FAILED)
        except PermissionDeniedError:
            return self._unavailable(DependencyFailureReason.PROVIDER_PERMISSION_DENIED)
        except RateLimitError:
            return self._unavailable(DependencyFailureReason.PROVIDER_RATE_LIMITED)
        except APITimeoutError:
            return self._unavailable(DependencyFailureReason.PROVIDER_TIMEOUT)
        except APIConnectionError:
            return self._unavailable(DependencyFailureReason.PROVIDER_UNREACHABLE)
        except NotFoundError:
            reason = (
                DependencyFailureReason.MODEL_UNAVAILABLE
                if self.model is not None
                else DependencyFailureReason.PROVIDER_CHECK_FAILED
            )
            return self._unavailable(reason)
        except APIError:
            return self._unavailable(DependencyFailureReason.PROVIDER_CHECK_FAILED)

        return DependencyHealth(
            name=self.name,
            status=DependencyStatus.OK,
            provider=self.provider,
            model=self.model,
        )

    async def close(self) -> None:
        """Close the provider client owned by this health check."""
        await self._client.close()

    def _unavailable(self, reason: DependencyFailureReason) -> DependencyHealth:
        """Build a bounded failure without raw provider details."""
        return DependencyHealth(
            name=self.name,
            status=DependencyStatus.UNAVAILABLE,
            provider=self.provider,
            model=self.model,
            reason=reason,
        )
