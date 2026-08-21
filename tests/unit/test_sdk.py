import httpx
import pytest

from trussium.sdk import TrussiumClient, TrussiumClientError


def test_readiness_uses_configured_runtime_url() -> None:
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"status": "ok"})),
    )
    assert client.readiness() == {"status": "ok"}
    client.close()


def test_transport_errors_are_normalized() -> None:
    client = TrussiumClient("http://runtime")
    client._client = httpx.Client(
        base_url="http://runtime",
        transport=httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(httpx.ConnectError("unavailable"))
        ),
    )
    with pytest.raises(TrussiumClientError):
        client.capabilities()
    client.close()
