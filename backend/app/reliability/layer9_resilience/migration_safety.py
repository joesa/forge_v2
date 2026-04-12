"""Layer 9 — Migration Safety: block destructive SQL operations.

Called by db_agent BEFORE writing any SQL/migration content.
Blocks: DROP TABLE, DELETE without WHERE, TRUNCATE, DROP DATABASE.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MigrationSafetyResult:
    safe: bool
    violations: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# Patterns for destructive operations (case-insensitive)
_DROP_TABLE_RE = re.compile(
    r"\bDROP\s+TABLE\b", re.IGNORECASE
)
_DROP_DATABASE_RE = re.compile(
    r"\bDROP\s+DATABASE\b", re.IGNORECASE
)
_TRUNCATE_RE = re.compile(
    r"\bTRUNCATE\b", re.IGNORECASE
)
_DELETE_RE = re.compile(
    r"\bDELETE\s+FROM\b", re.IGNORECASE
)
_WHERE_RE = re.compile(
    r"\bWHERE\b", re.IGNORECASE
)
_DROP_COLUMN_RE = re.compile(
    r"\bDROP\s+COLUMN\b", re.IGNORECASE
)
_ALTER_TYPE_RE = re.compile(
    r"\bALTER\s+COLUMN\b.*\bTYPE\b", re.IGNORECASE
)


def check_migration_safety(sql: str) -> MigrationSafetyResult:
    """Check SQL content for destructive operations.

    Args:
        sql: The SQL or migration content to check.

    Returns:
        MigrationSafetyResult with safe=False if destructive ops found.
    """
    violations: list[dict] = []
    warnings: list[str] = []

    # Split into statements for per-statement analysis
    statements = _split_statements(sql)

    for i, stmt in enumerate(statements, 1):
        stripped = stmt.strip()
        if not stripped:
            continue

        # BLOCK: DROP TABLE
        if _DROP_TABLE_RE.search(stripped):
            violations.append({
                "type": "drop_table",
                "statement_number": i,
                "statement": _truncate_stmt(stripped),
                "detail": "DROP TABLE is blocked — data loss risk",
            })

        # BLOCK: DROP DATABASE
        if _DROP_DATABASE_RE.search(stripped):
            violations.append({
                "type": "drop_database",
                "statement_number": i,
                "statement": _truncate_stmt(stripped),
                "detail": "DROP DATABASE is blocked — catastrophic data loss",
            })

        # BLOCK: TRUNCATE
        if _TRUNCATE_RE.search(stripped):
            violations.append({
                "type": "truncate",
                "statement_number": i,
                "statement": _truncate_stmt(stripped),
                "detail": "TRUNCATE is blocked — data loss risk",
            })

        # BLOCK: DELETE without WHERE
        if _DELETE_RE.search(stripped) and not _WHERE_RE.search(stripped):
            violations.append({
                "type": "delete_without_where",
                "statement_number": i,
                "statement": _truncate_stmt(stripped),
                "detail": "DELETE without WHERE clause is blocked — would delete all rows",
            })

        # WARN: DROP COLUMN (allowed but flagged)
        if _DROP_COLUMN_RE.search(stripped):
            warnings.append(
                f"Statement {i}: DROP COLUMN detected — ensure data migration is handled"
            )

        # WARN: ALTER COLUMN TYPE (allowed but flagged)
        if _ALTER_TYPE_RE.search(stripped):
            warnings.append(
                f"Statement {i}: ALTER COLUMN TYPE detected — may cause data conversion issues"
            )

    safe = len(violations) == 0

    if not safe:
        logger.warning(
            "Migration safety: %d violations found in SQL",
            len(violations),
        )
    elif warnings:
        logger.info(
            "Migration safety: passed with %d warnings",
            len(warnings),
        )

    return MigrationSafetyResult(safe=safe, violations=violations, warnings=warnings)


def check_files_migration_safety(files: dict[str, str]) -> MigrationSafetyResult:
    """Check all SQL/migration files in a generated files dict."""
    all_violations: list[dict] = []
    all_warnings: list[str] = []

    for path, content in files.items():
        if not isinstance(content, str):
            continue
        if not _is_migration_file(path):
            continue

        result = check_migration_safety(content)
        for v in result.violations:
            v["file"] = path
            all_violations.append(v)
        for w in result.warnings:
            all_warnings.append(f"[{path}] {w}")

    return MigrationSafetyResult(
        safe=len(all_violations) == 0,
        violations=all_violations,
        warnings=all_warnings,
    )


def _is_migration_file(path: str) -> bool:
    """Check if a file path looks like a migration or SQL file."""
    lower = path.lower()
    if lower.endswith(".sql"):
        return True
    if "migration" in lower or "migrate" in lower:
        return True
    if "alembic" in lower and lower.endswith(".py"):
        return True
    if "schema" in lower and lower.endswith(".sql"):
        return True
    return False


def _split_statements(sql: str) -> list[str]:
    """Split SQL into individual statements by semicolon."""
    return [s.strip() for s in sql.split(";") if s.strip()]


def _truncate_stmt(stmt: str, max_len: int = 200) -> str:
    """Truncate a statement for display."""
    if len(stmt) <= max_len:
        return stmt
    return stmt[:max_len] + "..."
