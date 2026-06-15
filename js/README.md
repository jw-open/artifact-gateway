# artifact-gateway-sdk

Browser client SDK for [**artifact-gateway**](https://github.com/jw-open/artifact-gateway) — the secure proxy for AI-generated artifact web apps.

An AI agent generates an HTML/JS "artifact" that runs in a **sandboxed iframe**. This SDK lets that artifact make **RBAC-scoped, authenticated** calls back through the gateway — without ever holding API keys — to:

- **external** third-party HTTPS APIs (CORS bypass + server-side credential vault)
- **internal** APIs (allowlisted paths)
- **isolated databases** (per-user / per-session DuckDB & MongoDB)
- **files** (per-user / per-session read/write/list/delete)
- **streaming** upstreams (SSE)
- **code execution** in a constrained sandbox (`run`)

The server side is the Python package [`artifact-gateway`](https://pypi.org/project/artifact-gateway/).

## Install

```bash
npm install artifact-gateway-sdk
```

Or load directly in an artifact via CDN (no build step):

```html
<script src="https://cdn.jsdelivr.net/npm/artifact-gateway-sdk/dist/artifact-gateway-sdk.js"></script>
```

## How it works

The **host page** (your app) renders the artifact in a sandboxed iframe and, after load, posts an init message:

```js
iframe.contentWindow.postMessage(
  { type: "artifact-gateway:init", token: "<short-lived app JWT>", proxyBase: "/api/app/" },
  "*"
);
```

Inside the artifact, the SDK captures the token (held **in memory only**) and exposes `window.artifactGateway`:

```html
<script src="https://cdn.jsdelivr.net/npm/artifact-gateway-sdk/dist/artifact-gateway-sdk.js"></script>
<script>
  // The token may arrive after your scripts run — gate calls on _onReady.
  window.artifactGateway._onReady = async () => {
    const r = await window.artifactGateway.external({
      method: "GET",
      url: "https://api.example.com/v1/data",
      credentialId: "my-api-key",      // resolved server-side; never inline secrets
    });
    console.log(r.status, r.body);
  };
</script>
```

> `window.ohwise` is kept as an alias of `window.artifactGateway` for OhWise compatibility.

## Programmatic (bundlers)

```js
import { createClient } from "artifact-gateway-sdk";

const gw = createClient({ token, proxyBase: "/api/app/" });
const rows = await gw.db.userQuery("analytics", "SELECT * FROM events WHERE ts > ?", ["2026-01-01"]);
```

## API

| Call | Purpose |
|------|---------|
| `external({method,url,headers,body,credentialId})` | third-party HTTPS (CORS bypass; secrets via `credentialId`) |
| `stream({...}, onChunk)` | SSE / token streams |
| `internal({method,path,body})` | allowlisted internal APIs |
| `db.userQuery/userExec/sessionQuery/sessionExec(db,sql,params)` | isolated DuckDB |
| `db.find/upsert/delete(collection, …)` | isolated MongoDB |
| `files.write/read/list/delete(path[,content])` (+ `session*`) | isolated file IO |
| `run(language, code, stdin)` | constrained code execution |
| `refresh()` | re-issue the app token (auto-called on 401) |

## Security notes

- The app token is a short-lived, RBAC-scoped JWT — keep it **in memory only**, never `localStorage`.
- **Never embed secrets** in the artifact — reference them by `credentialId`; the gateway injects them server-side from an encrypted vault.
- All calls are scope-checked at the gateway; external is HTTPS-only; internal is path-allowlisted; DB access is per-user/per-session isolated.

## License

Apache-2.0
