"""Resend API stubs — transactional email."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Send email ───────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/emails",
            status=200,
            response_body={
                "id": "email_mock_001",
                "from": "noreply@forge.dev",
                "to": ["test@example.com"],
                "created_at": "2025-01-01T00:00:00.000Z",
            },
        ),
        # ── Get email ────────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/emails/:id",
            status=200,
            response_body={
                "id": "email_mock_001",
                "from": "noreply@forge.dev",
                "to": ["test@example.com"],
                "subject": "Mock subject",
                "created_at": "2025-01-01T00:00:00.000Z",
                "last_event": "delivered",
            },
        ),
        # ── Batch send ───────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/emails/batch",
            status=200,
            response_body={
                "data": [
                    {"id": "email_mock_002"},
                    {"id": "email_mock_003"},
                ],
            },
        ),
        # ── Domains ──────────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/domains",
            status=200,
            response_body={
                "data": [
                    {
                        "id": "domain_mock_001",
                        "name": "forge.dev",
                        "status": "verified",
                    }
                ]
            },
        ),
        # ── API Keys ─────────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/api-keys",
            status=200,
            response_body={
                "data": [
                    {
                        "id": "key_mock_001",
                        "name": "Mock Key",
                        "created_at": "2025-01-01T00:00:00.000Z",
                    }
                ]
            },
        ),
    ]
