/**
 * FORGE Sandbox Agent
 *
 * Lifecycle:
 *   1. Pull project files from Supabase Storage (via backend API)
 *   2. Write files to /app
 *   3. npm install
 *   4. Start Vite dev server on port 3000
 *   5. Subscribe to Redis file_sync:{sandbox_id} for live updates
 *   6. Expose health/control API on port 9999
 *
 * Env vars (set by Northflank):
 *   SANDBOX_ID          — this sandbox's UUID
 *   PROJECT_ID          — the project UUID
 *   REDIS_URL           — Redis connection string
 *   FORGE_API_URL       — backend API base URL (e.g. https://api.forge.dev)
 *   FORGE_SERVICE_TOKEN — service-to-service auth token
 */

import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import Redis from "ioredis";

const SANDBOX_ID = process.env.SANDBOX_ID;
const PROJECT_ID = process.env.PROJECT_ID;
const REDIS_URL = process.env.REDIS_URL;
const FORGE_API_URL = process.env.FORGE_API_URL || "http://localhost:8000";
const FORGE_SERVICE_TOKEN = process.env.FORGE_SERVICE_TOKEN || "";
const APP_DIR = "/app";
const AGENT_PORT = 9999;
const DEV_SERVER_PORT = 3000;

let devServerProcess = null;
let status = "booting"; // booting | pulling | installing | running | error
let lastError = "";

// ── 1. Pull files from backend API ─────────────────────────────

async function pullFiles() {
  status = "pulling";
  console.log(`[forge-agent] Pulling files for project ${PROJECT_ID}...`);

  try {
    // Fetch file list (API returns a nested tree)
    const listRes = await fetch(
      `${FORGE_API_URL}/api/v1/projects/${PROJECT_ID}/files`,
      { headers: { Authorization: `Bearer ${FORGE_SERVICE_TOKEN}` } },
    );

    if (!listRes.ok) {
      throw new Error(`Failed to list files: ${listRes.status} ${await listRes.text()}`);
    }

    const tree = await listRes.json();

    // Flatten tree → array of file nodes
    function flattenTree(nodes) {
      const flat = [];
      for (const node of nodes) {
        if (node.type === "file") {
          flat.push(node);
        } else if (node.children) {
          flat.push(...flattenTree(node.children));
        }
      }
      return flat;
    }
    const files = flattenTree(tree);

    // Download each file
    let pulled = 0;
    for (const file of files) {
      const contentRes = await fetch(
        `${FORGE_API_URL}/api/v1/projects/${PROJECT_ID}/files/content?path=${encodeURIComponent(file.path)}`,
        { headers: { Authorization: `Bearer ${FORGE_SERVICE_TOKEN}` } },
      );

      if (!contentRes.ok) {
        console.warn(`[forge-agent] Failed to fetch ${file.path}: ${contentRes.status}`);
        continue;
      }

      const data = await contentRes.json();
      const fullPath = join(APP_DIR, file.path);
      mkdirSync(dirname(fullPath), { recursive: true });
      writeFileSync(fullPath, data.content || "", "utf-8");
      pulled++;
    }

    console.log(`[forge-agent] Pulled ${pulled} files`);
  } catch (err) {
    console.error("[forge-agent] Pull failed:", err.message);
    status = "error";
    lastError = err.message;
    throw err;
  }
}

// ── 2. Install dependencies ─────────────────────────────────────

function npmInstall() {
  return new Promise((resolve, reject) => {
    status = "installing";
    console.log("[forge-agent] Running npm install...");

    const proc = spawn("npm", ["install", "--prefer-offline", "--no-audit"], {
      cwd: APP_DIR,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, NODE_ENV: "development" },
    });

    let stderr = "";
    proc.stdout.on("data", (d) => process.stdout.write(d));
    proc.stderr.on("data", (d) => {
      stderr += d.toString();
      process.stderr.write(d);
    });

    proc.on("close", (code) => {
      if (code === 0) {
        console.log("[forge-agent] npm install complete");
        resolve();
      } else {
        reject(new Error(`npm install exited with code ${code}: ${stderr.slice(-500)}`));
      }
    });

    proc.on("error", reject);
  });
}

// ── 3. Start dev server ─────────────────────────────────────────

function startDevServer() {
  console.log(`[forge-agent] Starting dev server on port ${DEV_SERVER_PORT}...`);

  // Detect framework — read package.json scripts
  let startCmd = "npx";
  let startArgs = ["vite", "--host", "0.0.0.0", "--port", String(DEV_SERVER_PORT)];

  const pkgPath = join(APP_DIR, "package.json");
  if (existsSync(pkgPath)) {
    try {
      const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"));
      const scripts = pkg.scripts || {};
      // If there's a custom dev script, use it
      if (scripts.dev) {
        startCmd = "npm";
        startArgs = ["run", "dev", "--", "--host", "0.0.0.0", "--port", String(DEV_SERVER_PORT)];
      }
    } catch { /* ignore parse errors, fall back to vite */ }
  }

  devServerProcess = spawn(startCmd, startArgs, {
    cwd: APP_DIR,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      PORT: String(DEV_SERVER_PORT),
      HOST: "0.0.0.0",
      NODE_ENV: "development",
    },
  });

  devServerProcess.stdout.on("data", (d) => process.stdout.write(d));
  devServerProcess.stderr.on("data", (d) => process.stderr.write(d));

  devServerProcess.on("close", (code) => {
    console.log(`[forge-agent] Dev server exited with code ${code}`);
    if (status === "running") {
      status = "error";
      lastError = `Dev server exited unexpectedly (code ${code})`;
    }
  });

  devServerProcess.on("error", (err) => {
    console.error("[forge-agent] Dev server failed to start:", err.message);
    status = "error";
    lastError = err.message;
  });

  status = "running";
}

// ── 4. Redis file sync subscriber ───────────────────────────────

function subscribeToFileSync() {
  if (!REDIS_URL) {
    console.warn("[forge-agent] No REDIS_URL — file sync disabled");
    return;
  }

  const sub = new Redis(REDIS_URL);
  const channel = `file_sync:${SANDBOX_ID}`;

  sub.subscribe(channel, (err) => {
    if (err) {
      console.error("[forge-agent] Redis subscribe error:", err.message);
      return;
    }
    console.log(`[forge-agent] Subscribed to ${channel}`);
  });

  sub.on("message", (_ch, message) => {
    try {
      const { path: filePath, content } = JSON.parse(message);
      const fullPath = join(APP_DIR, filePath);

      // Security: prevent path traversal
      if (!fullPath.startsWith(APP_DIR + "/")) {
        console.warn(`[forge-agent] Blocked path traversal: ${filePath}`);
        return;
      }

      mkdirSync(dirname(fullPath), { recursive: true });
      writeFileSync(fullPath, content, "utf-8");
      console.log(`[forge-agent] Synced: ${filePath}`);
    } catch (err) {
      console.error("[forge-agent] File sync error:", err.message);
    }
  });

  sub.on("error", (err) => {
    console.error("[forge-agent] Redis error:", err.message);
  });
}

// ── 5. Health/control API on port 9999 ──────────────────────────

function startHealthServer() {
  const server = createServer((req, res) => {
    const url = new URL(req.url, `http://localhost:${AGENT_PORT}`);

    if (url.pathname === "/health") {
      const healthy = status === "running";
      res.writeHead(healthy ? 200 : 503, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        status,
        sandbox_id: SANDBOX_ID,
        project_id: PROJECT_ID,
        error: lastError || undefined,
        uptime: process.uptime(),
      }));
      return;
    }

    if (url.pathname === "/status") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({
        status,
        sandbox_id: SANDBOX_ID,
        project_id: PROJECT_ID,
        dev_server_running: devServerProcess !== null && devServerProcess.exitCode === null,
        error: lastError || undefined,
      }));
      return;
    }

    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found" }));
  });

  server.listen(AGENT_PORT, "0.0.0.0", () => {
    console.log(`[forge-agent] Health API on :${AGENT_PORT}`);
  });
}

// ── Main ────────────────────────────────────────────────────────

async function main() {
  console.log(`[forge-agent] Starting — sandbox=${SANDBOX_ID} project=${PROJECT_ID}`);

  if (!SANDBOX_ID || !PROJECT_ID) {
    console.error("[forge-agent] SANDBOX_ID and PROJECT_ID are required");
    process.exit(1);
  }

  // Start health API immediately so Northflank can see us booting
  startHealthServer();

  try {
    await pullFiles();
    await npmInstall();
    startDevServer();
    subscribeToFileSync();
    console.log("[forge-agent] Ready — dev server on :3000, agent on :9999");
  } catch (err) {
    console.error("[forge-agent] Boot failed:", err.message);
    status = "error";
    lastError = err.message;
    // Don't exit — keep health endpoint running so we can debug
  }
}

main();
