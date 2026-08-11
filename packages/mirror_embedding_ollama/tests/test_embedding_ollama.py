"""Tests for the Ollama embedding provider.

Categories:
  1. Always-run: settings defaults, httpx request building (mocked at HTTP level),
     error handling.
  2. Server-dependent: require a running Ollama server; skipped when unreachable.
"""

from __future__ import annotations

import math

import httpx
import pytest

from mirror_embedding.models import EmbeddingInput, EmbeddingRequest
from mirror_embedding_ollama.provider import OllamaEmbeddingProvider
from mirror_embedding_ollama.settings import OllamaEmbeddingSettings

# ---------------------------------------------------------------------------
# Server-dependent helpers
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://localhost:11434"


def _ollama_reachable() -> bool:
    """Return True if an Ollama server is reachable at the default address."""
    try:
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except httpx.ConnectError:
        return False


_server = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="Ollama server not reachable at localhost:11434",
)


# ---------------------------------------------------------------------------
# Always-run tests: settings
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    """Verify OllamaEmbeddingSettings defaults."""

    def test_default_base_url(self) -> None:
        settings = OllamaEmbeddingSettings()
        assert settings.base_url == "http://localhost:11434"

    def test_default_model(self) -> None:
        settings = OllamaEmbeddingSettings()
        assert settings.model == "nomic-embed-text"

    def test_default_timeout(self) -> None:
        settings = OllamaEmbeddingSettings()
        assert settings.timeout == 30.0

    def test_inherits_dimension(self) -> None:
        settings = OllamaEmbeddingSettings()
        assert settings.dimension == 64

    def test_inherits_normalize(self) -> None:
        settings = OllamaEmbeddingSettings()
        assert settings.normalize is True

    def test_custom_settings(self) -> None:
        settings = OllamaEmbeddingSettings(
            base_url="http://remote:9999",
            model="all-minilm",
            timeout=10.0,
            dimension=128,
            normalize=False,
        )
        assert settings.base_url == "http://remote:9999"
        assert settings.model == "all-minilm"
        assert settings.timeout == 10.0
        assert settings.dimension == 128
        assert settings.normalize is False


# ---------------------------------------------------------------------------
# Always-run tests: request building (mocked at HTTP level)
# ---------------------------------------------------------------------------


def _mock_response(
    embedding: list[float], status_code: int = 200, text: str = ""
) -> httpx.Response:
    """Build a fake httpx.Response with the given embedding payload."""
    import json

    return httpx.Response(
        status_code=status_code,
        json={"embedding": embedding},
        request=httpx.Request("POST", "http://localhost:11434/api/embeddings"),
    )


class TestRequestBuilding:
    """Verify the provider issues correct HTTP requests (mocked at HTTP level)."""

    @pytest.mark.asyncio
    async def test_single_item_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify a single-item embed builds the right payload."""
        captured_requests: list[httpx.Request] = []

        fake_embedding = [0.1, 0.2, 0.3, 0.4]

        async def _mock_send(
            request: httpx.Request, **kwargs: object  # noqa: ANN001
        ) -> httpx.Response:
            captured_requests.append(request)
            return _mock_response(fake_embedding)

        settings = OllamaEmbeddingSettings(dimension=8)
        provider = OllamaEmbeddingProvider(settings)

        # Inject mock client
        mock_client = httpx.AsyncClient()
        mock_client.send = _mock_send  # type: ignore[attr-defined]
        provider._client = mock_client

        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="a", text="hello world")]
        )
        result = await provider.embed(request)

        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert "/api/embeddings" in str(req.url)

        import json

        body = json.loads(req.content)
        assert body["model"] == "nomic-embed-text"
        assert body["prompt"] == "hello world"
        assert len(result.vectors) == 1
        assert result.vectors[0].item_id == "a"
        assert result.vectors[0].values == tuple(fake_embedding)

    @pytest.mark.asyncio
    async def test_batch_items_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify multiple items each produce a separate HTTP call."""
        call_count = 0

        async def _mock_send(
            request: httpx.Request, **kwargs: object  # noqa: ANN001
        ) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _mock_response([0.1] * 8)

        settings = OllamaEmbeddingSettings(dimension=8)
        provider = OllamaEmbeddingProvider(settings)
        mock_client = httpx.AsyncClient()
        mock_client.send = _mock_send  # type: ignore[attr-defined]
        provider._client = mock_client

        request = EmbeddingRequest(
            items=[
                EmbeddingInput(item_id="x", text="first"),
                EmbeddingInput(item_id="y", text="second"),
                EmbeddingInput(item_id="z", text="third"),
            ]
        )
        result = await provider.embed(request)

        assert call_count == 3
        assert len(result.vectors) == 3
        assert [v.item_id for v in result.vectors] == ["x", "y", "z"]

    @pytest.mark.asyncio
    async def test_metadata_preserved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify item metadata flows through to the embedding vector."""

        async def _mock_send(
            request: httpx.Request, **kwargs: object  # noqa: ANN001
        ) -> httpx.Response:
            return _mock_response([1.0, 0.0])

        settings = OllamaEmbeddingSettings(dimension=8)
        provider = OllamaEmbeddingProvider(settings)
        mock_client = httpx.AsyncClient()
        mock_client.send = _mock_send  # type: ignore[attr-defined]
        provider._client = mock_client

        request = EmbeddingRequest(
            items=[
                EmbeddingInput(
                    item_id="m",
                    text="test",
                    metadata={"source": "doc", "page": 1},
                )
            ]
        )
        result = await provider.embed(request)

        vec = result.vectors[0]
        assert vec.metadata == {"source": "doc", "page": 1}


# ---------------------------------------------------------------------------
# Always-run tests: error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Verify the provider raises clear errors on failure."""

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        """Verify ConnectionError is raised when Ollama is unreachable."""
        settings = OllamaEmbeddingSettings(
            base_url="http://127.0.0.1:1"  # closed port → ConnectError
        )
        provider = OllamaEmbeddingProvider(settings)

        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="e", text="test")]
        )

        with pytest.raises(ConnectionError, match="Could not connect to Ollama"):
            await provider.embed(request)

    @pytest.mark.asyncio
    async def test_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify RuntimeError is raised on HTTP 500 from Ollama."""

        async def _mock_send(
            request: httpx.Request, **kwargs: object  # noqa: ANN001
        ) -> httpx.Response:
            return httpx.Response(
                status_code=500,
                text="internal server error",
                request=httpx.Request("POST", "http://localhost:11434/api/embeddings"),
            )

        settings = OllamaEmbeddingSettings()
        provider = OllamaEmbeddingProvider(settings)
        mock_client = httpx.AsyncClient()
        mock_client.send = _mock_send  # type: ignore[attr-defined]
        provider._client = mock_client

        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="e", text="test")]
        )

        with pytest.raises(RuntimeError, match="Ollama API returned HTTP 500"):
            await provider.embed(request)

    @pytest.mark.asyncio
    async def test_missing_embedding_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify KeyError when response lacks 'embedding' key."""

        async def _mock_send(
            request: httpx.Request, **kwargs: object  # noqa: ANN001
        ) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                json={"unexpected": "format"},
                request=httpx.Request("POST", "http://localhost:11434/api/embeddings"),
            )

        settings = OllamaEmbeddingSettings()
        provider = OllamaEmbeddingProvider(settings)
        mock_client = httpx.AsyncClient()
        mock_client.send = _mock_send  # type: ignore[attr-defined]
        provider._client = mock_client

        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="e", text="test")]
        )

        with pytest.raises(KeyError, match="embedding"):
            await provider.embed(request)


# ---------------------------------------------------------------------------
# Server-dependent tests: real Ollama backend
# ---------------------------------------------------------------------------


@_server
class TestRealOllamaBackend:
    """Real-backend integration tests against a running Ollama server."""

    @pytest.mark.asyncio
    async def test_embed_returns_vectors(self) -> None:
        """Verify real embedding produces non-empty vectors."""
        provider = OllamaEmbeddingProvider(
            OllamaEmbeddingSettings(model="nomic-embed-text")
        )
        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="r1", text="Hello, world!")]
        )
        result = await provider.embed(request)

        assert len(result.vectors) == 1
        vec = result.vectors[0]
        assert vec.item_id == "r1"
        assert len(vec.values) > 0
        assert all(isinstance(v, float) for v in vec.values)

    @pytest.mark.asyncio
    async def test_vector_dimension(self) -> None:
        """Verify the vector dimension is reasonable (nomic-embed-text = 768)."""
        provider = OllamaEmbeddingProvider(
            OllamaEmbeddingSettings(model="nomic-embed-text")
        )
        request = EmbeddingRequest(
            items=[EmbeddingInput(item_id="r2", text="Test dimension")]
        )
        result = await provider.embed(request)

        assert len(result.vectors[0].values) == 768

    @pytest.mark.asyncio
    async def test_batch_embed(self) -> None:
        """Verify batch embedding produces one vector per input."""
        provider = OllamaEmbeddingProvider()
        request = EmbeddingRequest(
            items=[
                EmbeddingInput(item_id="b1", text="First"),
                EmbeddingInput(item_id="b2", text="Second"),
            ]
        )
        result = await provider.embed(request)

        assert len(result.vectors) == 2
        assert result.vectors[0].item_id == "b1"
        assert result.vectors[1].item_id == "b2"
        # Different text should produce different vectors
        assert result.vectors[0].values != result.vectors[1].values
