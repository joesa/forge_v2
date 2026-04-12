"""Enable RLS on all tables with user-scoped policies

Revision ID: a3f8e1b2c4d6
Revises: 72589ef730ee
Create Date: 2026-04-11 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a3f8e1b2c4d6'
down_revision: Union[str, None] = '72589ef730ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Tables by ownership tier ────────────────────────────────────

# Tier 0: users — self-owned (id = auth.uid())
# Tier 1: Direct user_id column
TIER1_TABLES = [
    "ai_providers",
    "projects",
    "pipeline_runs",
    "builds",
    "editor_sessions",
    "chat_messages",
    "deployments",
    "idea_sessions",
    "ideas",
    "annotations",
    "preview_shares",
]

# Tier 2: Indirect via project_id → projects.user_id
TIER2_PROJECT_TABLES = [
    "build_snapshots",
    "sandboxes",
]

# Tier 3: Indirect via build_id → builds.user_id
TIER3_BUILD_TABLES = [
    "hot_fix_records",
    "performance_reports",
    "accessibility_reports",
    "coherence_reports",
]

# Tier 4: Indirect via pipeline_run_id → pipeline_runs.user_id
TIER4_PIPELINE_TABLES = [
    "agent_outputs",
]

ALL_TABLES = (
    ["users"]
    + TIER1_TABLES
    + TIER2_PROJECT_TABLES
    + TIER3_BUILD_TABLES
    + TIER4_PIPELINE_TABLES
)


def upgrade() -> None:
    # ── Enable RLS on every table ────────────────────────────────
    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Force RLS even for table owners (defense-in-depth)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # ── alembic_version — system table, block Data API access ────
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alembic_version FORCE ROW LEVEL SECURITY")
    # No policies = nobody via Data API can read/write
    # service_role bypasses RLS so Alembic still works

    # ── Tier 0: users — own row only ────────────────────────────
    op.execute("""
        CREATE POLICY users_select_own ON users
            FOR SELECT TO authenticated
            USING (id = auth.uid())
    """)
    op.execute("""
        CREATE POLICY users_update_own ON users
            FOR UPDATE TO authenticated
            USING (id = auth.uid())
            WITH CHECK (id = auth.uid())
    """)

    # ── Tier 1: Direct user_id tables ────────────────────────────
    for table in TIER1_TABLES:
        op.execute(f"""
            CREATE POLICY {table}_select_own ON {table}
                FOR SELECT TO authenticated
                USING (user_id = auth.uid())
        """)
        op.execute(f"""
            CREATE POLICY {table}_insert_own ON {table}
                FOR INSERT TO authenticated
                WITH CHECK (user_id = auth.uid())
        """)
        op.execute(f"""
            CREATE POLICY {table}_update_own ON {table}
                FOR UPDATE TO authenticated
                USING (user_id = auth.uid())
                WITH CHECK (user_id = auth.uid())
        """)
        op.execute(f"""
            CREATE POLICY {table}_delete_own ON {table}
                FOR DELETE TO authenticated
                USING (user_id = auth.uid())
        """)

    # ── Tier 2: Indirect via project_id ──────────────────────────
    for table in TIER2_PROJECT_TABLES:
        op.execute(f"""
            CREATE POLICY {table}_select_own ON {table}
                FOR SELECT TO authenticated
                USING (project_id IN (
                    SELECT id FROM projects WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_insert_own ON {table}
                FOR INSERT TO authenticated
                WITH CHECK (project_id IN (
                    SELECT id FROM projects WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_update_own ON {table}
                FOR UPDATE TO authenticated
                USING (project_id IN (
                    SELECT id FROM projects WHERE user_id = auth.uid()
                ))
                WITH CHECK (project_id IN (
                    SELECT id FROM projects WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_delete_own ON {table}
                FOR DELETE TO authenticated
                USING (project_id IN (
                    SELECT id FROM projects WHERE user_id = auth.uid()
                ))
        """)

    # ── Tier 3: Indirect via build_id ────────────────────────────
    for table in TIER3_BUILD_TABLES:
        op.execute(f"""
            CREATE POLICY {table}_select_own ON {table}
                FOR SELECT TO authenticated
                USING (build_id IN (
                    SELECT id FROM builds WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_insert_own ON {table}
                FOR INSERT TO authenticated
                WITH CHECK (build_id IN (
                    SELECT id FROM builds WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_update_own ON {table}
                FOR UPDATE TO authenticated
                USING (build_id IN (
                    SELECT id FROM builds WHERE user_id = auth.uid()
                ))
                WITH CHECK (build_id IN (
                    SELECT id FROM builds WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_delete_own ON {table}
                FOR DELETE TO authenticated
                USING (build_id IN (
                    SELECT id FROM builds WHERE user_id = auth.uid()
                ))
        """)

    # ── Tier 4: Indirect via pipeline_run_id ─────────────────────
    for table in TIER4_PIPELINE_TABLES:
        op.execute(f"""
            CREATE POLICY {table}_select_own ON {table}
                FOR SELECT TO authenticated
                USING (pipeline_run_id IN (
                    SELECT id FROM pipeline_runs WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_insert_own ON {table}
                FOR INSERT TO authenticated
                WITH CHECK (pipeline_run_id IN (
                    SELECT id FROM pipeline_runs WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_update_own ON {table}
                FOR UPDATE TO authenticated
                USING (pipeline_run_id IN (
                    SELECT id FROM pipeline_runs WHERE user_id = auth.uid()
                ))
                WITH CHECK (pipeline_run_id IN (
                    SELECT id FROM pipeline_runs WHERE user_id = auth.uid()
                ))
        """)
        op.execute(f"""
            CREATE POLICY {table}_delete_own ON {table}
                FOR DELETE TO authenticated
                USING (pipeline_run_id IN (
                    SELECT id FROM pipeline_runs WHERE user_id = auth.uid()
                ))
        """)

    # ── Service role bypass note ─────────────────────────────────
    # Supabase service_role bypasses RLS by default.
    # Our FastAPI backend connects with service_role, so it is unaffected.
    # These policies protect the Data API (PostgREST) and direct DB access.


def downgrade() -> None:
    # ── Drop all policies ────────────────────────────────────────

    # Tier 0: users
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")
    op.execute("DROP POLICY IF EXISTS users_update_own ON users")

    # Tier 1
    for table in TIER1_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_own ON {table}")

    # Tier 2
    for table in TIER2_PROJECT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_own ON {table}")

    # Tier 3
    for table in TIER3_BUILD_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_own ON {table}")

    # Tier 4
    for table in TIER4_PIPELINE_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_own ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_own ON {table}")

    # ── Disable RLS ──────────────────────────────────────────────
    for table in ALL_TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE alembic_version NO FORCE ROW LEVEL SECURITY")
