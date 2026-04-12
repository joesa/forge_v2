"""OpenAI API stubs — chat completions, embeddings, images."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Chat completions ─────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/chat/completions",
            status=200,
            response_body={
                "id": "chatcmpl-mock001",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Mock response from OpenAI.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
        ),
        # ── Embeddings ───────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/embeddings",
            status=200,
            response_body={
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": [0.001] * 1536,
                    }
                ],
                "model": "text-embedding-ada-002",
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        ),
        # ── Image generation ─────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/images/generations",
            status=200,
            response_body={
                "created": 1700000000,
                "data": [
                    {"url": "https://mock.openai.com/image.png"},
                ],
            },
        ),
        # ── Models list ──────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/v1/models",
            status=200,
            response_body={
                "object": "list",
                "data": [
                    {"id": "gpt-4", "object": "model", "owned_by": "openai"},
                    {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
                ],
            },
        ),
        # ── Moderations ──────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/moderations",
            status=200,
            response_body={
                "id": "modr-mock001",
                "model": "text-moderation-latest",
                "results": [{"flagged": False, "categories": {}, "category_scores": {}}],
            },
        ),
    ]
