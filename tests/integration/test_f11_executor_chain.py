"""Regression tests for executor input resolution across capabilities (F11).

Covers the compiled-plan execution path: Pipeline -> Planner -> ExecutionPlan
-> Executor -> providers, with real provider discovery and a real local HTTP
fetch. The prior knowledge-slice test invoked providers directly; this test
exercises reference resolution, single-to-list coercion, nested output paths,
and abort semantics through the executor.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from mirror_core.application import Application
from mirror_core.settings import MirrorSettings

PAGE = b"<html><head><title>Doc</title></head><body><h1>Hello Mirror</h1><p>alpha content here</p><p>more words</p></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *args: object) -> None:
        pass


async def _chain_run(url: str) -> object:
    app = Application(MirrorSettings())
    await app.start()
    try:
        from mirror_core.pipeline import Pipeline

        pipeline = Pipeline.model_validate(
            {
                "id": "knowledge-chain",
                "version": "1.0",
                "inputs": {"url": "str"},
                "steps": [
                    {
                        "id": "fetch_page",
                        "capability": "fetch",
                        "input": {"url": "$pipeline.url"},
                        "outputs": ["result"],
                    },
                    {
                        "id": "make_docs",
                        "capability": "transform",
                        "input": {
                            "value": "fetch_page.result",
                            "output_type": "mirror_chunk.models:ChunkDocument",
                            "mapping": {
                                "document_id": "url",
                                "text": "content",
                                "metadata": {"src": "url"},
                            },
                        },
                        "outputs": ["result"],
                    },
                    {
                        "id": "split_chunks",
                        "capability": "chunk",
                        "input": {"documents": "make_docs.value"},
                        "outputs": ["result"],
                    },
                ],
            }
        )
        return await app.run_pipeline_detailed(pipeline, inputs={"url": url})
    finally:
        await app.shutdown()


async def test_multi_capability_chain_runs_through_executor() -> None:
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        host, port = server.server_address
        result = await _chain_run(f"http://{host}:{port}/")
    finally:
        server.shutdown()

    assert result.outcome.value == "succeeded"
    assert result.states["fetch_page"].value == "succeeded"
    assert result.states["make_docs"].value == "succeeded"
    assert result.states["split_chunks"].value == "succeeded"
    assert not result.errors

    transformed = result.results["make_docs"].payload.value
    assert transformed.document_id == f"http://{host}:{port}/"
    assert isinstance(transformed.text, str)
    assert "Hello Mirror" in transformed.text
    assert transformed.metadata["src"] == f"http://{host}:{port}/"

    chunks = result.results["split_chunks"].payload.chunks
    assert chunks
    assert all(chunk.document_id == transformed.document_id for chunk in chunks)
    assert all("mirror" in chunk.text.lower() for chunk in chunks)


async def test_step_failure_aborts_without_leaking_cancelled_error() -> None:
    """A failing step must cancel siblings and finish with a failure outcome.

    Previously the sibling-cancellation from an abort re-raised
    ``asyncio.CancelledError`` out of ``execute_run``, masking the real step
    error with an unhandled exception.
    """
    app = Application(MirrorSettings())
    await app.start()
    try:
        from mirror_core.pipeline import Pipeline

        pipeline = Pipeline.model_validate(
            {
                "id": "abort-chain",
                "version": "1.0",
                "inputs": {"text": "str"},
                "steps": [
                    {
                        "id": "ok_step",
                        "capability": "transform",
                        "input": {
                            "value": "hello world",
                            "output_type": "mirror_chunk.models:ChunkDocument",
                            "mapping": {
                                "document_id": "ok",
                                "text": "hello world",
                            },
                        },
                        "outputs": ["result"],
                    },
                    {
                        "id": "fail_step",
                        "capability": "transform",
                        "input": {
                            "value": "$pipeline.text",
                            "output_type": "does_not.exist:Model",
                            "mapping": {"document_id": "x"},
                        },
                        "outputs": ["result"],
                    },
                ],
            }
        )
        result = await app.run_pipeline_detailed(pipeline, inputs={"text": "boom"})
    finally:
        await app.shutdown()

    assert result.outcome.value in {"failed", "partially_succeeded"}
    assert result.states["fail_step"].value == "failed"
    assert "fail_step" in result.errors
