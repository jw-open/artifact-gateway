/** artifact-sdk — type declarations. */

export interface ExternalRequest {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  url: string;            // must be https://
  headers?: Record<string, string>;
  body?: unknown;
  /** Resolve a stored secret server-side and inject it (never embed secrets). */
  credentialId?: string;
}
export interface ExternalResponse { status: number; headers: Record<string, string>; body: unknown; }

export interface InternalRequest {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  path: string;           // allowlisted /api/... path
  body?: unknown;
}

export interface QueryResult { columns: string[]; rows: unknown[][]; rowcount: number; }
export interface RunResult { stdout: string; stderr: string; exit_code: number | null; timed_out: boolean; }

export interface ArtifactGatewayClient {
  setToken(token: string): void;
  setProxyBase(base: string): void;
  fetch(type: string, payload: unknown): Promise<unknown>;
  refresh(): Promise<string | null>;
  external(req: ExternalRequest): Promise<ExternalResponse>;
  stream(req: ExternalRequest, onChunk: (text: string) => void): Promise<void>;
  internal(req: InternalRequest): Promise<unknown>;
  run(language: "python" | "javascript" | "bash", code: string, stdin?: string): Promise<RunResult>;
  db: {
    userQuery(db: string, sql: string, params?: unknown[]): Promise<QueryResult>;
    userExec(db: string, sql: string, params?: unknown[]): Promise<{ ok: boolean }>;
    sessionQuery(db: string, sql: string, params?: unknown[]): Promise<QueryResult>;
    sessionExec(db: string, sql: string, params?: unknown[]): Promise<{ ok: boolean }>;
    find(collection: string, filter?: Record<string, unknown>, limit?: number): Promise<{ data: unknown[]; count: number }>;
    upsert(collection: string, filter: Record<string, unknown>, update: Record<string, unknown>): Promise<{ ok: boolean; matched: number; modified: number; upserted: boolean }>;
    delete(collection: string, filter: Record<string, unknown>): Promise<{ ok: boolean; deleted: number }>;
  };
  files: {
    write(path: string, content: string): Promise<{ ok: boolean; path: string; bytes: number }>;
    read(path: string): Promise<{ path: string; content: string }>;
    list(path?: string): Promise<{ entries: Array<{ name: string; bytes: number | null }> }>;
    delete(path: string): Promise<{ ok: boolean }>;
    sessionWrite(path: string, content: string): Promise<{ ok: boolean; path: string; bytes: number }>;
    sessionRead(path: string): Promise<{ path: string; content: string }>;
    sessionList(path?: string): Promise<{ entries: Array<{ name: string; bytes: number | null }> }>;
    sessionDelete(path: string): Promise<{ ok: boolean }>;
  };
  /**
   * Recommended store for interactive apps: per-resource current state (versioned
   * upsert) plus an append-only history. Persist here, never localStorage.
   */
  state: {
    set(ns: string, resourceId: string, patch: Record<string, unknown>, expectedVersion?: number): Promise<{ ok: boolean; version: number }>;
    get(ns: string, resourceId: string): Promise<{ data: Record<string, unknown> | null }>;
    list(ns: string, filter?: Record<string, unknown>): Promise<{ data: unknown[]; count: number }>;
    remove(ns: string, resourceId: string): Promise<{ ok: boolean; deleted: number }>;
    history(ns: string, resourceId?: string, limit?: number): Promise<{ data: unknown[]; count: number }>;
  };
  /** Set this to run code once the host delivers the token (browser auto-install). */
  _onReady?: (() => void) | null;
}

export function createClient(opts?: { token?: string | null; proxyBase?: string }): ArtifactGatewayClient;
export function autoInstall(): ArtifactGatewayClient | null;

declare const _default: { createClient: typeof createClient; autoInstall: typeof autoInstall };
export default _default;

declare global {
  interface Window {
    artifactGateway?: ArtifactGatewayClient;
    /** Alias of artifactGateway (OhWise back-compat). */
    ohwise?: ArtifactGatewayClient;
  }
}
