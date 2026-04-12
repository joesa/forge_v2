/**
 * Preview proxy authentication — local-only, no network calls.
 *
 * Two auth strategies:
 *   1. Supabase JWT (HS256) — via cookie or Authorization header
 *   2. Share token — HMAC(sandbox_id + expires_at) via ?token= query param
 */

export interface Env {
  SUPABASE_JWT_SECRET: string;
  FORGE_HMAC_SECRET: string;
  SANDBOX_URLS: KVNamespace;
  PREVIEW_HMR: DurableObjectNamespace;
}

// ── JWT (HS256) ────────────────────────────────────────────────

function base64UrlDecode(str: string): Uint8Array {
  // Pad to multiple of 4
  const padded = str.replace(/-/g, "+").replace(/_/g, "/");
  const padding = "=".repeat((4 - (padded.length % 4)) % 4);
  const binary = atob(padded + padding);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function importHS256Key(secret: string): Promise<CryptoKey> {
  const enc = new TextEncoder();
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
}

interface JWTPayload {
  sub: string;
  exp: number;
  aud?: string;
  [key: string]: unknown;
}

export async function validateSupabaseJWT(
  token: string,
  supabaseJwtSecret: string,
): Promise<JWTPayload | null> {
  const parts = token.split(".");
  if (parts.length !== 3) return null;

  const [headerB64, payloadB64, signatureB64] = parts as [string, string, string];

  // Verify header is HS256
  try {
    const headerJson = new TextDecoder().decode(base64UrlDecode(headerB64));
    const header = JSON.parse(headerJson) as { alg?: string };
    if (header.alg !== "HS256") return null;
  } catch {
    return null;
  }

  // Verify signature
  const key = await importHS256Key(supabaseJwtSecret);
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = base64UrlDecode(signatureB64);

  const valid = await crypto.subtle.verify("HMAC", key, signature, data);
  if (!valid) return null;

  // Decode and check expiry
  try {
    const payloadJson = new TextDecoder().decode(base64UrlDecode(payloadB64));
    const payload = JSON.parse(payloadJson) as JWTPayload;

    const now = Math.floor(Date.now() / 1000);
    if (typeof payload.exp !== "number" || payload.exp < now) return null;

    return payload;
  } catch {
    return null;
  }
}

// ── Share Token (HMAC) ──────────────────────────────────────────

export async function validateShareToken(
  token: string,
  sandboxId: string,
  expiresAtUnix: number,
  hmacSecret: string,
): Promise<boolean> {
  // Both signature and expires_at are required
  if (!token || !expiresAtUnix) return false;

  // Check expiry first
  const now = Math.floor(Date.now() / 1000);
  if (expiresAtUnix < now) return false;

  // Verify HMAC: sign(sandbox_id + ":" + expires_at)
  const key = await importHS256Key(hmacSecret);
  const message = new TextEncoder().encode(`${sandboxId}:${expiresAtUnix}`);
  const expectedSig = await crypto.subtle.sign("HMAC", key, message);
  const expectedB64 = btoa(String.fromCharCode(...new Uint8Array(expectedSig)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

  // Constant-time comparison
  if (token.length !== expectedB64.length) return false;
  let mismatch = 0;
  for (let i = 0; i < token.length; i++) {
    mismatch |= token.charCodeAt(i) ^ expectedB64.charCodeAt(i);
  }
  return mismatch === 0;
}

// ── Extract token from request ──────────────────────────────────

export function extractJWTFromRequest(request: Request): string | null {
  // 1. Authorization: Bearer <token>
  const authHeader = request.headers.get("Authorization");
  if (authHeader?.startsWith("Bearer ")) {
    return authHeader.slice(7);
  }

  // 2. Cookie: sb-access-token=<token>
  const cookie = request.headers.get("Cookie");
  if (cookie) {
    const match = cookie.match(/sb-access-token=([^;]+)/);
    if (match?.[1]) return match[1];
    // Also check sb-<ref>-auth-token (Supabase default cookie name)
    const match2 = cookie.match(/sb-[^-]+-auth-token=([^;]+)/);
    if (match2?.[1]) {
      // The cookie value might be a base64-encoded JSON array [access_token, refresh_token]
      try {
        const decoded = JSON.parse(decodeURIComponent(match2[1]));
        if (Array.isArray(decoded) && typeof decoded[0] === "string") {
          return decoded[0] as string;
        }
      } catch {
        return match2[1];
      }
    }
  }

  return null;
}
