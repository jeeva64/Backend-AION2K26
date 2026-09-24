# AGENTS.md

Notes for OpenCode sessions working in this repo. Read `readme.md`, `db.md`,
`integrations.md`, `RULES.md`, and `MIGRATION.md` first for routes, schemas,
the client-facing response envelope, participant-facing rules, and the
MongoDB→PostgreSQL migration — this file only captures what those don't say.
`RULES.md` is the published rulebook (harmonized symposium circular + website
rules, event date 07/10/2026): documentation only — it never changes behavior;
when editing it, re-check `EVENT_MAX_TEAM_SIZE`, `EVENT_SLOT_MAP`,
`MAX_STUDENTS_PER_LEADER`, and the ₹200 fee in code.

Docs are synced with code: `readme.md` + `integrations.md` document all **29**
endpoints (including `/admin/changepassword`,
`PUT /admin/college/{collegeId}`, `GET /admin/leader-college-depts`,
`PUT/GET /admin/registration-deadline` and the
nine registration-payment endpoints) and the Postgres stack; `db.md` is a
legacy MongoDB reference kept for the migration window (banner at top).

## Stack

Python 3.11 / FastAPI 0.115 / **SQLAlchemy 2.0 + asyncpg (Neon PostgreSQL)** /
Alembic / Pydantic 2 / pydantic-settings 2.15 / slowapi / PyJWT / bcrypt /
boto3 (Neon Object Storage, S3-compatible). The data layer is Neon PostgreSQL;
the legacy Motor/Mongo code under `app/db/mongo.py` and `app/repositories/`
is dormant (kept for the migration window, gated on `MONGO_RETAIN=true`).
Payment proofs are stored in a private Neon Object Storage bucket
(`PROOF_STORAGE_BACKEND=neon`); local disk is used for dev/tests. No linter,
formatter, typechecker, or build step is configured — verification is
`pytest` only.

## Commands (Windows; venv style used by the docs)

```bash
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -r requirements-dev.txt   # pytest/httpx/pytest-asyncio/psycopg2-binary
.venv\Scripts\python -m alembic upgrade head                    # apply SQL schema
.venv\Scripts\python -m alembic downgrade base                  # drop everything
.venv\Scripts\python run.py                                     # uvicorn + reload (only when ENVIRONMENT=development)
.venv\Scripts\python -m pytest tests -v
.venv\Scripts\python -m pytest tests\db_constraints_test.py -v      # single file
.venv\Scripts\python -m pytest tests\e2e_api_test.py::test_full_flow -v  # single test
.venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"
.venv\Scripts\python scripts\seed_reference_data.py            # re-seed events/slots (idempotent)
.venv\Scripts\python scripts\migrate_mongo_to_postgres.py      # one-time data migration; --force / --dry-run
```

There is no `Makefile`, `tox.ini`, or `setup.cfg`. `pytest.ini` sets
`asyncio_mode=auto` — async test functions don't need `@pytest.mark.asyncio`
explicitly.

## Test prerequisites (non-obvious)

- **PostgreSQL must be running** at `localhost:5432` with a role
  `aion:aion` (CREATEDB). The `tests/conftest.py` session fixture drops
  the `aion_pytest_test` database's tables, then runs `alembic upgrade head`
  to rebuild them — exercising the real Alembic migration. It then seeds
  one Super Admin (`SA1` / `Admin@12345`, `role: 1`).
- The autouse `_clear_registrations` fixture truncates `event_registrations`
  between tests so stats queries don't leak across tests. **It doesn't wipe
  users/admins/colleges** — when writing a new test that registers a leader,
  use a unique `college` string (or different `department`/`shift`) to avoid
  colliding with the slot-conflict rule. It truncates `payments`,
  `payment_audit`, and `event_settings` too, and wipes the local proof dir.
- **Rate limiting is forced off** by conftest (`RATE_LIMIT_ENABLED=false`) so
  the in-memory limiter can't interfere with the TestClient; payment-proof
  storage is forced to the local-disk backend (`PROOF_STORAGE_BACKEND=local`,
  scratch dir under `PROOF_LOCAL_DIR`) — tests never touch Neon Object Storage
  or need cloud credentials.
- `tests/migration_test.py` self-skips when MongoDB is unreachable so the
  rest of the suite runs in Mongo-less environments.

## First-run bootstrap (chicken-and-egg)

`/admin/adminreg` requires a Super Admin token, so the first Super Admin
must be created out-of-band against Postgres:

```bash
.venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"
```

It writes directly to PostgreSQL via `DATABASE_URL` from `.env` and aborts if
the `adminId` already exists. The legacy Mongo variant is
`scripts/create_super_admin_mongo.py` (kept for the migration window).

## Schema is owned by Alembic

All tables, indexes, CHECKs, FKs, and the `trg_bid_mayhem` trigger are created
by `alembic/versions/0001_initial_schema.py`. Do **not** hand-edit the schema
or call `Base.metadata.create_all` in production — add a new Alembic revision
instead. `event_slots` (3 rows: 1, 2, BOTH) and `events` (8 rows from
`EVENT_SLOT_MAP`) are seeded by the same migration.

Revision chain: `0001_initial_schema` → `0002_seed_super_admin` (intentional
no-op; bootstrap Super Admin comes from the explicit seeder script) →
`0003_bid_mayhem_bidirectional` (replaces the `enforce_bid_mayhem_exclusivity`
function body via CREATE OR REPLACE so `trg_bid_mayhem` rejects a `'BOTH'`-slot
event in **either** column when the other is populated) →
`0004_registration_payments` (additive: `event_registrations.status` with
legacy rows backfilled `'CONFIRMED'`, plus `payments` + `payment_audit`) →
`0005_event_settings` (additive: `event_settings` singleton table with
`registration_deadline TIMESTAMPTZ`).

## Repo-critical invariants (do not regress)

- **API field names stay camelCase** even though DB columns are snake_case.
  The Next.js frontend depends on `leaderId`, `registerNumber`,
  `foodPreference`, `event1`/`slot1`/`event2`/`slot2`, `totalStudents`,
  `registeredEvents`, `deletedCount`, etc. Pydantic uses camelCase aliases on
  top of snake_case SQLAlchemy columns — keep the alias when adding fields.
- **Collection/table names are still frozen** to the legacy set:
  `users`, `admins`, `colleges`, `events` (now used as a reference table, not
  the legacy one), `event_slots` (new), `event_registrations`,
  `event_settings` (new, singleton row for registration deadline).
- **Validation failures must return `400`, not `422`**, with the exact
  Express-era message. The custom handlers in
  `app/exceptions/handlers.py` override FastAPI's default `RequestValidationError`
  behavior to preserve frontend compatibility. Don't "fix" them to return
  `422`. The `/addcollege` route signature is deliberately `colleges: list[dict]`
  (no Pydantic model) to keep the 400-not-422 contract.
- **`foodPreference` is captured once**, on student creation, and never
  overwritten when the student is added to a second event. See
  `app/services/registration_sqla.py`.
- **Bid Mayhem occupies both slots** — enforced both at the service layer
  (`app/services/registration_sqla.py`) AND at the DB level by the
  `trg_bid_mayhem` PL/pgSQL trigger, which since revision `0003` is
  **bidirectional**: a row is rejected when either event column holds a
  `'BOTH'`-slot event while the other is populated (the same-slot CHECK alone
  can't catch `event2 = Bid Mayhem`, since `'1'/'2' <> 'BOTH'`). The slot map in
  `app/utils/constants.py` is the single source of truth for which event
  belongs to which slot; the `events`+`event_slots` reference tables are
  seeded from it.
- **Max 2 events per student** is declarative: `event1_id`/`event2_id` are
  wide columns (not a join table), with CHECKs ensuring event2/slot2 pairing,
  distinct events, and no same-slot clash.
- `register_team` runs in a single SQL transaction; on any exception the
  session rolls back. The Mongo-era manual compensation block is gone.
- **Money is integer paise** (`expectedAmountPaises`, etc.) — never floats,
  never rupee decimals. Fee = `settings.REGISTRATION_FEE_PER_STUDENT_PAISE`
  (default 20000 = Rs.200) × `COUNT(DISTINCT upper(register_number))`; the
  calculation lives ONLY in `app/services/fees.py` — never duplicate it in a
  router or trust any frontend amount.
- **Registration/payment state machines are guarded**:
  `event_registrations.status`: PAYMENT_PENDING → VERIFICATION_PENDING →
  CONFIRMED, with rejection reverting rows to PAYMENT_PENDING;
  `payments.payment_status`: PENDING → VERIFICATION_PENDING → SUCCESS /
  REJECTED (REJECTED → VERIFICATION_PENDING via Super Admin reopen). Every
  transition is an UPDATE with a `WHERE status = ...` guard — rowcount 0 means
  409, never a silent overwrite.
- **All `/admin/payments*` endpoints are Super Admin-only** (`adminRole: 1`);
  moderators get 403 there by design (unlike view/delete team endpoints).
- **UTR** is trimmed, uppercased, validated `^[A-Za-z0-9]{8,22}$`, and UNIQUE
  across payments via a partial index; duplicates return 409 through a
  SAVEPOINT catch (never leak raw IntegrityError as 500).
- **Payment proofs are private**: content-sniffed with Pillow (JPEG/PNG/WebP),
  size-capped, stored under a server-generated key
  `payment-proofs/{leader}/{payment}/{uuid}.{ext}` in Neon Object Storage
  (`neon` backend) or local disk (`local`); admins access them only via
  authenticated endpoints (signed URL or authorized stream). Never expose
  public URLs.
- **Verification is atomic**: verify/reject/reopen update the payment row,
  flip all the leader's registration statuses, and append `payment_audit` in
  one session transaction (`get_db` commits or rolls back as a unit).
- **Per-event team size limits**: `EVENT_MAX_TEAM_SIZE` in `app/utils/constants.py`
  defines max participants per event (e.g. VisionX: 1, Crazy Sell: 4). Enforced
  in `register_team()` before any writes. Exceeding returns `400`.
- **Registration deadline**: admin-set global deadline stored in `event_settings`
  singleton row (id=1). Blocks `/regleader` and `/registerteam` after deadline.
  Payment proof submission (`/payments/proof`) is still allowed after the deadline.
- **Post-verification expansion**: after SUCCESS, leader can register more students
  (new rows = PAYMENT_PENDING). Supplementary proof via `/payments/proof` transitions
  `SUCCESS → VERIFICATION_PENDING` for the payment row.

## Config fail-fast

`app/config/settings.py` reads `.env` via pydantic-settings. On startup
`settings.validate_secrets()` (called from `connect_to_db`) raises if
`DATABASE_URL` is missing or not a `postgresql*` DSN, or if `JWT_SECRET` is
shorter than 16 chars. The app pings Postgres (`SELECT 1`) during the FastAPI
lifespan and aborts if unreachable. `.env` is gitignored; copy
`.env.example`. `extra="ignore"` is set, so unknown env vars won't crash
startup. `MONGO_URI` is now optional (only the migration script needs it).

## Important entrypoints

- `app/main.py` — app factory, middleware stack order, exception wiring, router
  mounts (`auth` at root, `admin` at `/admin`). Lifespan connects/closes the
  SQLAlchemy engine (and optionally Mongo when `MONGO_RETAIN=true`).
- `app/db/sqlalchemy.py` — async engine + `async_sessionmaker` + `get_db`
  FastAPI dependency (commits on success, rolls back on exception).
- `app/models_sqla/` — SQLAlchemy ORM models (snake_case columns). Separate
  from the Pydantic doc-models in `app/models/` (legacy reference).
- `app/repositories_sqla/` — async repositories returning plain **dicts**
  (camelCase keys), mirroring the original Mongo repo method names. The
  repository base + per-collection repos share the injected `AsyncSession`.
- `app/repositories_sqla/event_registration_repository.py` — hydrates rows to
  camelCase dicts via `_hydrate_many`, which resolves the events/slots maps
  **once per call**. Never reintroduce a per-row map lookup (that was an N+1:
  two extra SELECTs for every returned document).
- `app/repositories_sqla/event_settings_repository.py` — get/set deadline
  for the `event_settings` singleton row (id=1).
- `app/services/registration_sqla.py` — the only non-trivial business logic
  (team registration, slot rules, Bid Mayhem exclusivity, 15-student cap,
  per-event team size limits, single-transaction rollback).
- `app/services/payment_sqla.py` — payment workflow (proof submission with
  Pillow content-sniffing, guarded verify/reject/reopen, edit lock,
  race-safe payment upsert via SAVEPOINT). Status transitions live here only.
  Supplementary payment flow: allows SUCCESS→VERIFICATION_PENDING when leader
  has pending registrations.
- `app/services/fees.py` — the single source of truth for fee math, UTR
  normalization/validation and the UPI intent URI.
- `app/storage/proof_storage.py` — proof storage behind a protocol:
  `B2Storage` (boto3 S3-compatible, private bucket) / `LocalStorage`
  (dev/tests). Factory keyed on `PROOF_STORAGE_BACKEND`; never bypass it.
- `app/services/stats_sqla.py` — SQL GROUP BY equivalents of the original
  Mongo aggregation pipelines (`dashboard_stats`, `view_event_regs`).
  `eventCounts` comes from one set-based query (UNION ALL of both event
  columns joined to `events`, GROUP BY name) — don't loop per-event COUNTs.
  `count_leader_event` (SQLA repo) and the `literal_column` import there are
  intentionally retained for future use — don't flag or remove them.
- `app/api/auth.py` and `app/api/admin.py` — all 18 route handlers; thin layer
  over services + repositories. `IntegrityError` from SQLAlchemy replaces
  `pymongo.errors.DuplicateKeyError`.
- `app/utils/serializers.py` + `app/utils/response.py` — `MongoJSONResponse`
  still serializes `datetime`/`ObjectId`-ish values; set as
  `default_response_class` on the app. Keep this when adding endpoints.
- `alembic/env.py` — async Alembic env, reads `DATABASE_URL` from settings.

## Future RAG extension (do not implement yet)

The `public` schema holds transactional data only. The future AION chatbot's
RAG layer lives in its own schema (e.g. `rag`) with `pgvector` enabled by a
**later** `alembic revision` — `CREATE EXTENSION pgvector` and embedding
tables (`rag.event_documents`, `rag.chunks`). See `MIGRATION.md` §7 for
the integration points and the suggested extension layout. Payment records,
UTRs and proof metadata are private transactional data — they must NEVER be
indexed into or exposed through the future RAG knowledge base.

## Rate limiting gotchas

`slowapi` uses an **in-memory** store valid only for a single uvicorn
process. With `--reload` or multiple workers, limits are per-process and
not shared. For multi-worker deployments wire a shared Redis `storage_uri`
(see slowapi docs). Default `RATE_LIMIT_ENABLED=false` — enable explicitly
in production via `.env`. Health is `@limiter.exempt`.

## Deployment

The backend deploys to **Render** as a Python web service.

- `.python-version` (repo root) — pins `3.11`. Render reads this for new
  services; services created before the file existed may need the version
  set in the Render dashboard. Without it, Render defaults to 3.14, which
  breaks `pydantic-core` (no pre-built wheel; source build fails on
  Render's read-only Cargo cache).
- `render.yaml` — defines `buildCommand: pip install -r requirements.txt`
  and `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  Production uses `uvicorn` directly, bypassing `run.py`.
- `run.py` is **dev-only**: `reload=settings.ENVIRONMENT == "development"`.
  It no longer forces `reload=True`.
- `python-dotenv==1.1.0` is an explicit dependency (used by
  `scripts/create_super_admin.py`; was previously a transitive dep of
  `pydantic-settings`).
- `CORS_ORIGINS` must be set to the Vercel frontend URL in production.
- The frontend reads `NEXT_PUBLIC_API_BASE` (Vercel env var) pointing to
  this backend's Render URL.
