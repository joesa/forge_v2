# ─────────────────────────────────────────────────────────────────
# FORGE Sandbox — Container Image
# Runs inside each Northflank sandbox VM.
# Boots a Vite dev server and listens for file-sync events via Redis.
# ─────────────────────────────────────────────────────────────────
FROM node:20-slim

# Install Python for backend-capable sandboxes & curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The file-sync agent (Node.js script that subscribes to Redis pub/sub)
COPY agent/ /opt/forge-agent/
RUN cd /opt/forge-agent && npm ci --omit=dev

# Health check endpoint (port 9999)
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:9999/health || exit 1

# Ports:
#   3000 — app dev server (Vite or custom)
#   9999 — forge agent health/control API
#   24678 — Vite HMR WebSocket
EXPOSE 3000 9999 24678

# Entry point: forge agent boots → pulls files from storage → starts dev server
CMD ["node", "/opt/forge-agent/index.mjs"]
