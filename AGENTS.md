# FORGE — Master Agent Context

## What This Project Is
FORGE is an AI-native full-stack application development platform.
Users arrive with an idea and leave with a live production application.
Guarantee: zero broken first builds through a 10-layer reliability system.

## Technology Stack

### Backend
- Python 3.12, FastAPI (fully async)
- Supabase PostgreSQL — application database (managed, PgBouncer pooler built in)
- Supabase Auth — JWT/HS256, OAuth flows, email-password, magic links
- Supabase Storage — all files: generated apps, build snapshots, screenshots
- SQLAlchemy 2.0 async + Alembic (always DATABASE_DIRECT_URL for migrations)
- supabase-py — SDK for auth admin operations and storage
- Inngest — durable event-driven background functions (replaces Trigger.dev)
  Served at: POST /api/inngest (mounted in main.py via inngest.fast_api.serve)
  Client: forge_inngest in backend/app/inngest_client.py
  Events use prefix: forge/ (e.g. forge/pipeline.run)
- Upstash Redis — caching, pub/sub, job queue
- Pinecone — semantic build cache + build memory
- LangGraph — multi-agent pipeline orchestration
- OpenTelemetry + Sentry + Prometheus

### Frontend
- React 18, Vite 5, TypeScript 5.4 strict, React Router v6
- @supabase/supabase-js — auth token management
- Zustand — all shared client state
- TanStack Query v5 — all server data fetching
- Monaco Editor, Tailwind CSS v3, Framer Motion
- React Hook Form + Zod, Cloudflare Pages

### Infrastructure
- Northflank — FastAPI backend containers (microVM) + Firecracker sandbox VMs (pre-warmed pool 20+)
  Northflank is compute ONLY. No database, auth, or storage.
- Cloudflare Workers — *.preview.forge.dev reverse proxy
- Cloudflare Durable Objects — HMR WebSocket relay
- Cloudflare KV — sandbox URL registry

## Services NOT in this stack — never reference these
- Trigger.dev — replaced by Inngest
- Nhost — replaced by Supabase
- Cloudflare R2 — replaced by Supabase Storage
- boto3 / botocore — replaced by supabase-py
- Fly.io — not used
- AWS S3 / amazonaws.com — not used

## Architecture Rules
1.  DB reads: get_read_session() only
2.  DB writes: get_write_session() only
3.  Alembic: DATABASE_DIRECT_URL only (pooler breaks DDL)
4.  JWT: HS256 + SUPABASE_JWT_SECRET, audience="authenticated"
5.  API keys: AES-256-GCM; key_iv, key_tag as LargeBinary
6.  Build agents: temperature=0, seed=42
7.  File coherence: ReviewAgent ONLY
8.  Storage: supabase-py — never boto3 or R2
9.  Inngest: send events via forge_inngest.send() — never import functions directly
10. Never hardcode secrets
11. TypeScript strict, zero any
12. Preview: file save → browser update < 700ms
13. Northflank: compute only

## Build Status
Phase: 1 — Foundation
Completed: none
Next: Session 1.1 — Backend core