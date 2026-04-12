"""Layer 10 — AI Reliability: context window, CSS validation, determinism, fallback cascade."""
from app.reliability.layer10_ai.context_window_manager import (
    chunk_for_model,
    merge_chunks,
    LIMITS,
)
from app.reliability.layer10_ai.css_validator import validate_css_classes, CSSValidationResult
from app.reliability.layer10_ai.determinism_enforcer import enforce_determinism
from app.reliability.layer10_ai.fallback_cascade import FallbackCascade, FallbackResult

__all__ = [
    "chunk_for_model",
    "merge_chunks",
    "LIMITS",
    "validate_css_classes",
    "CSSValidationResult",
    "enforce_determinism",
    "FallbackCascade",
    "FallbackResult",
]
