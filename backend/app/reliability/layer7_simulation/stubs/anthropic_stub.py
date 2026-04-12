"""Anthropic API stubs — messages."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Messages ─────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/messages",
            status=200,
            response_body={
                "id": "msg_mock001",
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "Mock response from Anthropic Claude.",
                    }
                ],
                "model": "claude-3-opus-20240229",
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 20,
                },
            },
        ),
        # ── Messages (streaming) ─────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/messages",
            status=200,
            body_contains={"stream": True},
            response_body={
                "id": "msg_mock002",
                "type": "message",
                "role": "assistant",
                "content": [{"type": "text", "text": "Streamed mock."}],
                "model": "claude-3-opus-20240229",
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        ),
        # ── Count tokens ─────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v1/messages/count_tokens",
            status=200,
            response_body={"input_tokens": 42},
        ),
    ]
