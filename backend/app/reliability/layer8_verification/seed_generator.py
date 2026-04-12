"""Layer 8f — Seed Data Generator.

Faker.js-style seed data generation:
  - 10 users + 5-20 records per table
  - Respects FK order (topological sort)
  - Deterministic (seed=42)

Called from ReviewAgent only.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid as uuid_lib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────
DEFAULT_USER_COUNT = 10
DEFAULT_RECORDS_MIN = 5
DEFAULT_RECORDS_MAX = 20
FAKER_SEED = 42


@dataclass
class TableSchema:
    """Parsed table/model schema."""

    name: str
    columns: list[ColumnDef] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)


@dataclass
class ColumnDef:
    """Column definition."""

    name: str
    col_type: str  # "string" | "integer" | "uuid" | "boolean" | "datetime" | "float" | "json" | "text" | "email"
    nullable: bool = False
    is_primary: bool = False
    is_foreign_key: bool = False
    default: Any = None


@dataclass
class ForeignKey:
    """Foreign key relationship."""

    column: str
    references_table: str
    references_column: str


@dataclass
class SeedReport:
    """Seed generation report."""

    passed: bool = True
    tables_seeded: int = 0
    total_records: int = 0
    user_count: int = 0
    seed_files: dict[str, str] = field(default_factory=dict)  # filepath → content
    table_order: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ── Deterministic data generators ────────────────────────────────

class FakerLite:
    """Simple deterministic fake data generator. Seed=42."""

    def __init__(self, seed: int = FAKER_SEED) -> None:
        import random
        self._rng = random.Random(seed)
        self._counter = 0

    _FIRST_NAMES = [
        "Alice", "Bob", "Charlie", "Diana", "Edward",
        "Fiona", "George", "Hannah", "Ivan", "Julia",
        "Kevin", "Laura", "Michael", "Nora", "Oscar",
        "Patricia", "Quinn", "Rachel", "Steven", "Tanya",
    ]
    _LAST_NAMES = [
        "Smith", "Johnson", "Williams", "Brown", "Jones",
        "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
        "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
        "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    ]
    _DOMAINS = ["example.com", "test.org", "demo.net", "sample.io", "forge.dev"]
    _WORDS = [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "quantum", "stellar", "cosmic", "nexus", "prism",
        "forge", "spark", "pixel", "cipher", "atlas",
    ]

    def first_name(self) -> str:
        return self._rng.choice(self._FIRST_NAMES)

    def last_name(self) -> str:
        return self._rng.choice(self._LAST_NAMES)

    def full_name(self) -> str:
        return f"{self.first_name()} {self.last_name()}"

    def email(self) -> str:
        self._counter += 1
        first = self.first_name().lower()
        last = self.last_name().lower()
        domain = self._rng.choice(self._DOMAINS)
        return f"{first}.{last}{self._counter}@{domain}"

    def uuid(self) -> str:
        return str(uuid_lib.UUID(int=self._rng.getrandbits(128), version=4))

    def integer(self, min_val: int = 1, max_val: int = 1000) -> int:
        return self._rng.randint(min_val, max_val)

    def float_val(self, min_val: float = 0.0, max_val: float = 100.0) -> float:
        return round(self._rng.uniform(min_val, max_val), 2)

    def boolean(self) -> bool:
        return self._rng.choice([True, False])

    def text(self, words: int = 10) -> str:
        return " ".join(self._rng.choice(self._WORDS) for _ in range(words))

    def sentence(self) -> str:
        return self.text(self._rng.randint(5, 15)).capitalize() + "."

    def datetime_recent(self) -> str:
        days_ago = self._rng.randint(0, 90)
        dt = datetime(2026, 1, 1) - timedelta(days=days_ago)
        return dt.isoformat() + "Z"

    def phone(self) -> str:
        return f"+1{self._rng.randint(200, 999)}{self._rng.randint(1000000, 9999999)}"

    def url(self) -> str:
        return f"https://{self._rng.choice(self._WORDS)}.{self._rng.choice(self._DOMAINS)}"

    def pick_from(self, ids: list[str]) -> str:
        return self._rng.choice(ids) if ids else self.uuid()

    def record_count(self) -> int:
        return self._rng.randint(DEFAULT_RECORDS_MIN, DEFAULT_RECORDS_MAX)


# ── Schema extraction ────────────────────────────────────────────

def _extract_schemas(generated_files: dict[str, str]) -> list[TableSchema]:
    """Extract table schemas from generated code (Prisma, SQLAlchemy, TypeORM, Drizzle, raw SQL)."""
    schemas: list[TableSchema] = []

    for filepath, content in generated_files.items():
        if not isinstance(content, str):
            continue
        ext = os.path.splitext(filepath)[1].lower()

        if "prisma" in filepath.lower() or ext == ".prisma":
            schemas.extend(_parse_prisma_models(content))
        elif "schema" in filepath.lower() and ext in {".ts", ".js"}:
            schemas.extend(_parse_drizzle_or_typeorm(filepath, content))
        elif ext == ".py" and ("model" in filepath.lower() or "schema" in filepath.lower()):
            schemas.extend(_parse_sqlalchemy_models(content))
        elif ext == ".sql":
            schemas.extend(_parse_sql_create_tables(content))

    return schemas


def _parse_prisma_models(content: str) -> list[TableSchema]:
    """Parse Prisma schema models."""
    schemas: list[TableSchema] = []
    model_blocks = re.finditer(
        r"model\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL
    )

    for match in model_blocks:
        model_name = match.group(1)
        body = match.group(2)
        table = TableSchema(name=model_name)

        for line in body.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("@@"):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            col_name = parts[0]
            col_type_raw = parts[1]
            col_type = _normalize_prisma_type(col_type_raw)
            nullable = "?" in col_type_raw
            is_pk = "@id" in line
            is_fk = "@relation" in line

            table.columns.append(ColumnDef(
                name=col_name,
                col_type=col_type,
                nullable=nullable,
                is_primary=is_pk,
                is_foreign_key=is_fk,
            ))

            # Parse @relation
            rel_match = re.search(r'@relation.*references:\s*\[(\w+)\]', line)
            fk_field_match = re.search(r'@relation.*fields:\s*\[(\w+)\]', line)
            if rel_match and fk_field_match:
                table.foreign_keys.append(ForeignKey(
                    column=fk_field_match.group(1),
                    references_table=col_type_raw.replace("?", "").replace("[]", ""),
                    references_column=rel_match.group(1),
                ))

        schemas.append(table)

    return schemas


def _parse_drizzle_or_typeorm(filepath: str, content: str) -> list[TableSchema]:
    """Parse Drizzle/TypeORM table definitions."""
    schemas: list[TableSchema] = []

    # Drizzle: export const users = pgTable("users", { ... })
    for match in re.finditer(
        r'(?:export\s+)?(?:const|let)\s+(\w+)\s*=\s*\w+Table\s*\(\s*["\'](\w+)["\']',
        content,
    ):
        table = TableSchema(name=match.group(2))
        # Simplified: extract column-like patterns
        schemas.append(table)

    return schemas


def _parse_sqlalchemy_models(content: str) -> list[TableSchema]:
    """Parse SQLAlchemy model definitions."""
    schemas: list[TableSchema] = []

    for match in re.finditer(
        r'__tablename__\s*=\s*["\'](\w+)["\']', content
    ):
        table = TableSchema(name=match.group(1))
        schemas.append(table)

    return schemas


def _parse_sql_create_tables(content: str) -> list[TableSchema]:
    """Parse CREATE TABLE statements."""
    schemas: list[TableSchema] = []

    for match in re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"']?(\w+)[\"']?\s*\(([^;]+)\)",
        content, re.IGNORECASE | re.DOTALL,
    ):
        table_name = match.group(1)
        body = match.group(2)
        table = TableSchema(name=table_name)

        for line in body.split(","):
            line = line.strip()
            parts = line.split()
            if len(parts) >= 2 and not line.upper().startswith(("PRIMARY", "FOREIGN", "CONSTRAINT", "UNIQUE", "INDEX")):
                col_name = parts[0].strip('"\'')
                col_type = _normalize_sql_type(parts[1])
                table.columns.append(ColumnDef(name=col_name, col_type=col_type))

            # FK
            fk_match = re.search(
                r"REFERENCES\s+[\"']?(\w+)[\"']?\s*\(\s*[\"']?(\w+)[\"']?\s*\)",
                line, re.IGNORECASE,
            )
            if fk_match:
                table.foreign_keys.append(ForeignKey(
                    column=parts[0].strip('"\'') if parts else "",
                    references_table=fk_match.group(1),
                    references_column=fk_match.group(2),
                ))

        schemas.append(table)

    return schemas


def _normalize_prisma_type(raw: str) -> str:
    """Normalize Prisma type to our internal type."""
    clean = raw.replace("?", "").replace("[]", "")
    mapping = {
        "String": "string", "Int": "integer", "Float": "float",
        "Boolean": "boolean", "DateTime": "datetime", "Json": "json",
        "BigInt": "integer",
    }
    return mapping.get(clean, "string")


def _normalize_sql_type(raw: str) -> str:
    """Normalize SQL type to our internal type."""
    upper = raw.upper()
    if "INT" in upper:
        return "integer"
    if "CHAR" in upper or "TEXT" in upper:
        return "string"
    if "BOOL" in upper:
        return "boolean"
    if "FLOAT" in upper or "DOUBLE" in upper or "DECIMAL" in upper or "NUMERIC" in upper:
        return "float"
    if "DATE" in upper or "TIME" in upper:
        return "datetime"
    if "JSON" in upper:
        return "json"
    if "UUID" in upper:
        return "uuid"
    return "string"


# ── Topological sort (FK order) ──────────────────────────────────

def _topological_sort(schemas: list[TableSchema]) -> list[str]:
    """Sort tables by FK dependencies — parents first."""
    graph: dict[str, set[str]] = defaultdict(set)
    all_tables: set[str] = set()

    for table in schemas:
        all_tables.add(table.name)
        for fk in table.foreign_keys:
            if fk.references_table != table.name:  # skip self-ref
                graph[table.name].add(fk.references_table)
                all_tables.add(fk.references_table)

    # Kahn's algorithm
    in_degree: dict[str, int] = {t: 0 for t in all_tables}
    for table, deps in graph.items():
        for dep in deps:
            if dep in in_degree:
                in_degree[table] = in_degree.get(table, 0)  # ensure exists

    # Build adjacency list (parent → children)
    adj: dict[str, list[str]] = defaultdict(list)
    for child, parents in graph.items():
        for parent in parents:
            adj[parent].append(child)
            in_degree[child] = in_degree.get(child, 0) + 1

    # Re-count from scratch
    in_degree = {t: 0 for t in all_tables}
    for child, parents in graph.items():
        in_degree[child] = len(parents)

    queue = [t for t in all_tables if in_degree[t] == 0]
    queue.sort()  # deterministic
    result: list[str] = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for child in sorted(adj[node]):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)
        queue.sort()

    # Add any remaining (circular deps)
    remaining = all_tables - set(result)
    result.extend(sorted(remaining))

    return result


# ── Seed record generation ───────────────────────────────────────

def _generate_value(faker: FakerLite, col: ColumnDef, existing_ids: dict[str, list[str]]) -> Any:
    """Generate a fake value for a column."""
    name_lower = col.name.lower()

    # FK reference
    if col.is_foreign_key:
        # Try to find the referenced table's IDs
        for table_ids in existing_ids.values():
            if table_ids:
                return faker.pick_from(table_ids)
        return faker.uuid()

    # Heuristic by name
    if name_lower in ("id", "uuid"):
        return faker.uuid()
    if "email" in name_lower:
        return faker.email()
    if name_lower in ("name", "full_name", "fullname"):
        return faker.full_name()
    if "first_name" in name_lower or "firstname" in name_lower:
        return faker.first_name()
    if "last_name" in name_lower or "lastname" in name_lower:
        return faker.last_name()
    if "phone" in name_lower:
        return faker.phone()
    if "url" in name_lower or "website" in name_lower or "avatar" in name_lower:
        return faker.url()
    if "password" in name_lower:
        return "$2b$10$fakehash.placeholder.for.seed.data.only"
    if "created" in name_lower or "updated" in name_lower or "date" in name_lower:
        return faker.datetime_recent()
    if "title" in name_lower or "subject" in name_lower:
        return faker.sentence()
    if "description" in name_lower or "bio" in name_lower or "body" in name_lower or "content" in name_lower:
        return faker.text(20)
    if "active" in name_lower or "enabled" in name_lower or "verified" in name_lower:
        return faker.boolean()
    if "price" in name_lower or "amount" in name_lower or "total" in name_lower:
        return faker.float_val(1.0, 999.99)
    if "count" in name_lower or "quantity" in name_lower or "age" in name_lower:
        return faker.integer(1, 100)

    # By type
    match col.col_type:
        case "uuid":
            return faker.uuid()
        case "string" | "text":
            return faker.text(5)
        case "integer":
            return faker.integer()
        case "float":
            return faker.float_val()
        case "boolean":
            return faker.boolean()
        case "datetime":
            return faker.datetime_recent()
        case "email":
            return faker.email()
        case "json":
            return {}
        case _:
            return faker.text(3)


def _generate_records(
    table: TableSchema,
    count: int,
    faker: FakerLite,
    existing_ids: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Generate `count` seed records for a table."""
    records: list[dict[str, Any]] = []

    for _ in range(count):
        record: dict[str, Any] = {}
        for col in table.columns:
            if col.name.endswith("[]") or col.col_type == "relation":
                continue  # Skip Prisma relations
            record[col.name] = _generate_value(faker, col, existing_ids)
        records.append(record)

    return records


# ── Main entry point ─────────────────────────────────────────────

async def run_seed_generator(
    generated_files: dict[str, str],
    *,
    user_count: int = DEFAULT_USER_COUNT,
) -> dict:
    """Generate deterministic seed data for all detected tables.

    10 users + 5-20 records per table. Respects FK order.

    Args:
        generated_files: Dict of filepath → content.
        user_count: Number of user records to generate.

    Returns:
        Dict with passed, tables_seeded, total_records, seed_files, etc.
    """
    faker = FakerLite(seed=FAKER_SEED)
    report = SeedReport()

    # Extract schemas
    schemas = _extract_schemas(generated_files)

    if not schemas:
        report.warnings.append("No database schemas detected — skipping seed generation")
        logger.info("Seed generator: no schemas found")
        return _report_to_dict(report)

    # Topological sort
    table_order = _topological_sort(schemas)
    report.table_order = table_order

    schema_map = {s.name: s for s in schemas}
    existing_ids: dict[str, list[str]] = {}
    all_seed_data: dict[str, list[dict[str, Any]]] = {}

    # Generate in FK order
    for table_name in table_order:
        schema = schema_map.get(table_name)
        if not schema:
            continue

        # User tables get fixed count
        is_user_table = any(
            kw in table_name.lower()
            for kw in ("user", "account", "profile", "member")
        )
        count = user_count if is_user_table else faker.record_count()

        records = _generate_records(schema, count, faker, existing_ids)
        all_seed_data[table_name] = records

        # Track IDs for FK references
        for record in records:
            pk_val = record.get("id") or record.get("uuid")
            if pk_val:
                existing_ids.setdefault(table_name, []).append(str(pk_val))

        report.tables_seeded += 1
        report.total_records += len(records)
        if is_user_table:
            report.user_count = count

    # Generate seed file
    seed_content = json.dumps(all_seed_data, indent=2, default=str)
    report.seed_files["prisma/seed.json"] = seed_content

    # Also generate a seed script
    seed_script = _generate_seed_script(table_order, all_seed_data)
    report.seed_files["prisma/seed.ts"] = seed_script

    logger.info(
        "Seed generator: %d tables, %d total records, %d users",
        report.tables_seeded, report.total_records, report.user_count,
    )

    return _report_to_dict(report)


def _generate_seed_script(
    table_order: list[str],
    seed_data: dict[str, list[dict[str, Any]]],
) -> str:
    """Generate a TypeScript seed script."""
    lines = [
        '// Auto-generated seed data — deterministic (seed=42)',
        '// Run: npx ts-node prisma/seed.ts',
        'import { PrismaClient } from "@prisma/client";',
        '',
        'const prisma = new PrismaClient();',
        '',
        'async function main() {',
    ]

    for table_name in table_order:
        records = seed_data.get(table_name, [])
        if not records:
            continue

        # camelCase the table name for Prisma client
        model_name = table_name[0].lower() + table_name[1:]
        lines.append(f'  // Seed {table_name} ({len(records)} records)')
        lines.append(f'  await prisma.{model_name}.createMany({{')
        lines.append(f'    data: {json.dumps(records, indent=6, default=str)},')
        lines.append('    skipDuplicates: true,')
        lines.append('  });')
        lines.append('')

    lines.extend([
        '  console.log("Seed complete");',
        '}',
        '',
        'main()',
        '  .catch((e) => {',
        '    console.error(e);',
        '    process.exit(1);',
        '  })',
        '  .finally(async () => {',
        '    await prisma.$disconnect();',
        '  });',
        '',
    ])

    return "\n".join(lines)


def _report_to_dict(report: SeedReport) -> dict:
    """Convert report to plain dict."""
    return {
        "passed": report.passed,
        "tables_seeded": report.tables_seeded,
        "total_records": report.total_records,
        "user_count": report.user_count,
        "seed_files": report.seed_files,
        "table_order": report.table_order,
        "warnings": report.warnings,
    }
