# Retriever MCP OAuth Demo

Production-style reference implementation showing how **Retriever** integrates with **MCP** using **FastMCP** and an **OAuth 2.1 authorization-code + PKCE** consent flow hosted by Django.

This is intentionally small, but security boundaries match what you would migrate into a real Retriever application.

---

## 1. What this project demonstrates

- Claude Custom Connector → public MCP URL
- OAuth discovery (Protected Resource Metadata + Authorization Server Metadata)
- Retriever-hosted **login** (Django session + CSRF) and **consent**
- Authorization code → access token
- FastMCP validates the token, resolves user + organization, enforces scopes
- Tenant isolation via Retriever service layer (never trust `organization_id` from the model)

**Not demonstrated (and not desired):** Claude → API key → FastMCP.

---

## 2. Architecture

```mermaid
flowchart TB
    Claude[Claude MCP Client]
    MCP[FastMCP Resource Server /mcp]
    AS[Retriever OAuth Authorization Server]
    Login[Django Session Login]
    Consent[Retriever Consent Screen]
    Svc[Retriever Service Layer]
    DB[(PostgreSQL)]

    Claude -->|MCP Streamable HTTP| MCP
    MCP -->|401 + resource_metadata| Claude
    Claude -->|OAuth discovery| AS
    Claude -->|authorize PKCE| AS
    AS --> Login
    Login --> Consent
    Consent -->|authorization code| Claude
    Claude -->|token endpoint| AS
    AS -->|access token| Claude
    Claude -->|Bearer token| MCP
    MCP --> Svc
    Svc --> DB
```

Roles:

| Role | Component |
|------|-----------|
| OAuth Authorization Server | Django + django-oauth-toolkit |
| MCP Resource Server | FastMCP |
| MCP Client | Claude (custom connector) |
| Website login | Django sessions only (no JWT) |

---

## 3. Components

| Path | Responsibility |
|------|----------------|
| `accounts/` | Session login/logout/dashboard |
| `organizations/` | Org + membership + active org |
| `oauth_server/` | Discovery, consent override, DCR, connected apps |
| `mcp_server/` | FastMCP tools + token verifier |
| `retriever/` | Devices/orders models, services, audit, seed |
| `frontend/` | Vite React shell (Django still owns auth) |
| `config/asgi.py` | Mounts FastMCP at `/mcp` + Django |

---

## 4. OAuth flow

1. Claude POSTs to `/mcp` without a token.
2. Server returns **401** with  
   `WWW-Authenticate: Bearer resource_metadata="https://<host>/.well-known/oauth-protected-resource"`.
3. Claude fetches Protected Resource Metadata → learns authorization server + scopes.
4. Claude fetches `/.well-known/oauth-authorization-server`.
5. Browser opens `/o/authorize/` with PKCE (`S256`), `state`, `scope`, `resource`.
6. If no Django session → `/login/?next=<authorize URL>` (params preserved).
7. Consent Allow → authorization code redirect to  
   `https://claude.ai/api/mcp/auth_callback`.
8. Claude exchanges code (+ `code_verifier` + client credentials) at `/o/token/`.
9. Claude calls `/mcp` with `Authorization: Bearer <access_token>`.

---

## 5. Browser / session behavior

**Case A — already logged into Retriever:** authorize → consent (skip login).

**Case B — logged out:** authorize → login → return to same authorize URL → consent.

Session cookies: HttpOnly, SameSite=Lax, Secure when `DEBUG=false`.

---

## 6. Consent flow

Consent is a **Retriever-branded Django template** (`templates/oauth2_provider/authorize.html`).

- Shows signed-in user, active organization, human-readable scopes
- **Allow** records org binding (`OAuthAuthorizationContext`) and issues a code
- **Deny** returns `error=access_denied` (no code, no token)
- Client secret / access token / auth code never enter React or localStorage

---

## 7. MCP flow

- Transport: **Streamable HTTP** (MCP 2025-11-25)
- Flags: `stateless_http=True`, `json_response=True` (serverless-safe)
- Public endpoint: `https://<host>/mcp`

---

## 8. FastMCP authentication

`DjangoAccessTokenVerifier` validates opaque django-oauth-toolkit tokens **in-process** (ORM), avoiding self-HTTP introspection on Vercel cold starts.

Checks: token exists, not expired, audience/resource matches `MCP_RESOURCE_URL`, org context present.

---

## 9. User → organization resolution

At consent time, Retriever binds the user’s **active organization** into `OAuthAuthorizationContext`.

MCP tools read `organization_id` only from token claims. Tool arguments named `organization_id` are **ignored**.

---

## 10. Scope authorization

| Scope | Meaning | Tools |
|-------|---------|-------|
| `retriever.devices.read` | View devices | `get_devices` |
| `retriever.orders.read` | View orders | `get_deployment_orders`, `get_return_orders` |
| `retriever.orders.write` | Create demo orders | `create_test_deployment_order` |

---

## 11. Tenant isolation

```
token → user → organization (from consent) → service(organization_id=…) → ORM
```

Queries always filter by authenticated organization. Demonstrated in tests.

---

## 12. Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
npm install && npm run build   # optional React assets
python manage.py migrate
uvicorn config.asgi:application --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/signup/ to create an account (user + organization), or http://127.0.0.1:8000/login/ to sign in.

Optional sample data (devices, orders, pre-registered Claude OAuth client):

```bash
python manage.py seed_demo
```

Seed also creates `demo_user` / `DemoPassword123!` if you want a ready-made account; signup is enough for normal login.

---

## 13. Environment variables

See [`.env.example`](.env.example).

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Django secret |
| `PUBLIC_BASE_URL` | Issuer / metadata base URL |
| `MCP_RESOURCE_URL` | Canonical MCP resource (audience) |
| `DATABASE_URL` | Postgres; omit for SQLite |
| `ALLOWED_HOSTS` | Host allowlist |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins |

---

## 14. Database setup

- **Local default:** SQLite (`db.sqlite3`) when `DATABASE_URL` is empty
- **Vercel / production:** Postgres via `DATABASE_URL` (Neon, Vercel Postgres, or Supabase)

### Step 1 — Create Postgres and verify with `psql`

1. Create a project in [Neon](https://neon.tech), Vercel Postgres, or similar.
2. Copy the connection string (include `?sslmode=require` for Neon).
3. Put it in `.env` (local) and later in Vercel env vars:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

4. Test the connection (credentials go only in your shell / `.env`, never in git):

```bash
# Using the env var from .env
set -a && source .env && set +a
psql "$DATABASE_URL"
```

Or paste the URI directly:

```bash
psql "postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require"
```

You should get a `psql` prompt. Type `\q` to quit.

5. Apply Django schema:

```bash
python manage.py migrate
```

---

## 15. Seed demo data

```bash
python manage.py seed_demo
```

Creates user, orgs, devices, orders, and OAuth client **Claude Retriever Demo**.  
**Client secret is printed once** — store it; it is hashed in the DB.

---

## 16. Connect this demo to Claude

Official docs:

- [Custom connectors (remote MCP)](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [Authentication for connectors](https://claude.com/docs/connectors/building/authentication)

### Steps

1. Deploy or tunnel so the app is on **public HTTPS** reachable from Anthropic IPs (`160.79.104.0/21`).
2. Note MCP URL: `https://<your-host>/mcp`
3. Run `python manage.py seed_demo` and copy **Client ID** + **Client Secret**.
4. In Claude (Pro/Max): **Customize → Connectors → Add custom connector**.
5. Paste the MCP URL.
6. **Advanced settings:** paste OAuth Client ID and Client Secret.
7. Click **Add**, then **Connect**.
8. Browser opens Retriever:
   - If already logged in → consent
   - Else → login → consent
9. Click **Allow Access**.
10. Claude completes token exchange.
11. Enable the connector in a chat and ask e.g. “List my Retriever devices”.

### Redirect URI (do not invent)

Registered by seed:

```
https://claude.ai/api/mcp/auth_callback
```

(Claude Code loopback URIs are also allowlisted for local tooling.)

### Terminology

| Term | Meaning |
|------|---------|
| OAuth Client ID + Client Secret | Identify/authenticate the **OAuth client** (Claude) |
| Access Token | Authorized access granted by the **user** after consent |

These are **not** “two API keys”.

---

## 17. Vercel deployment

Vercel officially supports Django via the Python runtime (ASGI preferred).

### Files

- [`vercel.json`](vercel.json) — `maxDuration` for `config/asgi.py`
- [`pyproject.toml`](pyproject.toml) — build runs `npm install && npm run build`

### Steps

**Step 1 — Postgres (do this first)**

1. Create Neon / Vercel Postgres.
2. Copy connection URI into Vercel env as `DATABASE_URL` (and optionally into local `.env`).
3. Verify: `psql "$DATABASE_URL"` then `\q`.

**Step 2 — Vercel project + env**

1. Create a Vercel project from this repo.
2. Set env vars (Production):

| Variable | Example (replace with yours) |
|----------|------------------------------|
| `DEBUG` | `false` |
| `SECRET_KEY` | long random string |
| `DATABASE_URL` | `postgresql://...@...neon.tech/neondb?sslmode=require` |
| `PUBLIC_BASE_URL` | `https://your-app.vercel.app` |
| `MCP_RESOURCE_URL` | `https://your-app.vercel.app/mcp` |
| `ALLOWED_HOSTS` | `your-app.vercel.app,.vercel.app` |
| `CSRF_TRUSTED_ORIGINS` | `https://your-app.vercel.app` |
| `MCP_REQUIRE_AUDIENCE` | `true` |

3. If URL unknown yet: deploy once, copy URL, update `PUBLIC_BASE_URL` / `MCP_RESOURCE_URL` / hosts, redeploy.

**Step 3 — Deploy**

```bash
npx vercel --prod
```

**Step 4 — Migrate + seed against prod DB**

```bash
set -a && source .env && set +a   # or export DATABASE_URL=...
python manage.py migrate
python manage.py seed_demo
```

Save the printed OAuth **Client ID** and **Client Secret**.

### Vercel limitations (documented, not hidden)

| Limitation | Mitigation in this demo |
|------------|-------------------------|
| No long-lived process | `stateless_http=True` |
| SSE streaming unreliable | `json_response=True` (JSON responses) |
| Function timeout | Keep OAuth/MCP under Claude’s ~10s discovery/token budgets; `maxDuration=60` |
| Ephemeral disk | All state in Postgres |
| Cold starts | In-process token verification (no self-HTTP introspect) |

WebSockets are not required for this demo.

---

## 18. Testing

```bash
pytest
```

Coverage includes session auth, OAuth (PKCE, deny/allow, code reuse, discovery), token audience, tenant isolation, MCP 401 challenge, connected-app revoke.

---

## 19. Troubleshooting

| Symptom | Check |
|---------|--------|
| Claude “couldn’t reach MCP server” | Public HTTPS; PRM 401 header; Anthropic IP allowlist |
| Consent never appears | User must complete browser login; check `next=` preserve |
| `invalid_client` | Client ID/secret from seed; Advanced settings filled |
| `invalid_grant` | Code expired (60s) or reused; PKCE verifier mismatch |
| Empty devices | Org binding at consent; active org when allowing |
| 401 after Disconnect | Expected — tokens revoked |

---

## 20. Security notes

- CSRF on session forms
- HttpOnly session cookies; Secure in production
- PKCE S256 required
- Redirect URI allowlist
- Short-lived auth codes; rotating refresh tokens
- Scoped access; audience validation
- No logging of passwords, tokens, secrets, or codes
- Client secrets hashed at rest

---

## 21. Migrating to production Retriever

Keep these boundaries:

1. Django session AS + branded consent (never hand login UI to the AI platform)
2. FastMCP as RS with token verification + scope checks
3. Org from consent/token context only
4. Business logic in service layer

Swap demo models for real Retriever apps; keep OAuth client registration + connected-apps UX.

---

## References

- [MCP Authorization (2025-11-25)](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [MCP Transports — Streamable HTTP](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)
- [Claude: Authentication for connectors](https://claude.com/docs/connectors/building/authentication)
- [Claude: Custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)
- [FastMCP Authentication](https://gofastmcp.com/servers/auth/authentication)
- [FastMCP Token Verification](https://gofastmcp.com/servers/auth/token-verification)
- [django-oauth-toolkit](https://django-oauth-toolkit.readthedocs.io/)
- [Vercel Django](https://vercel.com/docs/frameworks/full-stack/django)
- [RFC 9728 Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728)
- [RFC 8414 Authorization Server Metadata](https://www.rfc-editor.org/rfc/rfc8414)
- [RFC 8707 Resource Indicators](https://www.rfc-editor.org/rfc/rfc8707)
- [RFC 7591 Dynamic Client Registration](https://www.rfc-editor.org/rfc/rfc7591)
