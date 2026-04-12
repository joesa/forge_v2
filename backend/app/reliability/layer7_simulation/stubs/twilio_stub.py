"""Twilio API stubs — SMS, voice, verify."""
from __future__ import annotations

from app.reliability.layer7_simulation.wiremock_manager import StubMapping


def get_stubs() -> list[StubMapping]:
    return [
        # ── Send SMS ─────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/2010-04-01/Accounts/:sid/Messages.json",
            status=201,
            response_body={
                "sid": "SM_mock_001",
                "status": "queued",
                "to": "+15551234567",
                "from": "+15559876543",
                "body": "Mock SMS",
                "date_created": "2025-01-01T00:00:00Z",
            },
        ),
        # ── Get message ──────────────────────────────────────────
        StubMapping(
            method="GET",
            path="/2010-04-01/Accounts/:sid/Messages/:msg_sid.json",
            status=200,
            response_body={
                "sid": "SM_mock_001",
                "status": "delivered",
                "to": "+15551234567",
            },
        ),
        # ── Verify: start ────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v2/Services/:sid/Verifications",
            status=201,
            response_body={
                "sid": "VE_mock_001",
                "status": "pending",
                "to": "+15551234567",
                "channel": "sms",
            },
        ),
        # ── Verify: check ────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/v2/Services/:sid/VerificationCheck",
            status=200,
            response_body={
                "sid": "VE_mock_001",
                "status": "approved",
                "to": "+15551234567",
                "valid": True,
            },
        ),
        # ── Make call ────────────────────────────────────────────
        StubMapping(
            method="POST",
            path="/2010-04-01/Accounts/:sid/Calls.json",
            status=201,
            response_body={
                "sid": "CA_mock_001",
                "status": "queued",
                "to": "+15551234567",
                "from": "+15559876543",
            },
        ),
    ]
