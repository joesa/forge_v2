"""Layer 10 — Fallback Cascade: anthropic → openai → gemini → mistral → cohere.

Logs every fallback for billing. Each provider attempt is isolated with its own error handling.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Provider order: primary → fallbacks
PROVIDER_ORDER = ["anthropic", "openai", "gemini", "mistral", "cohere"]


@dataclass
class FallbackResult:
    success: bool
    provider: str | None = None
    response: Any = None
    attempts: list[dict] = field(default_factory=list)
    total_time_ms: float = 0.0


class FallbackCascade:
    """AI provider fallback cascade.

    Tries providers in order: anthropic → openai → gemini → mistral → cohere.
    Logs every fallback for billing tracking.
    """

    def __init__(
        self,
        providers: dict[str, Any] | None = None,
        provider_order: list[str] | None = None,
    ) -> None:
        """
        Args:
            providers: Dict mapping provider name → callable(prompt, **kwargs) -> response.
            provider_order: Custom provider order. Defaults to PROVIDER_ORDER.
        """
        self.providers = providers or {}
        self.order = provider_order or list(PROVIDER_ORDER)
        self.fallback_log: list[dict] = []

    def register_provider(self, name: str, fn: Any) -> None:
        """Register an AI provider callable."""
        self.providers[name] = fn

    async def call(
        self,
        prompt: str,
        *,
        temperature: int = 0,
        seed: int = 42,
        **kwargs: Any,
    ) -> FallbackResult:
        """Call AI providers in cascade order until one succeeds.

        Args:
            prompt: The prompt to send.
            temperature: Temperature setting (enforced by determinism_enforcer).
            seed: Seed for determinism.
            **kwargs: Additional provider-specific kwargs.

        Returns:
            FallbackResult with the first successful response.
        """
        start = time.monotonic()
        attempts: list[dict] = []

        for provider_name in self.order:
            fn = self.providers.get(provider_name)
            if fn is None:
                continue

            attempt_start = time.monotonic()
            try:
                response = await fn(
                    prompt,
                    temperature=temperature,
                    seed=seed,
                    **kwargs,
                )

                elapsed = (time.monotonic() - attempt_start) * 1000
                attempt_record = {
                    "provider": provider_name,
                    "success": True,
                    "time_ms": round(elapsed, 2),
                    "error": None,
                }
                attempts.append(attempt_record)
                self._log_attempt(attempt_record)

                total_time = (time.monotonic() - start) * 1000
                logger.info(
                    "Fallback cascade: %s succeeded in %.1fms (total %.1fms, %d attempts)",
                    provider_name, elapsed, total_time, len(attempts),
                )

                return FallbackResult(
                    success=True,
                    provider=provider_name,
                    response=response,
                    attempts=attempts,
                    total_time_ms=round(total_time, 2),
                )

            except Exception as e:
                elapsed = (time.monotonic() - attempt_start) * 1000
                attempt_record = {
                    "provider": provider_name,
                    "success": False,
                    "time_ms": round(elapsed, 2),
                    "error": str(e),
                }
                attempts.append(attempt_record)
                self._log_attempt(attempt_record)

                logger.warning(
                    "Fallback cascade: %s failed in %.1fms — %s",
                    provider_name, elapsed, e,
                )

        total_time = (time.monotonic() - start) * 1000
        logger.error(
            "Fallback cascade: all %d providers failed in %.1fms",
            len(attempts), total_time,
        )
        return FallbackResult(
            success=False,
            provider=None,
            response=None,
            attempts=attempts,
            total_time_ms=round(total_time, 2),
        )

    def _log_attempt(self, record: dict) -> None:
        """Log attempt for billing tracking."""
        self.fallback_log.append({
            **record,
            "timestamp": time.time(),
        })

    def get_billing_log(self) -> list[dict]:
        """Return the full fallback log for billing reconciliation."""
        return list(self.fallback_log)

    def clear_log(self) -> None:
        """Clear the fallback log."""
        self.fallback_log.clear()
