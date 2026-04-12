"""Layer 6 — Incremental Build.

SHA-256 hash comparison for partial rebuilds.
Only rebuild files whose content or dependencies have changed.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FileHash:
    """Hash record for a single file."""

    filepath: str
    content_hash: str
    dep_hash: str  # Hash of all dependencies


@dataclass
class IncrementalResult:
    """Result of an incremental build comparison."""

    changed_files: list[str]
    unchanged_files: list[str]
    new_files: list[str]
    deleted_files: list[str]
    total_files: int
    rebuild_files: list[str]  # Union of changed + new + dep-invalidated


class IncrementalBuildTracker:
    """Track file hashes to enable incremental builds.

    Compares SHA-256 hashes of file contents and their dependency
    trees to determine which files need rebuilding.
    """

    def __init__(self) -> None:
        self._hashes: dict[str, FileHash] = {}

    def compute_hashes(
        self,
        generated_files: dict[str, str],
        dependency_graph: dict[str, list[str]] | None = None,
    ) -> dict[str, FileHash]:
        """Compute hashes for all generated files.

        Args:
            generated_files: Dict of filepath → content.
            dependency_graph: Optional dict of filepath → [dependency filepaths].

        Returns dict of filepath → FileHash.
        """
        dep_graph = dependency_graph or {}
        hashes: dict[str, FileHash] = {}

        for filepath, content in generated_files.items():
            content_hash = _sha256(content)

            # Compute dep hash: hash of all dependency content hashes
            deps = dep_graph.get(filepath, [])
            dep_contents = []
            for dep in sorted(deps):
                if dep in generated_files:
                    dep_contents.append(_sha256(generated_files[dep]))
            dep_hash = _sha256("".join(dep_contents)) if dep_contents else ""

            hashes[filepath] = FileHash(
                filepath=filepath,
                content_hash=content_hash,
                dep_hash=dep_hash,
            )

        return hashes

    def compare(
        self,
        new_files: dict[str, str],
        dependency_graph: dict[str, list[str]] | None = None,
    ) -> IncrementalResult:
        """Compare new files against previous hashes.

        Returns IncrementalResult with changed/unchanged/new/deleted sets.
        """
        new_hashes = self.compute_hashes(new_files, dependency_graph)

        changed: list[str] = []
        unchanged: list[str] = []
        added: list[str] = []
        deleted: list[str] = []

        # Check for changes and additions
        for filepath, new_hash in new_hashes.items():
            if filepath not in self._hashes:
                added.append(filepath)
            else:
                old_hash = self._hashes[filepath]
                if (
                    old_hash.content_hash != new_hash.content_hash
                    or old_hash.dep_hash != new_hash.dep_hash
                ):
                    changed.append(filepath)
                else:
                    unchanged.append(filepath)

        # Check for deletions
        for filepath in self._hashes:
            if filepath not in new_hashes:
                deleted.append(filepath)

        # Determine files that need rebuild due to dependency invalidation
        dep_graph = dependency_graph or {}
        rebuild_set = set(changed + added)

        # Cascade: if a file changed, anything depending on it needs rebuild too
        changed_set = set(changed + added)
        for filepath, deps in dep_graph.items():
            if filepath not in rebuild_set:
                for dep in deps:
                    if dep in changed_set:
                        rebuild_set.add(filepath)
                        break

        result = IncrementalResult(
            changed_files=sorted(changed),
            unchanged_files=sorted(unchanged),
            new_files=sorted(added),
            deleted_files=sorted(deleted),
            total_files=len(new_files),
            rebuild_files=sorted(rebuild_set),
        )

        logger.info(
            "Incremental compare: %d changed, %d new, %d unchanged, %d deleted → %d to rebuild",
            len(changed), len(added), len(unchanged), len(deleted), len(rebuild_set),
        )

        return result

    def update(
        self,
        generated_files: dict[str, str],
        dependency_graph: dict[str, list[str]] | None = None,
    ) -> None:
        """Update stored hashes with new file contents."""
        self._hashes = self.compute_hashes(generated_files, dependency_graph)
        logger.info("Updated incremental hashes for %d files", len(self._hashes))

    def get_hash(self, filepath: str) -> FileHash | None:
        """Get stored hash for a file."""
        return self._hashes.get(filepath)

    def clear(self) -> None:
        """Clear all stored hashes."""
        self._hashes.clear()

    @property
    def file_count(self) -> int:
        """Number of tracked files."""
        return len(self._hashes)


# ── Utility ──────────────────────────────────────────────────────


def _sha256(content: str) -> str:
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(content.encode()).hexdigest()


def compute_file_hash(content: str) -> str:
    """Public utility: compute SHA-256 hash of file content."""
    return _sha256(content)
