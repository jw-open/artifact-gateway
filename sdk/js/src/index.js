/**
 * artifact-sdk — browser client for artifact-gateway.
 *
 * An AI-generated artifact (HTML/JS running in a sandboxed iframe) uses this to
 * make secure, RBAC-scoped calls back through the gateway: external HTTPS APIs
 * (CORS bypass + credential vault), internal APIs (allowlisted), user/session
 * isolated DBs (DuckDB/Mongo), file IO, streaming, and code execution.
 *
 * Two ways to use it:
 *   • Browser <script> (auto): the host posts an init message; `window.ohwise`
 *     (and `window.artifactGateway`) appear automatically. See dist/ build.
 *   • Programmatic (bundlers): `createClient({ token, proxyBase })`.
 *
 * The app token is held in memory only — never persist it.
 */

/** Build the namespaced credential/proxy client. */
export function createClient({ token = null, proxyBase = "/api/app/" } = {}) {
  let _token = token;
  let _proxyBase = proxyBase;
  const setToken = (t) => { _token = t; };
  const setProxyBase = (b) => { if (b) _proxyBase = b; };

  const authHeaders = () => ({
    "Content-Type": "application/json",
    Authorization: "Bearer " + _token,
  });

  const refresh = () =>
    fetch(_proxyBase + "token/refresh", { method: "POST", headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && d.token) _token = d.token; return _token; });

  const proxyFetch = (type, payload) => {
    if (!_token) return Promise.reject(new Error("artifact-gateway token not yet received"));
    return fetch(_proxyBase + type, { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) })
      .then((r) => {
        if (r.status === 401) {
          return refresh().then(() =>
            fetch(_proxyBase + type, { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) }).then((rr) => rr.json())
          );
        }
        return r.json();
      });
  };

  const streamFetch = (payload, onChunk) => {
    if (!_token) return Promise.reject(new Error("artifact-gateway token not yet received"));
    return fetch(_proxyBase + "external/stream", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) })
      .then((r) => {
        const reader = r.body.getReader();
        const dec = new TextDecoder();
        const pump = () =>
          reader.read().then((res) => {
            if (res.done) return;
            if (onChunk) onChunk(dec.decode(res.value, { stream: true }));
            return pump();
          });
        return pump();
      });
  };

  return {
    setToken,
    setProxyBase,
    fetch: proxyFetch,
    refresh,
    external: (payload) => proxyFetch("external", payload),
    stream: (payload, onChunk) => streamFetch(payload, onChunk),
    internal: (payload) => proxyFetch("internal", payload),
    run: (language, code, stdin) => proxyFetch("run", { language, code, stdin: stdin || "" }),
    db: {
      userQuery: (db, sql, params) => proxyFetch("db/user/" + db + "/query", { sql, params: params || [] }),
      userExec: (db, sql, params) => proxyFetch("db/user/" + db + "/exec", { sql, params: params || [] }),
      sessionQuery: (db, sql, params) => proxyFetch("db/session/" + db + "/query", { sql, params: params || [] }),
      sessionExec: (db, sql, params) => proxyFetch("db/session/" + db + "/exec", { sql, params: params || [] }),
      find: (col, filter, limit) => proxyFetch("db/user/" + col + "/find", { filter: filter || {}, limit: limit || 100 }),
      upsert: (col, filter, update) => proxyFetch("db/user/" + col + "/upsert", { filter, update }),
      delete: (col, filter) => proxyFetch("db/user/" + col + "/delete", { filter }),
    },
    files: {
      write: (path, content) => proxyFetch("files/user/write", { path, content }),
      read: (path) => proxyFetch("files/user/read", { path }),
      list: (path) => proxyFetch("files/user/list", { path: path || "" }),
      delete: (path) => proxyFetch("files/user/delete", { path }),
      sessionWrite: (path, content) => proxyFetch("files/session/write", { path, content }),
      sessionRead: (path) => proxyFetch("files/session/read", { path }),
      sessionList: (path) => proxyFetch("files/session/list", { path: path || "" }),
      sessionDelete: (path) => proxyFetch("files/session/delete", { path }),
    },
  };
}

/**
 * Browser auto-install: listen for the host's init postMessage and expose the
 * client as `window.ohwise` (+ `window.artifactGateway`). The host sends:
 *   { type: "artifact-gateway:init" | "ohwise:init", token, proxyBase }
 * Set `window.ohwise._onReady` to run code once the token arrives.
 */
export function autoInstall() {
  if (typeof window === "undefined") return null;
  const client = createClient({ token: null, proxyBase: "/api/app/" });
  // expose under both names (generic + OhWise back-compat)
  client._onReady = null;
  window.artifactGateway = client;
  window.ohwise = client;
  window.addEventListener("message", (e) => {
    const d = e && e.data;
    if (d && (d.type === "artifact-gateway:init" || d.type === "ohwise:init")) {
      client.setToken(d.token);
      client.setProxyBase(d.proxyBase);
      if (typeof client._onReady === "function") client._onReady();
    }
  });
  return client;
}

export default { createClient, autoInstall };
