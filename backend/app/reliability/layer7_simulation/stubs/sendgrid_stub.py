"""SendGrid API stubs — email send, contacts, templates."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Send email (v3 Mail Send) ────────────────────────────
        StubMapping(
            method="POST",
            path="/v3/mail/send",
            status=202,
            response_body={},
            response_headers={
                "Content-Type": "application/json",
                "X-Message-Id": "mock-sendgrid-msg-001",
            },
        ),
        # ── Marketing: add contacts ──────────────────────────────
        StubMapping(
            method="PUT",
            path="/v3/marketing/contacts",
            status=202,
            response_body={
                "job_id": "mock-job-001",
            },
        ),
        # ── Templates: list ──────────────────────────────────────
        StubMapping(
            method="GET",
            path="/v3/templates",
            status=200,
            response_body={
                "result": [
                    {
                        "id": "tmpl_mock_001",
                        "name": "Welcome Email",
                        "generation": "dynamic",
                    }
                ],
            },
        ),
        # ── Templates: get single ────────────────────────────────
        StubMapping(
            method="GET",
            path="/v3/templates/:id",
            status=200,
            response_body={
                "id": "tmpl_mock_001",
                "name": "Welcome Email",
                "generation": "dynamic",
                "versions": [
                    {
                        "id": "ver_mock_001",
                        "template_id": "tmpl_mock_001",
                        "active": 1,
                        "name": "v1",
                        "subject": "Welcome!",
                    }
                ],
            },
        ),
        # ── Stats: global ────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/v3/stats",
            status=200,
            response_body=[
                {
                    "date": "2025-01-01",
                    "stats": [
                        {
                            "metrics": {
                                "requests": 100,
                                "delivered": 95,
                                "opens": 50,
                                "clicks": 20,
                            }
                        }
                    ],
                }
            ],
        ),
    ]
