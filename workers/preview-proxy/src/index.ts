/**
 * Preview Proxy — Cloudflare Worker entry point.
 *
 * Routes: *.preview.forge.dev/*
 *
 * Flow:
 *   1. Extract sandbox_id from subdomain
 *   2. Authenticate (JWT cookie or ?token= HMAC share token)
 *   3. KV lookup: sandbox:{id}:url → sandbox internal URL
 *   4. WebSocket upgrade → route to PreviewHMR Durable Object
 *   5. HTTP requests → proxy to sandbox
 */

import {
  type Env,
  extractJWTFromRequest,
  validateSupabaseJWT,
  validateShareToken,
} from "./auth";

export { PreviewHMR } from "./hmr-relay";

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    try {
      return await handleRequest(request, env, ctx);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Internal error";
      return new Response(JSON.stringify({ error: message }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }
  },
};

async function handleRequest(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const url = new URL(request.url);

  // ── 1. Extract sandbox_id from subdomain ──────────────────────
  // Expected: {sandbox_id}.preview.forge.dev
  const host = url.hostname;
  const sandboxId = extractSandboxId(host);
  if (!sandboxId) {
    return jsonResponse(400, { error: "Invalid preview URL — expected {sandbox_id}.preview.forge.dev" });
  }

  // ── 2. Authenticate ───────────────────────────────────────────
  const authResult = await authenticate(request, sandboxId, env);
  if (!authResult.ok) {
    return jsonResponse(401, { error: authResult.reason });
  }

  // ── 3. KV lookup for sandbox URL ──────────────────────────────
  const kvKey = `sandbox:${sandboxId}:url`;
  const sandboxUrl = await env.SANDBOX_URLS.get(kvKey);
  if (!sandboxUrl) {
    return jsonResponse(404, { error: "Sandbox not found or not running" });
  }

  // ── 4. WebSocket upgrade → Durable Object ─────────────────────
  if (request.headers.get("Upgrade") === "websocket") {
    return handleWebSocket(request, env, sandboxId, sandboxUrl);
  }

  // ── 5. HTTP → proxy to sandbox ────────────────────────────────
  return proxyRequest(request, url, sandboxUrl, ctx);
}

// ── Helpers ─────────────────────────────────────────────────────

function extractSandboxId(hostname: string): string | null {
  // {sandbox_id}.preview.forge.dev → sandbox_id
  const match = hostname.match(/^([a-zA-Z0-9_-]+)\.preview\.forge\.dev$/);
  return match?.[1] ?? null;
}

interface AuthResult {
  ok: boolean;
  reason: string;
}

async function authenticate(
  request: Request,
  sandboxId: string,
  env: Env,
): Promise<AuthResult> {
  // Strategy 1: JWT from cookie or Authorization header
  const jwt = extractJWTFromRequest(request);
  if (jwt) {
    const payload = await validateSupabaseJWT(jwt, env.SUPABASE_JWT_SECRET);
    if (payload) {
      return { ok: true, reason: "" };
    }
    // JWT present but invalid — don't fall through to share token
    return { ok: false, reason: "Invalid or expired JWT" };
  }

  // Strategy 2: Share token via query params
  const url = new URL(request.url);
  const token = url.searchParams.get("token");
  const expiresAt = url.searchParams.get("expires_at");

  if (token && expiresAt) {
    const expiresAtUnix = parseInt(expiresAt, 10);
    if (isNaN(expiresAtUnix)) {
      return { ok: false, reason: "Invalid expires_at value" };
    }

    const valid = await validateShareToken(
      token,
      sandboxId,
      expiresAtUnix,
      env.FORGE_HMAC_SECRET,
    );
    if (valid) {
      return { ok: true, reason: "" };
    }
    return { ok: false, reason: "Invalid or expired share token" };
  }

  return { ok: false, reason: "Authentication required — provide JWT or share token" };
}

async function handleWebSocket(
  request: Request,
  env: Env,
  sandboxId: string,
  sandboxUrl: string,
): Promise<Response> {
  const doId = env.PREVIEW_HMR.idFromName(sandboxId);
  const stub = env.PREVIEW_HMR.get(doId);

  // Forward to Durable Object with sandbox URL
  const doUrl = new URL(request.url);
  doUrl.searchParams.set("sandboxUrl", sandboxUrl);
  return await stub.fetch(new Request(doUrl.toString(), request));
}

async function proxyRequest(
  request: Request,
  originalUrl: URL,
  sandboxUrl: string,
  ctx: ExecutionContext,
): Promise<Response> {
  // Build target URL: replace origin with sandbox URL, keep path + query
  const target = new URL(originalUrl.pathname + originalUrl.search, sandboxUrl);

  // Forward request with original headers (minus Host)
  const headers = new Headers(request.headers);
  headers.delete("Host");
  headers.set("X-Forwarded-Host", originalUrl.hostname);
  headers.set("X-Forwarded-Proto", originalUrl.protocol.replace(":", ""));

  const proxyReq = new Request(target.toString(), {
    method: request.method,
    headers,
    body: request.body,
    redirect: "manual",
  });

  const response = await fetch(proxyReq);

  // Copy response with CORS headers for preview
  const respHeaders = new Headers(response.headers);
  respHeaders.set("X-Forge-Sandbox", "true");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: respHeaders,
  });
}

function jsonResponse(status: number, body: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
