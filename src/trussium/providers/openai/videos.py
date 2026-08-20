"""OpenAI video job adapter."""

from openai import APIError, AsyncOpenAI
from openai._types import omit
from openai.types.video import Video

from trussium.capabilities.videos import VideoCreateRequest, VideoJob
from trussium.observability.propagation import outbound_trace_context_headers
from trussium.providers.openai.chat import OpenAIChatCapability


class OpenAIVideoCapability:
    provider_name = "openai"

    def __init__(self, client: AsyncOpenAI) -> None:
        self._client = client

    async def create(self, request: VideoCreateRequest) -> VideoJob:
        try:
            video = await self._client.videos.create(
                model=request.model,
                prompt=request.prompt,
                seconds=request.seconds if request.seconds is not None else omit,
                size=request.size if request.size is not None else omit,
                extra_headers=outbound_trace_context_headers(),
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        return self._normalize(video)

    async def retrieve(self, video_id: str) -> VideoJob:
        try:
            video = await self._client.videos.retrieve(
                video_id, extra_headers=outbound_trace_context_headers()
            )
        except APIError as error:
            raise OpenAIChatCapability._normalize_api_error(error) from error
        return self._normalize(video)

    def _normalize(self, video: Video) -> VideoJob:
        return VideoJob(
            id=video.id,
            provider=self.provider_name,
            model=str(video.model),
            status=video.status,
            progress=video.progress,
            seconds=str(video.seconds),
            size=str(video.size),
        )
