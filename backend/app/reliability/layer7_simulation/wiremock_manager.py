"""Layer 7 — WireMock Manager.

In-process HTTP mock server that intercepts all external API calls
during build. Non-stubbed endpoints return 404 (no internet pass-through).

Usage (always in try/finally):
    try:
        await wiremock_manager.start()
        await wiremock_manager.configure_stubs(services)
        os.environ["EXTERNAL_API_BASE_URL"] = wiremock_manager.base_url
        # ... run build agents ...
        await wiremock_manager.verify_all_calls()
    finally:
        await wiremock_manager.stop()
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from aiohttp import web

logger = logging.getLogger(__name__)


@dataclass
class StubMapping:
    """A single request→response stub."""

    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str  # URL path pattern, e.g. /v1/charges
    status: int = 200
    response_body: dict | str = field(default_factory=dict)
    response_headers: dict[str, str] = field(
        default_factory=lambda: {"Content-Type": "application/json"}
    )
    # If set, match only when request body contains these keys
    body_contains: dict[str, Any] | None = None


@dataclass
class RecordedCall:
    """A request that hit the mock server."""

    method: str
    path: str
    query: str
    body: str
    matched_stub: str | None  # stub path or None if 404


class WireMockManager:
    """In-process HTTP mock server for external service simulation.

    Non-stubbed endpoints always return 404. No internet pass-through.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8089

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._stubs: list[StubMapping] = []
        self._calls: list[RecordedCall] = []
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._started = False

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    @property
    def calls(self) -> list[RecordedCall]:
        return list(self._calls)

    @property
    def is_running(self) -> bool:
        return self._started

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the mock HTTP server."""
        if self._started:
            logger.warning("WireMock already running on %s", self.base_url)
            return

        self._app = web.Application()
        self._app.router.add_route("*", "/{path_info:.*}", self._handle_request)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        self._started = True

        logger.info("WireMock started on %s", self.base_url)

    async def stop(self) -> None:
        """Stop the mock HTTP server. MUST be called in finally block."""
        if not self._started:
            return

        try:
            if self._site:
                await self._site.stop()
            if self._runner:
                await self._runner.cleanup()
        except Exception:
            logger.exception("Error stopping WireMock")
        finally:
            self._app = None
            self._runner = None
            self._site = None
            self._started = False
            logger.info("WireMock stopped")

    async def configure_stubs(self, services: list[str]) -> None:
        """Configure stubs for the given service names.

        Args:
            services: List of service identifiers, e.g. ["stripe", "resend", "openai"]
        """
        from app.reliability.layer7_simulation.stubs import (
            anthropic_stub,
            openai_stub,
            resend_stub,
            sendgrid_stub,
            stripe_stub,
            twilio_stub,
        )

        _STUB_REGISTRY: dict[str, list[StubMapping]] = {
            "stripe": stripe_stub.get_stubs(),
            "resend": resend_stub.get_stubs(),
            "openai": openai_stub.get_stubs(),
            "anthropic": anthropic_stub.get_stubs(),
            "twilio": twilio_stub.get_stubs(),
            "sendgrid": sendgrid_stub.get_stubs(),
        }

        self._stubs.clear()
        loaded = 0
        for service in services:
            stubs = _STUB_REGISTRY.get(service)
            if stubs:
                self._stubs.extend(stubs)
                loaded += len(stubs)
                logger.info("Loaded %d stubs for %s", len(stubs), service)
            else:
                logger.warning("No stubs found for service: %s", service)

        logger.info("Configured %d total stubs for %d services", loaded, len(services))

    async def verify_all_calls(self) -> dict:
        """Verify all recorded calls matched a stub.

        Returns {
            "passed": bool,
            "total_calls": int,
            "matched": int,
            "unmatched": int,
            "unmatched_calls": [{"method", "path"}, ...],
        }
        """
        unmatched = [c for c in self._calls if c.matched_stub is None]

        result = {
            "passed": len(unmatched) == 0,
            "total_calls": len(self._calls),
            "matched": len(self._calls) - len(unmatched),
            "unmatched": len(unmatched),
            "unmatched_calls": [
                {"method": c.method, "path": c.path} for c in unmatched
            ],
        }

        if unmatched:
            logger.warning(
                "WireMock: %d unmatched calls out of %d",
                len(unmatched), len(self._calls),
            )
        else:
            logger.info("WireMock: all %d calls matched stubs", len(self._calls))

        return result

    def reset(self) -> None:
        """Clear all stubs and recorded calls."""
        self._stubs.clear()
        self._calls.clear()

    # ── Request handler ──────────────────────────────────────────

    async def _handle_request(self, request: web.Request) -> web.Response:
        """Handle incoming request. Non-stubbed → 404."""
        method = request.method
        path = "/" + request.match_info.get("path_info", "")
        query = request.query_string
        body = ""
        try:
            body = await request.text()
        except Exception:
            pass

        # Match against stubs
        matched = self._find_stub(method, path, body)

        self._calls.append(RecordedCall(
            method=method,
            path=path,
            query=query,
            body=body,
            matched_stub=matched.path if matched else None,
        ))

        if matched:
            resp_body = matched.response_body
            if isinstance(resp_body, dict):
                resp_body = json.dumps(resp_body)
            return web.Response(
                status=matched.status,
                text=resp_body,
                headers=matched.response_headers,
            )

        # Non-stubbed → 404, no internet pass-through
        logger.debug("WireMock 404: %s %s", method, path)
        return web.Response(
            status=HTTPStatus.NOT_FOUND,
            text=json.dumps({
                "error": "not_stubbed",
                "message": f"No stub configured for {method} {path}",
            }),
            headers={"Content-Type": "application/json"},
        )

    def _find_stub(self, method: str, path: str, body: str) -> StubMapping | None:
        """Find the first matching stub for a request."""
        for stub in self._stubs:
            if stub.method.upper() != method.upper():
                continue
            if not self._path_matches(stub.path, path):
                continue
            if stub.body_contains:
                if not self._body_matches(stub.body_contains, body):
                    continue
            return stub
        return None

    @staticmethod
    def _path_matches(pattern: str, actual: str) -> bool:
        """Check if path matches pattern. Supports simple prefix matching."""
        # Exact match
        if pattern == actual:
            return True
        # Pattern ends with * → prefix match
        if pattern.endswith("*"):
            return actual.startswith(pattern[:-1])
        # Pattern segments with wildcards
        pat_parts = pattern.strip("/").split("/")
        act_parts = actual.strip("/").split("/")
        if len(pat_parts) != len(act_parts):
            return False
        for pp, ap in zip(pat_parts, act_parts):
            if pp == "*":
                continue
            if pp.startswith(":"):
                continue
            if pp != ap:
                return False
        return True

    @staticmethod
    def _body_matches(expected: dict[str, Any], body: str) -> bool:
        """Check if request body contains expected keys."""
        try:
            parsed = json.loads(body)
            return all(k in parsed for k in expected)
        except (json.JSONDecodeError, TypeError):
            return False


# ── Service detection ────────────────────────────────────────────


def detect_required_services(state: dict) -> list[str]:
    """Detect which external services are needed based on pipeline state.

    Scans comprehensive_plan and generated_files for service references.
    """
    services: set[str] = set()

    # Check comprehensive plan
    plan = state.get("comprehensive_plan", {})
    plan_text = json.dumps(plan).lower() if plan else ""

    # Check generated files content
    files = state.get("generated_files", {})
    files_text = " ".join(files.values()).lower() if files else ""

    combined = plan_text + " " + files_text

    _SERVICE_KEYWORDS: dict[str, list[str]] = {
        "stripe": ["stripe", "payment", "checkout", "subscription", "billing"],
        "resend": ["resend", "transactional email", "email notification"],
        "openai": ["openai", "gpt-4", "gpt-3", "chatgpt", "dall-e", "whisper"],
        "anthropic": ["anthropic", "claude", "claude-3"],
        "twilio": ["twilio", "sms", "whatsapp", "phone verification"],
        "sendgrid": ["sendgrid", "email campaign", "marketing email"],
    }

    for service, keywords in _SERVICE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            services.add(service)

    logger.info("Detected required services: %s", sorted(services))
    return sorted(services)
