"""Layer 10 — Context Window Manager: chunk at 60% limit with 200-token overlap.

Merges chunks via seam_checker to ensure coherence across boundaries.
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

# Token limits per model
LIMITS: dict[str, int] = {
    "claude-opus-4-6": 200_000,
    "claude-sonnet-4-6": 200_000,
    "gpt-4o": 128_000,
}

# Chunk at 60% of model limit to leave room for response
CHUNK_RATIO = 0.60
OVERLAP_TOKENS = 200

# Rough chars-per-token estimate (conservative for code)
CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str) -> int:
    """Estimate token count from text length. Conservative for code."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def get_model_limit(model: str) -> int:
    """Get token limit for a model, defaulting to gpt-4o limit."""
    return LIMITS.get(model, LIMITS["gpt-4o"])


def chunk_for_model(
    text: str,
    model: str = "gpt-4o",
    *,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[str]:
    """Split text into chunks that fit within 60% of the model's context window.

    Args:
        text: The text to chunk.
        model: Model name to determine limit.
        overlap_tokens: Number of tokens to overlap between chunks.

    Returns:
        List of text chunks. If text fits in one chunk, returns [text].
    """
    limit = get_model_limit(model)
    chunk_token_limit = int(limit * CHUNK_RATIO)
    chunk_char_limit = int(chunk_token_limit * CHARS_PER_TOKEN)
    overlap_chars = int(overlap_tokens * CHARS_PER_TOKEN)

    estimated = estimate_tokens(text)
    if estimated <= chunk_token_limit:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)
    max_chunks = 1000  # Safety limit to prevent infinite loops

    while start < text_len and len(chunks) < max_chunks:
        end = min(start + chunk_char_limit, text_len)

        # Try to break at a natural boundary (newline)
        if end < text_len:
            # Look backwards from end for a newline
            newline_pos = text.rfind("\n", start + chunk_char_limit // 2, end)
            if newline_pos > start:
                end = newline_pos + 1  # Include the newline

        chunk = text[start:end]
        chunks.append(chunk)

        # If we've reached the end of text, we're done
        if end >= text_len:
            break

        # Next chunk starts overlap_chars before end
        start = end - overlap_chars
        if start <= (end - chunk_char_limit):
            # Prevent reverse progress if overlap is too large
            start = end

    logger.info(
        "Chunked %d tokens into %d chunks for model %s (limit %d, chunk limit %d)",
        estimated, len(chunks), model, limit, chunk_token_limit,
    )
    return chunks


def merge_chunks(
    chunks: list[str],
    generated_files: dict[str, str] | None = None,
) -> str:
    """Merge processed chunks back together, deduplicating overlap regions.

    Optionally runs seam_checker on the result if generated_files is provided.

    Args:
        chunks: List of processed text chunks.
        generated_files: Optional generated files dict for seam checking.

    Returns:
        Merged text with overlaps deduplicated.
    """
    if not chunks:
        return ""
    if len(chunks) == 1:
        return chunks[0]

    merged = chunks[0]

    for i in range(1, len(chunks)):
        chunk = chunks[i]
        overlap = _find_overlap(merged, chunk)
        if overlap > 0:
            merged = merged + chunk[overlap:]
        else:
            merged = merged + chunk

    # Optional seam check
    if generated_files is not None:
        try:
            from app.reliability.layer4_coherence.seam_checker import check_seams
            seam_result = check_seams(generated_files)
            if not seam_result["passed"]:
                logger.warning(
                    "Seam check after merge found %d broken seams",
                    len(seam_result["broken_seams"]),
                )
        except ImportError:
            pass

    return merged


def _find_overlap(text_a: str, text_b: str) -> int:
    """Find the length of the overlapping region between end of A and start of B."""
    # Check up to overlap_chars * 2 characters
    max_check = int(OVERLAP_TOKENS * CHARS_PER_TOKEN * 2)
    suffix = text_a[-max_check:] if len(text_a) > max_check else text_a

    best = 0
    for length in range(1, min(len(suffix), len(text_b)) + 1):
        if suffix.endswith(text_b[:length]):
            best = length

    return best
