"""Tests for Layer 7 — WireMock External Service Simulation."""
from __future__ import annotations

import asyncio
import json

import aiohttp
import pytest

from app.reliability.layer7_simulation.wiremock_manager import (
    RecordedCall,
    StubMapping,
    WireMockManager,
    detect_required_services,
)
from app.reliability.layer7_simulation.stubs import (
    anthropic_stub,
    openai_stub,
    resend_stub,
    sendgrid_stub,
    stripe_stub,
    twilio_stub,
)


# ── Stub registry tests ─────────────────────────────────────────


class TestStubModules:
    def test_stripe_stubs_exist(self):
        stubs = stripe_stub.get_stubs()
        assert len(stubs) >= 5
        assert all(isinstance(s, StubMapping) for s in stubs)

    def test_resend_stubs_exist(self):
        stubs = resend_stub.get_stubs()
        assert len(stubs) >= 3
        assert all(isinstance(s, StubMapping) for s in stubs)

    def test_openai_stubs_exist(self):
        stubs = openai_stub.get_stubs()
        assert len(stubs) >= 3
        paths = [s.path for s in stubs]
        assert "/v1/chat/completions" in paths
        assert "/v1/embeddings" in paths

    def test_anthropic_stubs_exist(self):
        stubs = anthropic_stub.get_stubs()
        assert len(stubs) >= 2
        assert any(s.path == "/v1/messages" for s in stubs)

    def test_twilio_stubs_exist(self):
        stubs = twilio_stub.get_stubs()
        assert len(stubs) >= 3

    def test_sendgrid_stubs_exist(self):
        stubs = sendgrid_stub.get_stubs()
        assert len(stubs) >= 3
        assert any(s.path == "/v3/mail/send" for s in stubs)

    def test_all_stubs_have_valid_methods(self):
        valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
        for module in [stripe_stub, resend_stub, openai_stub, anthropic_stub, twilio_stub, sendgrid_stub]:
            for stub in module.get_stubs():
                assert stub.method.upper() in valid_methods, f"Invalid method {stub.method} in {module.__name__}"

    def test_all_stubs_have_paths(self):
        for module in [stripe_stub, resend_stub, openai_stub, anthropic_stub, twilio_stub, sendgrid_stub]:
            for stub in module.get_stubs():
                assert stub.path.startswith("/"), f"Path must start with / in {module.__name__}"


# ── WireMockManager unit tests ──────────────────────────────────


class TestWireMockManagerUnit:
    def test_default_base_url(self):
        wm = WireMockManager()
        assert wm.base_url == "http://127.0.0.1:8089"

    def test_custom_port(self):
        wm = WireMockManager(port=9999)
        assert wm.base_url == "http://127.0.0.1:9999"

    def test_not_running_initially(self):
        wm = WireMockManager()
        assert wm.is_running is False

    def test_calls_empty_initially(self):
        wm = WireMockManager()
        assert wm.calls == []

    def test_reset(self):
        wm = WireMockManager()
        wm._stubs.append(StubMapping(method="GET", path="/test"))
        wm._calls.append(RecordedCall("GET", "/test", "", "", "/test"))
        wm.reset()
        assert len(wm._stubs) == 0
        assert len(wm._calls) == 0

    def test_path_matches_exact(self):
        assert WireMockManager._path_matches("/v1/charges", "/v1/charges") is True
        assert WireMockManager._path_matches("/v1/charges", "/v1/customers") is False

    def test_path_matches_wildcard(self):
        assert WireMockManager._path_matches("/v1/*", "/v1/charges") is True
        assert WireMockManager._path_matches("/v1/*", "/v2/charges") is False

    def test_path_matches_param(self):
        assert WireMockManager._path_matches("/v1/customers/:id", "/v1/customers/cus_123") is True
        assert WireMockManager._path_matches("/v1/customers/:id", "/v1/customers/cus_abc") is True
        assert WireMockManager._path_matches("/v1/customers/:id", "/v1/orders/ord_1") is False

    def test_body_matches(self):
        assert WireMockManager._body_matches({"key": True}, '{"key": true, "other": 1}') is True
        assert WireMockManager._body_matches({"missing": True}, '{"key": true}') is False
        assert WireMockManager._body_matches({"key": True}, "not json") is False

    def test_find_stub(self):
        wm = WireMockManager()
        wm._stubs = [
            StubMapping(method="POST", path="/v1/charges", status=200, response_body={"id": "ch_1"}),
            StubMapping(method="GET", path="/v1/models", status=200, response_body={}),
        ]
        assert wm._find_stub("POST", "/v1/charges", "") is not None
        assert wm._find_stub("GET", "/v1/models", "") is not None
        assert wm._find_stub("DELETE", "/v1/charges", "") is None
        assert wm._find_stub("GET", "/v1/unknown", "") is None


# ── WireMockManager integration tests (real HTTP) ───────────────


class TestWireMockManagerIntegration:
    """Tests that start/stop the actual HTTP server."""

    @pytest.fixture
    async def wiremock(self):
        """Start WireMock on a random high port, stop in finally."""
        wm = WireMockManager(port=18089)
        await wm.start()
        try:
            yield wm
        finally:
            await wm.stop()

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        wm = WireMockManager(port=18090)
        assert wm.is_running is False
        await wm.start()
        assert wm.is_running is True
        await wm.stop()
        assert wm.is_running is False

    @pytest.mark.asyncio
    async def test_stop_idempotent(self):
        """stop() on a non-running manager should not error."""
        wm = WireMockManager(port=18091)
        await wm.stop()  # Should not raise
        assert wm.is_running is False

    @pytest.mark.asyncio
    async def test_non_stubbed_returns_404(self, wiremock: WireMockManager):
        """Non-stubbed endpoint → 404 (no internet pass-through)."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{wiremock.base_url}/v1/unknown/endpoint") as resp:
                assert resp.status == 404
                body = await resp.json()
                assert body["error"] == "not_stubbed"

    @pytest.mark.asyncio
    async def test_stubbed_returns_configured_response(self, wiremock: WireMockManager):
        wiremock._stubs = [
            StubMapping(
                method="POST",
                path="/v1/charges",
                status=200,
                response_body={"id": "ch_test", "status": "succeeded"},
            ),
        ]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{wiremock.base_url}/v1/charges",
                json={"amount": 2000},
            ) as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["id"] == "ch_test"
                assert body["status"] == "succeeded"

    @pytest.mark.asyncio
    async def test_calls_recorded(self, wiremock: WireMockManager):
        wiremock._stubs = [
            StubMapping(method="GET", path="/v1/models", status=200, response_body={}),
        ]

        async with aiohttp.ClientSession() as session:
            await session.get(f"{wiremock.base_url}/v1/models")
            await session.get(f"{wiremock.base_url}/v1/unknown")

        assert len(wiremock.calls) == 2
        assert wiremock.calls[0].matched_stub == "/v1/models"
        assert wiremock.calls[1].matched_stub is None

    @pytest.mark.asyncio
    async def test_verify_all_calls_pass(self, wiremock: WireMockManager):
        wiremock._stubs = [
            StubMapping(method="GET", path="/test", status=200, response_body={}),
        ]

        async with aiohttp.ClientSession() as session:
            await session.get(f"{wiremock.base_url}/test")

        result = await wiremock.verify_all_calls()
        assert result["passed"] is True
        assert result["total_calls"] == 1
        assert result["unmatched"] == 0

    @pytest.mark.asyncio
    async def test_verify_all_calls_fail_unmatched(self, wiremock: WireMockManager):
        """Unmatched calls cause verify to fail."""
        async with aiohttp.ClientSession() as session:
            await session.get(f"{wiremock.base_url}/no/stub/here")

        result = await wiremock.verify_all_calls()
        assert result["passed"] is False
        assert result["unmatched"] == 1

    @pytest.mark.asyncio
    async def test_configure_stubs_with_services(self, wiremock: WireMockManager):
        await wiremock.configure_stubs(["stripe", "openai"])
        assert len(wiremock._stubs) > 0

        # Stripe charge should work
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{wiremock.base_url}/v1/charges",
                json={"amount": 1000},
            ) as resp:
                assert resp.status == 200
                body = await resp.json()
                assert "id" in body

    @pytest.mark.asyncio
    async def test_configure_stubs_unknown_service(self, wiremock: WireMockManager):
        """Unknown services should not error, just log warning."""
        await wiremock.configure_stubs(["nonexistent_service"])
        assert len(wiremock._stubs) == 0

    @pytest.mark.asyncio
    async def test_stop_in_finally_always_called(self):
        """Simulates pipeline failure — stop() still runs."""
        wm = WireMockManager(port=18092)
        try:
            await wm.start()
            assert wm.is_running is True
            raise RuntimeError("Simulated pipeline failure")
        except RuntimeError:
            pass
        finally:
            await wm.stop()

        assert wm.is_running is False

    @pytest.mark.asyncio
    async def test_param_path_matching(self, wiremock: WireMockManager):
        wiremock._stubs = [
            StubMapping(
                method="GET",
                path="/v1/customers/:id",
                status=200,
                response_body={"id": "cus_mock"},
            ),
        ]

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{wiremock.base_url}/v1/customers/cus_abc123") as resp:
                assert resp.status == 200
                body = await resp.json()
                assert body["id"] == "cus_mock"

    @pytest.mark.asyncio
    async def test_body_contains_matching(self, wiremock: WireMockManager):
        wiremock._stubs = [
            StubMapping(
                method="POST",
                path="/v1/messages",
                status=200,
                body_contains={"stream": True},
                response_body={"id": "streamed"},
            ),
            StubMapping(
                method="POST",
                path="/v1/messages",
                status=200,
                response_body={"id": "normal"},
            ),
        ]

        async with aiohttp.ClientSession() as session:
            # With stream=True → first stub matches
            async with session.post(
                f"{wiremock.base_url}/v1/messages",
                json={"stream": True, "model": "claude-3"},
            ) as resp:
                body = await resp.json()
                assert body["id"] == "streamed"

            # Without stream → second stub
            async with session.post(
                f"{wiremock.base_url}/v1/messages",
                json={"model": "claude-3"},
            ) as resp:
                body = await resp.json()
                assert body["id"] == "normal"


# ── detect_required_services tests ───────────────────────────────


class TestDetectRequiredServices:
    def test_detects_stripe(self):
        state = {"comprehensive_plan": {"features": ["payment processing with Stripe"]}}
        services = detect_required_services(state)
        assert "stripe" in services

    def test_detects_openai(self):
        state = {"comprehensive_plan": {"features": ["GPT-4 chatbot"]}}
        services = detect_required_services(state)
        assert "openai" in services

    def test_detects_anthropic(self):
        state = {"comprehensive_plan": {"features": ["Claude assistant"]}}
        services = detect_required_services(state)
        assert "anthropic" in services

    def test_detects_twilio(self):
        state = {"comprehensive_plan": {"features": ["SMS notifications via Twilio"]}}
        services = detect_required_services(state)
        assert "twilio" in services

    def test_detects_resend(self):
        state = {"comprehensive_plan": {"features": ["transactional email with Resend"]}}
        services = detect_required_services(state)
        assert "resend" in services

    def test_detects_sendgrid(self):
        state = {"comprehensive_plan": {"features": ["SendGrid email campaigns"]}}
        services = detect_required_services(state)
        assert "sendgrid" in services

    def test_detects_from_generated_files(self):
        state = {
            "comprehensive_plan": {},
            "generated_files": {
                "src/api/payments.ts": "import Stripe from 'stripe';",
            },
        }
        services = detect_required_services(state)
        assert "stripe" in services

    def test_detects_multiple_services(self):
        state = {
            "comprehensive_plan": {
                "features": ["Stripe payments", "OpenAI chat", "Twilio SMS"],
            },
        }
        services = detect_required_services(state)
        assert "stripe" in services
        assert "openai" in services
        assert "twilio" in services

    def test_empty_state(self):
        services = detect_required_services({})
        assert services == []

    def test_returns_sorted(self):
        state = {"comprehensive_plan": {"features": ["Twilio SMS, Stripe billing, OpenAI GPT-4"]}}
        services = detect_required_services(state)
        assert services == sorted(services)
