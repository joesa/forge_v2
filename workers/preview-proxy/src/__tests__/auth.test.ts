/**
 * Unit tests for preview-proxy auth module.
 * Tests: tampered expires_at fails, expired JWT fails.
 */
import { describe, it, expect } from "vitest";

// ── We need the Web Crypto API for these tests ──────────────────
// Node 20+ has globalThis.crypto — vitest should pick it up.

const TEST_JWT_SECRET = "test-supabase-jwt-secret-key-for-unit-tests";
const TEST_HMAC_SECRET = "test-forge-hmac-secret-key-for-unit-tests";

// ── Helpers to create test tokens ───────────────────────────────

function base64UrlEncode(data: Uint8Array | ArrayBuffer): string {
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlEncodeString(str: string): string {
  return base64UrlEncode(new TextEncoder().encode(str));
}

async function createHS256JWT(
  payload: Record<string, unknown>,
  secret: string,
): Promise<string> {
  const header = base64UrlEncodeString(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const body = base64UrlEncodeString(JSON.stringify(payload));
  const data = new TextEncoder().encode(`${header}.${body}`);

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, data);
  return `${header}.${body}.${base64UrlEncode(sig)}`;
}

async function createShareToken(
  sandboxId: string,
  expiresAt: number,
  secret: string,
): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const message = new TextEncoder().encode(`${sandboxId}:${expiresAt}`);
  const sig = await crypto.subtle.sign("HMAC", key, message);
  return base64UrlEncode(sig);
}

// ── Dynamic import of auth module (avoids Workers types issue) ──

async function getAuthModule() {
  return await import("../auth");
}

// ── JWT Tests ───────────────────────────────────────────────────

describe("validateSupabaseJWT", () => {
  it("accepts a valid JWT with future exp", async () => {
    const { validateSupabaseJWT } = await getAuthModule();
    const futureExp = Math.floor(Date.now() / 1000) + 3600;
    const token = await createHS256JWT(
      { sub: "user-123", exp: futureExp, aud: "authenticated" },
      TEST_JWT_SECRET,
    );

    const result = await validateSupabaseJWT(token, TEST_JWT_SECRET);
    expect(result).not.toBeNull();
    expect(result?.sub).toBe("user-123");
    expect(result?.exp).toBe(futureExp);
  });

  it("rejects an expired JWT", async () => {
    const { validateSupabaseJWT } = await getAuthModule();
    const pastExp = Math.floor(Date.now() / 1000) - 3600;
    const token = await createHS256JWT(
      { sub: "user-123", exp: pastExp, aud: "authenticated" },
      TEST_JWT_SECRET,
    );

    const result = await validateSupabaseJWT(token, TEST_JWT_SECRET);
    expect(result).toBeNull();
  });

  it("rejects a JWT signed with the wrong secret", async () => {
    const { validateSupabaseJWT } = await getAuthModule();
    const token = await createHS256JWT(
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
      "wrong-secret",
    );

    const result = await validateSupabaseJWT(token, TEST_JWT_SECRET);
    expect(result).toBeNull();
  });

  it("rejects a tampered JWT payload", async () => {
    const { validateSupabaseJWT } = await getAuthModule();
    const token = await createHS256JWT(
      { sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 },
      TEST_JWT_SECRET,
    );

    // Tamper with the payload (change a character in the middle segment)
    const parts = token.split(".");
    const tamperedPayload = parts[1]!.slice(0, -1) + (parts[1]!.slice(-1) === "A" ? "B" : "A");
    const tampered = `${parts[0]}.${tamperedPayload}.${parts[2]}`;

    const result = await validateSupabaseJWT(tampered, TEST_JWT_SECRET);
    expect(result).toBeNull();
  });

  it("rejects malformed tokens", async () => {
    const { validateSupabaseJWT } = await getAuthModule();

    expect(await validateSupabaseJWT("", TEST_JWT_SECRET)).toBeNull();
    expect(await validateSupabaseJWT("not.a.jwt", TEST_JWT_SECRET)).toBeNull();
    expect(await validateSupabaseJWT("only-one-part", TEST_JWT_SECRET)).toBeNull();
  });

  it("rejects non-HS256 algorithm (alg header check)", async () => {
    const { validateSupabaseJWT } = await getAuthModule();
    // Manually craft a token with alg: "none"
    const header = base64UrlEncodeString(JSON.stringify({ alg: "none", typ: "JWT" }));
    const payload = base64UrlEncodeString(
      JSON.stringify({ sub: "user-123", exp: Math.floor(Date.now() / 1000) + 3600 }),
    );
    const fakeToken = `${header}.${payload}.`;

    const result = await validateSupabaseJWT(fakeToken, TEST_JWT_SECRET);
    expect(result).toBeNull();
  });
});

// ── Share Token Tests ───────────────────────────────────────────

describe("validateShareToken", () => {
  it("accepts a valid share token", async () => {
    const { validateShareToken } = await getAuthModule();
    const sandboxId = "sandbox-abc-123";
    const expiresAt = Math.floor(Date.now() / 1000) + 3600;
    const token = await createShareToken(sandboxId, expiresAt, TEST_HMAC_SECRET);

    const result = await validateShareToken(token, sandboxId, expiresAt, TEST_HMAC_SECRET);
    expect(result).toBe(true);
  });

  it("rejects an expired share token", async () => {
    const { validateShareToken } = await getAuthModule();
    const sandboxId = "sandbox-abc-123";
    const expiresAt = Math.floor(Date.now() / 1000) - 3600; // expired
    const token = await createShareToken(sandboxId, expiresAt, TEST_HMAC_SECRET);

    const result = await validateShareToken(token, sandboxId, expiresAt, TEST_HMAC_SECRET);
    expect(result).toBe(false);
  });

  it("rejects a token with tampered expires_at", async () => {
    const { validateShareToken } = await getAuthModule();
    const sandboxId = "sandbox-abc-123";
    const realExpiresAt = Math.floor(Date.now() / 1000) + 3600;
    const token = await createShareToken(sandboxId, realExpiresAt, TEST_HMAC_SECRET);

    // Attacker tries to extend expiry
    const tamperedExpiresAt = realExpiresAt + 86400;
    const result = await validateShareToken(token, sandboxId, tamperedExpiresAt, TEST_HMAC_SECRET);
    expect(result).toBe(false);
  });

  it("rejects a token with wrong sandbox_id", async () => {
    const { validateShareToken } = await getAuthModule();
    const sandboxId = "sandbox-abc-123";
    const expiresAt = Math.floor(Date.now() / 1000) + 3600;
    const token = await createShareToken(sandboxId, expiresAt, TEST_HMAC_SECRET);

    // Attacker uses token for a different sandbox
    const result = await validateShareToken(token, "sandbox-other-456", expiresAt, TEST_HMAC_SECRET);
    expect(result).toBe(false);
  });

  it("rejects a token signed with wrong secret", async () => {
    const { validateShareToken } = await getAuthModule();
    const sandboxId = "sandbox-abc-123";
    const expiresAt = Math.floor(Date.now() / 1000) + 3600;
    const token = await createShareToken(sandboxId, expiresAt, "wrong-secret");

    const result = await validateShareToken(token, sandboxId, expiresAt, TEST_HMAC_SECRET);
    expect(result).toBe(false);
  });

  it("rejects empty token or zero expires_at", async () => {
    const { validateShareToken } = await getAuthModule();
    expect(await validateShareToken("", "sandbox-123", 0, TEST_HMAC_SECRET)).toBe(false);
    expect(await validateShareToken("sometoken", "sandbox-123", 0, TEST_HMAC_SECRET)).toBe(false);
  });
});

// ── Token Extraction Tests ──────────────────────────────────────

describe("extractJWTFromRequest", () => {
  it("extracts from Authorization Bearer header", async () => {
    const { extractJWTFromRequest } = await getAuthModule();
    const req = new Request("https://test.preview.forge.dev/", {
      headers: { Authorization: "Bearer my-jwt-token-here" },
    });
    expect(extractJWTFromRequest(req)).toBe("my-jwt-token-here");
  });

  it("extracts from sb-access-token cookie", async () => {
    const { extractJWTFromRequest } = await getAuthModule();
    const req = new Request("https://test.preview.forge.dev/", {
      headers: { Cookie: "sb-access-token=cookie-jwt-value; other=thing" },
    });
    expect(extractJWTFromRequest(req)).toBe("cookie-jwt-value");
  });

  it("returns null when no auth present", async () => {
    const { extractJWTFromRequest } = await getAuthModule();
    const req = new Request("https://test.preview.forge.dev/");
    expect(extractJWTFromRequest(req)).toBeNull();
  });
});
