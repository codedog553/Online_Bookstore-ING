# @agentserver — Bookstore Agent Microservice

This repository contains the `agentserver` microservice: a conversational intelligent agent that
bridges the frontend and the backend catalog/cart data. It combines a language model (DeepSeek)
with local data and domain logic to provide fact‑aware chat, recommendations and a safe,
confirm‑then‑execute cart mutation flow.

![Architecture](diagram.png)

## Contents

```text
agentserver/
├─ app/
│  ├─ api.py                # FastAPI routes
│  ├─ config.py             # Settings (pydantic)
│  ├─ container.py          # DI container and shared components
│  ├─ db.py                 # SQLAlchemy session factory
│  ├─ logging_config.py     # audit/runtime loggers
│  ├─ main.py               # app factory, middleware
│  ├─ models.py             # SQLAlchemy ORM models
│  ├─ schemas.py            # Pydantic request/response models
│  ├─ security.py           # JWT / CSRF / confirmation tokens
│  ├─ services/
│  │  ├─ conversations.py   # ephemeral conversation store
│  │  ├─ deepseek.py        # LLM integration + fallbacks
│  │  ├─ filters.py         # input sanitization
│  │  ├─ rate_limit.py      # rate limiting + QPS gate
│  │  └─ skills.py          # skill implementations (book_lookup, cart_guard)
│  └─ repositories/
│     ├─ cart.py            # cart CRUD operations
│     └─ catalog.py         # catalog search & heuristics
├─ tests/
│  └─ test_api.py
├─ .env.example
└─ requirements.txt
```

---

## 1. Context

- Purpose: provide a conversational assistant that can answer book queries, recommend books, and safely guide users through cart operations.
- Placement: sits between the SPA frontend and the backend datastore and may call an external LLM provider (DeepSeek).
- Boundaries:
  - Read: liberal access to catalog fields for search/recommendation.
  - Write: strictly limited to cart CRUD for the current authenticated session; no payment, order, or admin operations.

Key behavior summary:
- Chat (general): LLM handles natural conversation.
- Catalog queries: agent augments LLM replies with local catalog search results.
- Cart actions: agent only plans and requests confirmation; mutations occur via dedicated endpoints with token checks and audit logging.

Relevant files: `app/api.py`, `app/services/deepseek.py`, `app/services/skills.py`, `app/repositories/catalog.py`, `app/repositories/cart.py`.

---

## 2. Design Overview

Architecture (summary):

- Frontend SPA -> POST `/chat` -> Agent Server
- Agent Server -> (optionally) DeepSeek LLM for planning & reply composition
- Agent Server -> Database (read replicas for search; write DB for cart mutations)

Communication channels:
- REST (FastAPI) between frontend and `agentserver`
- HTTP (httpx) between `agentserver` and DeepSeek API
- SQLAlchemy sessions to the DB (read/write sessionmakers)

Component responsibilities:
- `app/main.py`: bootstrap, middleware (CORS, HTTPS redirect, secure headers)
- `app/api.py`: request handling, orchestration, rate checks, CSRF/confirmation enforcement
- `app/container.py`: build and expose shared services (deepseek, skills, loggers, locks)
- `app/services/deepseek.py`: LLM calls (plan_chat, suggest_cart_action, compose_book_answer), local fallbacks
- `app/services/skills.py`: BookLookupSkill (intent + catalog lookup), CartGuardSkill (confirmation text)
- `app/services/conversations.py`: in‑memory conversation store with TTL and max message window
- `app/repositories/*`: database access and business validations for catalog and cart
- `app/security.py`: JWT parsing, CSRF, confirmation token generation/verification
- `app/logging_config.py`: runtime and rotating audit logger

Notes on communication and trust:
- Conversation binding: conversations are bound to owner keys (`user:{id}` or `anon:{ip}`) to prevent cross-user reuse.
- LLM outputs are expected to provide strict JSON for planners; otherwise, the service uses deterministic fallbacks.

---

## 3. Business Logic

Primary use cases:

1. Natural conversation and small talk (intent: `general_chat`).
2. Catalog lookup (intent: `catalog_lookup`) — factual answers grounded in local DB.
3. Recommendation (intent: `catalog_recommendation`) — heuristic scoring + catalog snapshot.
4. Cart guidance (intent: `cart_help`) — explain how to modify cart.
5. Cart actions (intent: `cart_action`) — plan add/update/remove operations and require explicit confirmation.

Data flow (chat → catalog → cart):

1. Client sends POST `/chat` with `{ message, conversation_id? }`.
2. Agent validates input, binds conversation owner, appends user message to `ConversationStore`.
3. Agent calls `DeepSeekService.plan_chat(...)` to get intent + flags.
4. If needed, agent queries `catalog.search_books(...)` and `catalog.list_catalog(...)`.
5. Agent calls `DeepSeekService.suggest_cart_action(...)` and `DeepSeekService.compose_book_answer(...)` to build reply and `action_suggestion`.
6. If the suggestion indicates a cart mutation, the frontend obtains a confirmation preview via cart endpoints and presents a modal to the user.
7. On user approval the frontend submits the cart mutation with `confirmation_token`; agent verifies and executes the DB transaction.

Decision rules and safeguards:
- The LLM is used for intent planning and message composition, but cart mutations require a signed confirmation token, CSRF verification, and an authenticated user (JWT).
- All cart mutations operate under per‑resource asyncio locks to prevent concurrent race conditions.
- Audit logging records the actor, action, and details (`agentserver.audit` logger).

Example workflow — add item to cart (short):

1. User: "I want to buy a hardcover of X" → frontend POST `/chat`.
2. Agent returns `action_suggestion` (action=`add`, requires_confirmation=true) and reply text.
3. Frontend requests preview: POST `/cart/add` with `confirmed=false` → agent returns `confirmation_message` and `confirmation_token`.
4. Frontend shows modal; user confirms.
5. Frontend POST `/cart/add` with `confirmed=true` and `confirmation_token` → agent verifies token and executes `cart_repo.add_item` inside DB transaction.

API surface (high-level):
- `GET /health` — health + DeepSeek status
- `GET /csrf-token` — issue CSRF token (sets `agent_csrf` cookie)
- `POST /chat` — main conversational endpoint
- `GET /cart` — list current user's cart
- `POST /cart/add` — preview or commit add (confirmed flag)
- `PUT /cart/update` — preview or commit update
- `DELETE /cart/remove` — preview or commit remove

---

## 4. Technical Stack

- Language: Python 3.9+
- Web: FastAPI, Uvicorn
- ORM: SQLAlchemy 2.x (sync sessions)
- Config: pydantic v2 + pydantic-settings
- LLM client: httpx
- Auth: JWT via `python-jose`
- Testing: pytest
- Frontend client: Vue 3 + Vite (see `frontend/src/api/agent.ts`)

Dependencies are listed in `requirements.txt`.

Operational & recommended tools:
- Local DB: SQLite by default; PostgreSQL recommended for production.
- Observability: Prometheus + Grafana (recommended), Sentry for error tracking
- Shared state: Redis (recommended for conversation store, distributed locks, rate limiter) in multi-node deployments
- Deployment: Docker, Kubernetes, reverse proxy (NGINX) and TLS termination

---

## 5. Implementation Highlights

Core patterns
- Agent style: "Chatbot + Tools" — LLM handles language tasks; skills and repositories are the tools that access facts and act on data.
- Light CQRS: separate `read_sessionmaker` and `write_sessionmaker` allow wiring read replicas and a dedicated write DB/role.
- Confirm‑then‑execute: cart writes require a short‑lived signed confirmation token and CSRF protection.

Concurrency model
- FastAPI async endpoints run non‑blocking code.
- Blocking DB operations use `starlette.concurrency.run_in_threadpool(...)`.
- `AsyncQpsGate` limits DeepSeek QPS; `SlidingWindowRateLimiter` enforces per-client rate limits.
- In‑process `asyncio.Lock` instances (via `container.locks`) serialize critical cart operations per resource.

Error handling
- Domain validation errors raise `HTTPException` with appropriate status codes.
- DB writes run under `with db.begin()` to ensure transactional integrity.
- LLM call errors (timeouts / request errors) are logged and fall back to deterministic heuristics when possible.

Security
- Authentication: JWT tokens parsed by `app/security.py`.
- CSRF: matching header + cookie issued by `/csrf-token` and validated on write endpoints.
- Confirmation tokens: signed JWTs with short expiry issued for cart previews and validated on commit.
- Input sanitization: `validate_safe_text` and `escape_text` to avoid script injection.
- HTTP security headers are added by middleware (`Content-Security-Policy`, `X-Frame-Options`, etc.).

Scalability
- Single-node caveats: conversation store, rate limiter and locks are in‑memory today; move to Redis to scale horizontally.
- To scale the LLM integration, tune `DEEPSEEK_QPS` and add circuit breakers or bulkhead patterns if needed.

Extensibility
- Skills are a clear plugin boundary (`app/services/skills.py`). Adding a new skill requires implementing `run(ctx, db, ...)` and exposing it via `SkillRegistry`.

---

## Quick Start (developer)

1. Install and run locally

```bash
cd agentserver
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8011
# Open: http://localhost:8011/docs
```

2. Run tests

```bash
pytest -q
```

3. Set the frontend env for local integration

Add to `frontend/.env.local`:

```env
VITE_AGENT_API_BASE_URL=http://localhost:8011
```

---

## Examples

Get a CSRF token (authenticated):

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8011/csrf-token
```

Chat example (anonymous):

```bash
curl -X POST http://localhost:8011/chat -H "Content-Type: application/json" \
  -d '{"message":"请介绍三体"}'
```

Cart add preview and commit (authenticated):

```bash
# 1) Preview (confirmed=false)
curl -X POST http://localhost:8011/cart/add \
  -H "Authorization: Bearer <JWT>" \
  -H "X-CSRF-Token: <csrf>" \
  -H "Content-Type: application/json" \
  -d '{"sku_id":100,"quantity":2,"confirmed":false}'

# 2) Commit (confirmed=true with confirmation_token from preview response)
curl -X POST http://localhost:8011/cart/add \
  -H "Authorization: Bearer <JWT>" \
  -H "X-CSRF-Token: <csrf>" \
  -H "Content-Type: application/json" \
  -d '{"sku_id":100,"quantity":2,"confirmed":true,"confirmation_token":"<token>"}'
```

---

## Files & Entry Points

- App factory: `app/main.py`
- Routes: `app/api.py` (chat + cart endpoints)
- LLM: `app/services/deepseek.py`
- Skills: `app/services/skills.py`
- Repositories: `app/repositories/catalog.py`, `app/repositories/cart.py`
- Models: `app/models.py`
- Settings: `app/config.py`

---

## Next Steps and Recommendations

1. For production: use PostgreSQL, run Alembic migrations and configure connection pooling.
2. Replace in‑memory conversation store, locks and rate limiter with Redis for multi‑instance safety.
3. Add Prometheus metrics, centralized structured logs, and Sentry for error monitoring.
4. Add a Dockerfile and Kubernetes manifests for deployment automation.

---

## References

- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/
- pydantic v2: https://docs.pydantic.dev/
- httpx: https://www.python-httpx.org/
- python-jose: https://github.com/mpdavis/python-jose

If you need a diagram file, add `diagram.png` next to this README or generate one from the architecture described above.
