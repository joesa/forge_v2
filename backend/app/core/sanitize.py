import posixpath
import re

from fastapi import HTTPException


def sanitize_path(path: str) -> str:
    """Validate and clean a storage path. Raises HTTP 400 on traversal attempts."""
    if not path or path.startswith("/"):
        raise HTTPException(status_code=400, detail="Path must be a relative path")

    if ".." in path.split("/"):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")

    # Normalize and re-check
    normalized = posixpath.normpath(path)
    if normalized.startswith("/") or normalized.startswith(".."):
        raise HTTPException(status_code=400, detail="Path traversal is not allowed")

    return normalized
