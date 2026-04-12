/**
 * PreviewHMR — Durable Object for bidirectional HMR WebSocket relay.
 *
 * Relays Vite HMR messages between browser and sandbox (port 24678).
 * Handles sandbox disconnects with reconnect backoff and browser keepalive.
 */

import type { Env } from "./auth";

const VITE_HMR_PORT = 24678;
const MAX_RECONNECT_ATTEMPTS = 5;
const INITIAL_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;
const BROWSER_KEEPALIVE_MS = 30_000;

interface HMRSession {
  browserWs: WebSocket;
  sandboxWs: WebSocket | null;
  sandboxUrl: string;
  reconnectAttempts: number;
  reconnectTimer: number | null;
  keepaliveTimer: number | null;
  closed: boolean;
}

export class PreviewHMR implements DurableObject {
  private session: HMRSession | null = null;
  private state: DurableObjectState;

  constructor(state: DurableObjectState, _env: Env) {
    this.state = state;
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const sandboxUrl = url.searchParams.get("sandboxUrl");

    if (!sandboxUrl) {
      return new Response("Missing sandboxUrl parameter", { status: 400 });
    }

    if (request.headers.get("Upgrade") !== "websocket") {
      return new Response("Expected WebSocket", { status: 426 });
    }

    const pair = new WebSocketPair();
    const [client, server] = [pair[0], pair[1]];

    this.state.acceptWebSocket(server);
    await this.setupRelay(server, sandboxUrl);

    return new Response(null, { status: 101, webSocket: client });
  }

  private async setupRelay(
    browserWs: WebSocket,
    sandboxUrl: string,
  ): Promise<void> {
    // Close any existing session
    this.cleanup();

    this.session = {
      browserWs,
      sandboxWs: null,
      sandboxUrl,
      reconnectAttempts: 0,
      reconnectTimer: null,
      keepaliveTimer: null,
      closed: false,
    };

    await this.connectToSandbox();
  }

  private async connectToSandbox(): Promise<void> {
    const session = this.session;
    if (!session || session.closed) return;

    try {
      // Connect to sandbox Vite HMR WebSocket
      const wsUrl = this.buildSandboxWsUrl(session.sandboxUrl);
      const resp = await fetch(wsUrl, {
        headers: { Upgrade: "websocket" },
      });

      const sandboxWs = resp.webSocket;
      if (!sandboxWs) {
        throw new Error("Failed to establish WebSocket to sandbox");
      }

      sandboxWs.accept();
      session.sandboxWs = sandboxWs;
      session.reconnectAttempts = 0;

      // Sandbox → Browser
      sandboxWs.addEventListener("message", (event) => {
        if (!session.closed && session.browserWs.readyState === WebSocket.READY_STATE_OPEN) {
          session.browserWs.send(
            typeof event.data === "string" ? event.data : event.data,
          );
        }
      });

      // Sandbox disconnect
      sandboxWs.addEventListener("close", () => {
        session.sandboxWs = null;

        if (!session.closed) {
          // Notify browser about server restart
          this.sendToBrowser(session, JSON.stringify({ type: "server-restart" }));
          this.scheduleReconnect();
        }
      });

      sandboxWs.addEventListener("error", () => {
        try { sandboxWs.close(); } catch { /* ignore */ }
      });
    } catch {
      // Connection failed — schedule reconnect
      if (!session.closed) {
        this.scheduleReconnect();
      }
    }
  }

  private buildSandboxWsUrl(sandboxUrl: string): string {
    // sandboxUrl is like "http://10.0.0.5:3000" — convert to ws and add HMR port
    const url = new URL(sandboxUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.port = String(VITE_HMR_PORT);
    return url.toString();
  }

  private scheduleReconnect(): void {
    const session = this.session;
    if (!session || session.closed) return;

    session.reconnectAttempts++;

    if (session.reconnectAttempts > MAX_RECONNECT_ATTEMPTS) {
      // Give up — close browser connection
      this.sendToBrowser(
        session,
        JSON.stringify({
          type: "error",
          message: "Sandbox unreachable after max reconnection attempts",
        }),
      );
      this.cleanup();
      return;
    }

    // Backoff: 1s, 2s, 4s, 8s, 16s (capped at 30s)
    const backoff = Math.min(
      INITIAL_BACKOFF_MS * Math.pow(2, session.reconnectAttempts - 1),
      MAX_BACKOFF_MS,
    );

    session.reconnectTimer = setTimeout(() => {
      session.reconnectTimer = null;
      this.connectToSandbox();
    }, backoff) as unknown as number;
  }

  private sendToBrowser(session: HMRSession, data: string): void {
    try {
      if (session.browserWs.readyState === WebSocket.READY_STATE_OPEN) {
        session.browserWs.send(data);
      }
    } catch {
      /* browser already gone */
    }
  }

  // Called by the runtime for WebSocket messages from the browser
  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer): Promise<void> {
    const session = this.session;
    if (!session || session.closed) return;

    // Browser → Sandbox
    if (session.sandboxWs) {
      try {
        session.sandboxWs.send(
          typeof message === "string" ? message : message,
        );
      } catch {
        /* sandbox ws may be closing */
      }
    }
  }

  // Called by the runtime when browser WebSocket closes
  async webSocketClose(
    ws: WebSocket,
    _code: number,
    _reason: string,
    _wasClean: boolean,
  ): Promise<void> {
    const session = this.session;
    if (!session) return;

    // Browser disconnected — keep sandbox WS alive for 30s in case browser reconnects
    session.keepaliveTimer = setTimeout(() => {
      this.cleanup();
    }, BROWSER_KEEPALIVE_MS) as unknown as number;
  }

  async webSocketError(ws: WebSocket, error: unknown): Promise<void> {
    this.cleanup();
  }

  private cleanup(): void {
    const session = this.session;
    if (!session) return;

    session.closed = true;

    if (session.reconnectTimer !== null) {
      clearTimeout(session.reconnectTimer);
      session.reconnectTimer = null;
    }

    if (session.keepaliveTimer !== null) {
      clearTimeout(session.keepaliveTimer);
      session.keepaliveTimer = null;
    }

    if (session.sandboxWs) {
      try { session.sandboxWs.close(); } catch { /* ignore */ }
      session.sandboxWs = null;
    }

    try { session.browserWs.close(); } catch { /* ignore */ }

    this.session = null;
  }
}
