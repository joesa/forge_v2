from pathlib import Path

from pydantic_settings import BaseSettings

_THIS_DIR = Path(__file__).resolve().parent  # backend/app/
_BACKEND_DIR = _THIS_DIR.parent  # backend/
_ROOT_DIR = _BACKEND_DIR.parent  # repo root


class Settings(BaseSettings):
    model_config = {
        "env_file": [str(_ROOT_DIR / ".env.local"), str(_BACKEND_DIR / ".env")],
        "extra": "ignore",
    }

    # ── App ──────────────────────────────────────────────────────
    FORGE_ENV: str = "development"
    FORGE_SECRET_KEY: str
    FORGE_ENCRYPTION_KEY: str
    FORGE_HMAC_SECRET: str

    # ── Supabase ─────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str  # Supabase pooler — runtime queries
    DATABASE_DIRECT_URL: str  # Supabase direct — Alembic migrations ONLY
    DATABASE_READ_URL: str = ""

    # ── Supabase Storage buckets ─────────────────────────────────
    SUPABASE_BUCKET_PROJECTS: str = "forge-projects"
    SUPABASE_BUCKET_SNAPSHOTS: str = "forge-snapshots"
    SUPABASE_BUCKET_SCREENSHOTS: str = "forge-screenshots"

    # ── Inngest ──────────────────────────────────────────────────
    INNGEST_EVENT_KEY: str = "local-dev"
    INNGEST_SIGNING_KEY: str = "signkey-dev-000000000"
    INNGEST_BASE_URL: str = ""

    # ── Northflank ───────────────────────────────────────────────
    NORTHFLANK_API_KEY: str = ""
    NORTHFLANK_PROJECT_ID: str = ""
    NORTHFLANK_BUILD_SERVICE_ID: str = "sandbox-image"
    NORTHFLANK_SANDBOX_PLAN: str = "nf-compute-200"
    FORGE_SERVICE_TOKEN: str = ""  # service-to-service auth for sandbox agent

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = ""

    # ── Cloudflare ───────────────────────────────────────────────
    CLOUDFLARE_ACCOUNT_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_KV_NAMESPACE_ID: str = ""
    PREVIEW_DOMAIN: str = "preview.forge.dev"

    # ── Pinecone ─────────────────────────────────────────────────
    PINECONE_API_KEY: str = ""
    PINECONE_INDEX: str = "forge-build-cache"

    # ── AI Providers ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GOOGLE_AI_API_KEY: str = ""

    # ── Monitoring ───────────────────────────────────────────────
    SENTRY_DSN: str = ""

    @property
    def effective_read_url(self) -> str:
        return self.DATABASE_READ_URL or self.DATABASE_URL


settings = Settings()
