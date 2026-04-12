"""Layer 10 — Determinism Enforcer: decorator ensuring temperature=0, seed=42 on build agents."""
from __future__ import annotations

import functools
import logging
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_TEMPERATURE = 0
REQUIRED_SEED = 42


def enforce_determinism(fn=None, *, temperature: int = REQUIRED_TEMPERATURE, seed: int = REQUIRED_SEED):
    """Decorator that enforces deterministic AI parameters on build agent calls.

    Can be used as @enforce_determinism or @enforce_determinism(temperature=0, seed=42).

    Intercepts kwargs passed to the decorated function and overrides
    temperature and seed to the required values. Logs a warning if the
    original values differ.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Override temperature
            orig_temp = kwargs.get("temperature")
            if orig_temp is not None and orig_temp != temperature:
                logger.warning(
                    "Determinism enforcer: overriding temperature=%s to %s in %s",
                    orig_temp, temperature, func.__qualname__,
                )
            kwargs["temperature"] = temperature

            # Override seed
            orig_seed = kwargs.get("seed")
            if orig_seed is not None and orig_seed != seed:
                logger.warning(
                    "Determinism enforcer: overriding seed=%s to %s in %s",
                    orig_seed, seed, func.__qualname__,
                )
            kwargs["seed"] = seed

            return await func(*args, **kwargs)

        # Mark as determinism-enforced for introspection
        wrapper._determinism_enforced = True  # type: ignore[attr-defined]
        wrapper._required_temperature = temperature  # type: ignore[attr-defined]
        wrapper._required_seed = seed  # type: ignore[attr-defined]
        return wrapper

    if fn is not None:
        # Used as @enforce_determinism without parentheses
        return decorator(fn)
    return decorator


def validate_determinism(agent: Any) -> dict:
    """Validate that an agent's configuration is deterministic.

    Checks if the agent class or its execute method has the correct
    temperature and seed settings.

    Returns:
        {"passed": bool, "temperature": int|None, "seed": int|None, "issues": list[str]}
    """
    issues: list[str] = []

    # Check class-level constants
    temp = getattr(agent, "TEMPERATURE", None)
    if temp is None:
        # Check module-level constant imported from base
        temp = getattr(agent, "temperature", None)
    seed = getattr(agent, "SEED", None)
    if seed is None:
        seed = getattr(agent, "seed", None)

    if temp is not None and temp != REQUIRED_TEMPERATURE:
        issues.append(f"temperature={temp}, expected {REQUIRED_TEMPERATURE}")
    if seed is not None and seed != REQUIRED_SEED:
        issues.append(f"seed={seed}, expected {REQUIRED_SEED}")

    # Check if execute method has enforce_determinism decorator
    execute = getattr(agent, "execute", None)
    if execute is not None:
        has_enforcer = getattr(execute, "_determinism_enforced", False)
        if not has_enforcer and temp is None:
            issues.append("execute() not wrapped with @enforce_determinism and no TEMPERATURE constant")

    passed = len(issues) == 0
    return {
        "passed": passed,
        "temperature": temp,
        "seed": seed,
        "issues": issues,
    }
