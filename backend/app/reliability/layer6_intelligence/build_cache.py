"""Layer 6 — Build Cache (Pinecone).

Semantic vector search over previous successful builds.
Similarity threshold >= 0.92 to reuse.
ONLY store builds that passed ALL gates.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheResult:
    """Result from a build cache hit."""

    build_id: str
    similarity: float
    files: dict[str, str]
    metadata: dict[str, Any]


# ── Constants ────────────────────────────────────────────────────

SIMILARITY_THRESHOLD = 0.92
EMBEDDING_DIMENSION = 1536  # OpenAI ada-002 default


# ── Public API ───────────────────────────────────────────────────


async def check_cache(
    idea_spec: dict,
    pinecone_index: Any | None = None,
    embedding_fn: Any | None = None,
) -> CacheResult | None:
    """Check if a similar build exists in the cache.

    Returns CacheResult if similarity >= 0.92, else None.

    Args:
        idea_spec: The user's idea specification dict.
        pinecone_index: A Pinecone index instance (injected for testability).
        embedding_fn: Async function that returns embedding vector from text.
    """
    if pinecone_index is None or embedding_fn is None:
        logger.warning("Build cache not configured — skipping cache check")
        return None

    spec_text = _spec_to_text(idea_spec)
    spec_hash = _hash_spec(spec_text)

    try:
        embedding = await embedding_fn(spec_text)

        results = pinecone_index.query(
            vector=embedding,
            top_k=1,
            include_metadata=True,
        )

        matches = results.get("matches", [])
        if not matches:
            logger.info("No cache hit for spec hash %s", spec_hash[:12])
            return None

        best = matches[0]
        similarity = best.get("score", 0.0)

        if similarity < SIMILARITY_THRESHOLD:
            logger.info(
                "Cache near-miss: similarity %.4f < %.2f for %s",
                similarity, SIMILARITY_THRESHOLD, spec_hash[:12],
            )
            return None

        metadata = best.get("metadata", {})
        files_json = metadata.get("files", "{}")
        files = json.loads(files_json) if isinstance(files_json, str) else files_json

        logger.info(
            "Cache HIT: similarity %.4f for %s (build %s)",
            similarity, spec_hash[:12], metadata.get("build_id", "?"),
        )
        return CacheResult(
            build_id=metadata.get("build_id", ""),
            similarity=similarity,
            files=files,
            metadata=metadata,
        )

    except Exception:
        logger.exception("Build cache check failed")
        return None


async def store_in_cache(
    idea_spec: dict,
    build_id: str,
    files: dict[str, str],
    all_gates_passed: bool,
    pinecone_index: Any | None = None,
    embedding_fn: Any | None = None,
) -> bool:
    """Store a successful build in the cache.

    CRITICAL: Only store builds that passed ALL gates.

    Args:
        idea_spec: The user's idea specification dict.
        build_id: UUID of the completed build.
        files: Dict of filepath → content from the build.
        all_gates_passed: MUST be True or we refuse to store.
        pinecone_index: A Pinecone index instance.
        embedding_fn: Async function that returns embedding vector from text.

    Returns True if stored, False otherwise.
    """
    if not all_gates_passed:
        logger.warning("Refusing to cache build %s — not all gates passed", build_id)
        return False

    if pinecone_index is None or embedding_fn is None:
        logger.warning("Build cache not configured — skipping store")
        return False

    spec_text = _spec_to_text(idea_spec)
    spec_hash = _hash_spec(spec_text)

    try:
        embedding = await embedding_fn(spec_text)

        # Serialise files — large payloads get truncated metadata
        files_json = json.dumps(files)
        metadata: dict[str, Any] = {
            "build_id": build_id,
            "spec_hash": spec_hash,
            "file_count": len(files),
            "files": files_json if len(files_json) < 40_000 else "{}",
        }

        pinecone_index.upsert(
            vectors=[
                {
                    "id": spec_hash,
                    "values": embedding,
                    "metadata": metadata,
                }
            ]
        )

        logger.info("Cached build %s (hash %s, %d files)", build_id, spec_hash[:12], len(files))
        return True

    except Exception:
        logger.exception("Failed to store build in cache")
        return False


# ── Internal helpers ─────────────────────────────────────────────


def _spec_to_text(idea_spec: dict) -> str:
    """Convert idea spec to deterministic text for embedding."""
    parts: list[str] = []
    for key in sorted(idea_spec.keys()):
        value = idea_spec[key]
        if isinstance(value, str):
            parts.append(f"{key}: {value}")
        else:
            parts.append(f"{key}: {json.dumps(value, sort_keys=True)}")
    return "\n".join(parts)


def _hash_spec(spec_text: str) -> str:
    """SHA-256 hash of spec text for deduplication."""
    return hashlib.sha256(spec_text.encode()).hexdigest()
