"""Layer 6 — Build Memory.

Record and retrieve successful build patterns for learning.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class BuildRecord:
    """A record of a completed build."""

    build_id: str
    idea_summary: str
    tech_stack: list[str]
    file_count: int
    gate_results: dict[str, bool]
    patterns_used: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    success: bool = True


class BuildMemory:
    """In-memory build memory store.

    Records successful builds and provides pattern retrieval
    for future builds. In production, backed by Pinecone + Redis.
    """

    def __init__(self) -> None:
        self._records: list[BuildRecord] = []

    def record_build(
        self,
        build_id: str,
        idea_summary: str,
        tech_stack: list[str],
        files: dict[str, str],
        gate_results: dict[str, bool],
        patterns_used: list[str] | None = None,
    ) -> BuildRecord:
        """Record a completed build."""
        record = BuildRecord(
            build_id=build_id,
            idea_summary=idea_summary,
            tech_stack=tech_stack,
            file_count=len(files),
            gate_results=gate_results,
            patterns_used=patterns_used or [],
            success=all(gate_results.values()),
        )
        self._records.append(record)
        logger.info(
            "Recorded build %s (%d files, success=%s)",
            build_id, len(files), record.success,
        )
        return record

    def get_successful_builds(self) -> list[BuildRecord]:
        """Get all successful builds."""
        return [r for r in self._records if r.success]

    def get_builds_by_tech(self, tech: str) -> list[BuildRecord]:
        """Get builds that used a specific technology."""
        tech_lower = tech.lower()
        return [
            r for r in self._records
            if any(t.lower() == tech_lower for t in r.tech_stack) and r.success
        ]

    def get_common_patterns(self, min_count: int = 2) -> list[tuple[str, int]]:
        """Get patterns that appeared in multiple successful builds.

        Returns list of (pattern_name, count) sorted by frequency.
        """
        from collections import Counter

        counter: Counter[str] = Counter()
        for record in self._records:
            if record.success:
                counter.update(record.patterns_used)

        return [
            (pattern, count)
            for pattern, count in counter.most_common()
            if count >= min_count
        ]

    def get_failure_patterns(self) -> list[dict]:
        """Get patterns from failed builds to avoid."""
        failures: list[dict] = []
        for record in self._records:
            if not record.success:
                failed_gates = [
                    gate for gate, passed in record.gate_results.items()
                    if not passed
                ]
                failures.append({
                    "build_id": record.build_id,
                    "idea_summary": record.idea_summary,
                    "failed_gates": failed_gates,
                    "patterns_used": record.patterns_used,
                })
        return failures

    def suggest_patterns(self, tech_stack: list[str]) -> list[str]:
        """Suggest patterns based on tech stack from successful builds."""
        relevant_patterns: list[str] = []

        for tech in tech_stack:
            builds = self.get_builds_by_tech(tech)
            for build in builds:
                for pattern in build.patterns_used:
                    if pattern not in relevant_patterns:
                        relevant_patterns.append(pattern)

        return relevant_patterns

    def get_stats(self) -> dict:
        """Get build memory statistics."""
        total = len(self._records)
        successful = sum(1 for r in self._records if r.success)
        return {
            "total_builds": total,
            "successful_builds": successful,
            "failure_rate": (total - successful) / total if total > 0 else 0.0,
            "common_patterns": self.get_common_patterns(),
        }

    def to_json(self) -> str:
        """Serialise memory to JSON."""
        return json.dumps(
            [
                {
                    "build_id": r.build_id,
                    "idea_summary": r.idea_summary,
                    "tech_stack": r.tech_stack,
                    "file_count": r.file_count,
                    "gate_results": r.gate_results,
                    "patterns_used": r.patterns_used,
                    "timestamp": r.timestamp,
                    "success": r.success,
                }
                for r in self._records
            ],
            indent=2,
        )

    @classmethod
    def from_json(cls, data: str) -> BuildMemory:
        """Deserialise memory from JSON."""
        memory = cls()
        records = json.loads(data)
        for rec in records:
            record = BuildRecord(
                build_id=rec["build_id"],
                idea_summary=rec["idea_summary"],
                tech_stack=rec["tech_stack"],
                file_count=rec["file_count"],
                gate_results=rec["gate_results"],
                patterns_used=rec.get("patterns_used", []),
                timestamp=rec.get("timestamp", ""),
                success=rec.get("success", True),
            )
            memory._records.append(record)
        return memory
