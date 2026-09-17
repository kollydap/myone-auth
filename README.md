# MyOne Auth

> A multi-tenant OAuth2 / OIDC identity provider and SSO platform, built from scratch in FastAPI.

**Status:** 🚧 Early development — Phase 0 (Foundation). Not production-ready. Follow along as it's built in public.

---

## What this is

MyOne Auth is a centralized identity provider modeled on how enterprise "app suite" platforms handle auth — think Zoho One, Google Workspace, or Microsoft 365's identity layer. One login, one session, access to every app in the suite without re-authenticating.

It supports:
- **Multi-tenant organizations** — users belong to orgs, orgs get assigned apps and roles
- **OAuth2 Authorization Code flow with PKCE** — the modern standard for delegated auth
- **OpenID Connect** — identity on top of OAuth2 (`/userinfo`, discovery document, JWKS)
- **Single sign-on** — a central session that multiple client apps delegate to
- **RBAC** — org-scoped roles, app-scoped permissions, audit logging
- **Client apps as first-class citizens** — any service can register and integrate against it, the same way you'd integrate against Auth0 or Zoho Accounts

## Why I'm building this

I'm a backend developer and architect working mostly in Django/DRF, and most of my auth experience has been *consuming* OAuth (Stripe, Flutterwave, Google login) — never *being* the identity provider on the other end of that handshake.

This project exists to close that gap properly, by implementing the actual spec myself rather than dropping in a library:

- **Authorization Code + PKCE**, end to end — not just calling `authlib`, but understanding why the code is single-use, why it's bound to a `redirect_uri`, and what attack each parameter in the flow prevents
- **Session and SSO design** — how "log in once, access everything" actually works under the hood (spoiler: it's not magic, it's a well-scoped cookie and a session store)
- **Token security in practice** — refresh token rotation, reuse detection, key rotation, and the failure modes that show up when you get any of it wrong
- **FastAPI + async SQLAlchemy** at a level deeper than CRUD — this is my first serious project outside Django, deliberately chosen so I'm not leaning on framework habits I already have

I'm treating this as a real system, not a toy — proper phased build plan, task-by-task, with acceptance criteria at each step, working through it with a tech-lead-style process rather than shipping generated code I don't fully understand. The goal is to come out the other side able to explain and defend every decision in this codebase, not just have it work.

If you're learning the same thing, the commit history and issues are meant to be readable — you should be able to watch the reasoning happen, not just the final state.

## Non-goals (for now)

- Not trying to replace Auth0/Keycloak/Zitadel for real production use — this is a learning vehicle first
- Not implementing every OAuth grant type — focused on Authorization Code + PKCE and Client Credentials
- SAML, MFA, and external IdP federation are stretch goals, not v1 scope

## Tech stack

| Layer | Choice |
|---|---|
| API framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Database | PostgreSQL |
| Session / cache | Redis |
| Auth crypto | Argon2 (passwords), RS256 JWTs (tokens) |
| Testing | pytest + httpx |
| Containerization | Docker + Docker Compose |

## Project status / roadmap

| Phase | Focus | Status |
|---|---|---|
| 0 | Foundation — scaffolding, Docker, config, migrations | 🚧 In progress |
| 1 | Identity core — users, orgs, sessions, password auth | ⬜ Not started |
| 2 | OAuth2 authorization server — `/authorize`, `/token`, PKCE, JWKS | ⬜ Not started |
| 3 | SSO proof — sample client apps, silent re-auth, logout semantics | ⬜ Not started |
| 4 | RBAC + admin — roles, org-app assignment, audit log | ⬜ Not started |
| 5 | Hardening — token rotation, reuse detection, rate limiting | ⬜ Not started |
| 6 | Stretch — MFA, SAML, external IdP federation | ⬜ Not started |

## Getting started (local dev)

```bash
git clone https://github.com/kollydap/myone-auth.git
cd myone-auth
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`. Health check at `/health`.

Run migrations:
```bash
docker compose exec api alembic upgrade head
```

Run tests:
```bash
docker compose exec api pytest
```

## Architecture

```
                    ┌─────────────────────┐
                    │   MyOne Auth (IdP)   │
                    │  FastAPI + Postgres  │
                    │       + Redis        │
                    └──────────┬───────────┘
                               │  OAuth2/OIDC
              ┌────────────────┼────────────────┐
              │                │                │
      ┌───────▼──────┐ ┌───────▼──────┐ ┌───────▼──────┐
      │  Sample App A │ │ Sample App B │ │  Your own    │
      │  (client)     │ │ (client)     │ │  services    │
      └───────────────┘ └──────────────┘ └──────────────┘
```

Full PRD and phased build plan are in [`/docs`](./docs).

## Contributing

This is primarily a personal learning project, but issues, questions, and PRs pointing out spec violations or security issues are genuinely welcome — that's exactly the kind of feedback that makes the learning stick.

## License

MIT — see [`LICENSE`](./LICENSE).

## Author

**Oladapo** ([Kolawole Oladapo Osagie](https://github.com/kollydap)) — Backend developer & architect, Lagos, Nigeria.
