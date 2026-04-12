# FORGE — Copilot Standing Instructions

Before starting ANY task, read AGENTS.md in full.
For ALL frontend tasks, also read DESIGN_BRIEF.md in full.

## Architecture rules — never violate
1.  DB reads  → get_read_session() only
2.  DB writes → get_write_session() only
3.  Alembic migrations MUST use DATABASE_DIRECT_URL (not DATABASE_URL — pooler breaks DDL)
4.  JWT validation: HS256 using SUPABASE_JWT_SECRET — local decode, no network call
5.  User API keys: AES-256-GCM encrypted; key_iv and key_tag stored as LargeBinary
6.  Build agents: temperature=0, seed=42 (deterministic)
7.  File coherence engine: ReviewAgent ONLY — never in individual build agents 1-9
8.  Supabase Storage: use supabase-py SDK — never boto3, never R2, never amazonaws.com
9.  Inngest: event-driven jobs — send events via forge_inngest.send(), never call functions directly
10. Secrets: always from settings.SETTING_NAME — never hardcode
11. TypeScript: strict mode, zero 'any' types
12. Every page background: #04040a — if white, index.css Google Fonts import is not line 1
13. Northflank is compute only — all data lives in Supabase

## After every backend change
cd backend && pytest tests/ -v — fix every failure before reporting done

## After every frontend change
cd frontend && npm run typecheck — zero errors required

## After any SQLAlchemy model change
1. cd backend && alembic revision --autogenerate -m "<short description>"
2. Review the generated migration in backend/alembic/versions/ — verify it is correct
3. cd backend && alembic upgrade head
4. Run tests: cd backend && pytest tests/ -v

## Deployment checklist (run when asked to deploy)
### Backend (Northflank)
1. Ensure all tests pass: cd backend && pytest tests/ -v
2. Migrations must be run BEFORE deploying new code:
   cd backend && alembic upgrade head  (uses DATABASE_DIRECT_URL — never pooler)
3. Push to deploy branch — Northflank picks up container build automatically

### Frontend (Cloudflare Pages)
1. Typecheck: cd frontend && npm run typecheck
2. Build: cd frontend && npm run build
3. Push to deploy branch — Cloudflare Pages builds automatically

### Workers (Cloudflare Workers)
- Preview proxy lives in workers/preview-proxy/
- Deploy: cd workers/preview-proxy && npx wrangler deploy
- Each worker has its own wrangler.toml

### Inngest functions
- Functions are auto-discovered at /api/inngest endpoint
- Register new functions: add to the functions=[] array in backend/app/main.py inngest_serve() call
- Inngest syncs automatically when the backend deploys
- Local dev: run inngest dev server alongside backend

### Supabase (managed — no deploy needed for most things)
- Database migrations: Alembic only (see above)
- Auth config: Supabase dashboard only
- Storage buckets: created via supabase-py SDK or dashboard
- Edge Functions (if added later): cd supabase && supabase functions deploy <name>