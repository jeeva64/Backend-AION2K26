# MongoDB → PostgreSQL Migration Guide

This document describes the AION 2K26 2.0 database migration from MongoDB to
PostgreSQL. The FastAPI service layer remains the API boundary; the Next.js
frontend talks to FastAPI only — **no direct frontend access to PostgreSQL**.

## 1. ER / schema overview

Six tables in the `public` schema:

```
admins                 users                  colleges
──────                 ────                   ────────
id  PK (bigint)        id  PK (bigint)        id  PK (bigint)
admin_id  UQ NN        user_id  UQ NN         college_id  UQ NN
name  NN               name  NN               name  NN
password_hash  NN      email  UQ NN           state  NN
role  NN (1|2)         mobile_number  UQ NN  district  NN
created_at            college_name_text NN    registered_status DEFAULT false
updated_at            college_id?  FK→colleges.id  created_at
                      department  NN (CHECK)  updated_at
                      shift  NN (CHECK)
                      password_hash  NN
                      created_at / updated_at

events                 event_slots
──────                 ───────────
id  PK                 id  PK
name  UQ NN            slot_label  UQ NN  -- '1','2','BOTH' (CHECK)
display_name  NN       description?
slot_id  NN FK→event_slots.id   created_at
created_at / updated_at          

event_registrations (core)
────────────────────
id  PK
leader_id  NN FK→users.user_id (CASCADE)
name  NN
register_number  NN
mobile  NN
college_name_text  NN              -- snapshot (current Mongo behavior)
college_id?  FK→colleges.id (SET NULL)
department  NN (CHECK cs|it|ai|ds|ca)
degree  NN (CHECK ug|pg)
food_preference  NN (CHECK vegetarian|non-vegetarian)
event1_id  NN FK→events.id
slot1_id  NN FK→event_slots.id
event2_id?  FK→events.id
slot2_id?  FK→event_slots.id
created_at / updated_at

UNIQUE (leader_id, register_number)
indexes: (leader_id,event1_id), (leader_id,event2_id), 
         (college_name_text,department), (event1_id), (event2_id)

CHECK: event2/slot2 paired | distinct events | no same-slot clash
CHECK: status IN (PAYMENT_PENDING|VERIFICATION_PENDING|CONFIRMED|REJECTED)
TRIGGER trg_bid_mayhem: if EITHER column occupies slot 'BOTH' (Bid Mayhem),
        the other column must be NULL (bidirectional since revision 0003)

payments (one row per leader)
─────────────────────────────
id  PK
leader_id  NN UQ FK→users.user_id (CASCADE)
expected_amount_paises  NN CHECK(>=0)     -- integer paise, never floats
submitted_amount_paises? CHECK(>=0)
currency  NN DEFAULT 'INR' CHECK(='INR')
utr?                                      -- partial UNIQUE (non-null rows)
payment_status  NN DEFAULT 'PENDING'
        CHECK(PENDING|VERIFICATION_PENDING|SUCCESS|REJECTED)
proof_object_key / proof_original_filename / proof_mime_type / proof_file_size?
submitted_at? / verified_at?
verified_by?  FK→admins.admin_id (SET NULL)
rejection_reason?
created_at / updated_at
indexes: (payment_status), (submitted_at), UQ(utr) WHERE utr IS NOT NULL

payment_audit (append-only)
───────────────────────────
id  PK
payment_id  NN FK→payments.id (CASCADE)
admin_id?  action  NN CHECK(CREATED|PROOF_SUBMITTED|VERIFIED|REJECTED|REOPENED)
old_status? / new_status? / reason? / details JSONB?
created_at
index: (payment_id, created_at)
```

## 2. Deviations from the original MongoDB model

1. **`events` + `event_slots` reference tables** — Mongo had none (events
   lived in `EVENT_SLOT_MAP`). Enables referential integrity and a clean
   extension point for per-event metadata / future RAG event docs.
2. **`event1_id`/`event2_id` FKs** replace free-text `event1`/`event2`.
   The API still receives/emits the human-readable event name; the SQLA
   repo resolves name ⇄ id.
3. **Optional `college_id` + retained `college_name_text`** — safe-by-default.
   The Mongo `college` field was free text entered at registration time, not
   a true FK; the new schema preserves that snapshot while leaving room for
   incremental referential integrity as data is cleaned.
4. **`leader_id` FK → `users.user_id`** (the `LD…` business key, not `users.id`)
   — matches JWT payload + Mongo reality.
5. **Real transactions** for `register_team` — replaces the Mongo-era manual
   compensation/rollback block.
6. **`password_hash` renamed** from `password` — security clarity. bcrypt
   hashes migrate verbatim (no rehashing needed).
7. **`created_at`/`updated_at`** added on every table — pure metadata, not
   surfaced in any current response schema.
8. **Snake_case columns** with **Pydantic camelCase aliases** on top — DB/API
   naming decoupling (the brief required this).
9. **`trg_bid_mayhem` PL/pgSQL trigger** enforces Bid Mayhem `BOTH`-slot
   exclusivity at the DB level (in addition to the service-level check).
   Bidirectional since revision `0003_bid_mayhem_bidirectional`: a row is
   rejected when either event column carries a `BOTH`-slot event while the
   other column is populated (previously only the `event1` direction was
   covered at the DB level).
10. **Registration payment workflow (revision `0004_registration_payments`)**
    — adds `event_registrations.status` (existing rows backfilled
    `'CONFIRMED'`, then NOT NULL; no server default so app code must always be
    explicit), plus `payments` (one row per leader, integer-paise amounts,
    partial-UNIQUE UTR) and append-only `payment_audit`. Additive and
    non-destructive; downgrade drops only the new objects.

## 3. Required environment variables

```bash
# Primary PostgreSQL connection (async SQLAlchemy):
DATABASE_URL=postgresql+asyncpg://aion:aion@localhost:5432/aion2026
SQLA_ECHO=false                                   # optional, dev SQL echo

# Legacy MongoDB (read-only — used only by the data migration script):
MONGO_URI=mongodb://localhost:27017/aion2026
MONGO_DB=                                           # optional DB override
MONGO_RETAIN=false                                  # set true to keep Mongo lifespan active

# Auth (unchanged):
JWT_SECRET=<16+ chars>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# App (unchanged):
CORS_ORIGINS=*
PORT=5000
ENVIRONMENT=development
LOG_LEVEL=INFO
RATE_LIMIT_ENABLED=false
RATE_LIMIT_DEFAULT=20/minute
RATE_LIMIT_LOGIN=10/minute
```

`.env.example` carries the same values. `.env` is gitignored.

## 4. Migration instructions (first-time setup)

```bash
# 0. install new deps
.venv\Scripts\python -m pip install -r requirements.txt

# 1. create a role + database in PostgreSQL (run as superuser once)
psql -U postgres -c "CREATE ROLE aion WITH LOGIN PASSWORD 'aion' CREATEDB;"
psql -U postgres -c "CREATE DATABASE aion2026 OWNER aion;"
psql -U postgres -c "GRANT ALL ON SCHEMA public TO aion;"

# 2. apply the schema
.venv\Scripts\python -m alembic upgrade head

# 3. seed the bootstrap Super Admin (chicken-and-egg — the API requires
#    a Super Admin token to create other admins)
.venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"

# 4. (optional) re-seed events/slots reference data after a schema bump
.venv\Scripts\python scripts\seed_reference_data.py

# 5. (one-time) copy data from the legacy MongoDB into PostgreSQL
.venv\Scripts\python scripts\migrate_mongo_to_postgres.py
#    add --force to TRUNCATE the target tables first
#    add --dry-run to validate without committing (rolls back)
```

## 5. Rollback / recovery strategy

- The MongoDB source is **never modified** by the migration script — it only
  reads. Roll back to Mongo at any time by reverting the FastAPI layer
  (`app/main.py` lifespan + `app/dependencies/db.py`) and pointing the routers
  at the Mongo repos again (still present under `app/repositories/`).
- PostgreSQL rollback:
  ```bash
  .venv\Scripts\python -m alembic downgrade base     # drops all tables
  ```
  Re-run `alembic upgrade head` to rebuild.
- The migration script writes a detailed per-table JSON report at
  `scripts/migration_report_<timestamp>.json` (accepted / rejected / skipped
  counts per table plus per-row reason codes). Keep this file as an audit
  trail of what landed and what didn't.

## 6. API compatibility summary

**Zero contract changes** — the Next.js frontend requires no modifications:

- Same camelCase request/response keys (`leaderId`, `registerNumber`,
  `foodPreference`, `event1`/`slot1`/`event2`/`slot2`, `totalStudents`,
  `studentsRemaining`, `registeredEvents`, `deletedCount`, …).
- Same `{success, message, ...}` envelope on every response.
- Same status codes (200/201/400/401/403/404/409/429/500). Validation
  failures still return **400**, not FastAPI's default 422 — preserved by
  `app/exceptions/handlers.py`.
- Same JWT payload shapes — Leader `{userid, email, name, role:"user"}`;
  Admin `{adminId, adminRole, role:"admin"}`.
- All 15 endpoints unchanged; same rate limits; same security headers;
  same `X-Request-ID`.

## 7. Future RAG integration points

The schema is intentionally separated from any future retrieval layer:

```
Next.js  →  FastAPI  →  RAG Service  →  PostgreSQL + pgvector
                ↓
        transactional data (public schema)
```

- The `events` table is the natural anchor for future per-event knowledge —
  description, rules, FAQ. Add metadata columns there later without touching
  `event_registrations`.
- The future RAG layer lives in its own schema (suggested: `rag`) with
  tables like `rag.event_documents(event_id FK, content, embedding vector(N))`
  and `rag.chunks(...)`. **`pgvector` is NOT enabled in the initial migration**;
  it will be added by a later `alembic revision` that runs
  `CREATE EXTENSION pgvector` and creates the embedding tables.
- A future `app/services/rag/` module would expose the AION chatbot endpoints
  while keeping transactional reads/writes on the existing repos untouched.
- No transactional schema exists solely to serve RAG — the `messages` /
  `sessions` / `embeddings` tables will live in the `rag` schema and reference
  `events` via FK, leaving the `public` schema's transactional workload
  unaffected.

## 8. Tests

- **Existing suite preserved**: `e2e_api_test.py` (test_full_flow, auth matrix,
  security headers), `rate_limit_test.py`, `unit_security_test.py`,
  `unit_validators_test.py` — all green. They exercise the new Postgres backend
  with no API-contract changes.
- **New `tests/db_constraints_test.py`** — verifies CHECK/FK/UNIQUE constraints
  + the Bid Mayhem trigger reject invalid rows at the DB level.
- **New `tests/registration_race_test.py`** — two concurrent
  `/registerteam` calls racing the same `(leader_id, register_number)`:
  exactly one wins, the other gets a 4xx (never a 500).
- **New `tests/migration_test.py`** — seeds a scratch MongoDB with good+bad
  records, runs the migration script against a scratch Postgres DB, asserts
  the report counters. Auto-skips when MongoDB is unreachable so the rest of
  the suite runs in MongoDB-less environments.
- pytest config: `pytest.ini` sets `asyncio_mode = auto`. Tests target the
  dedicated `aion_pytest_test` database (created alongside `aion2026`).
  `conftest.py` runs `alembic upgrade head` per session and seeds `SA1` /
  `Admin@12345`.

## 9. Where the dormant Mongo code lives

Kept for the migration window (per Phase 1 decision), not deleted:

- `app/db/mongo.py` — Motor client + `connect_to_db` / `close_db` / `get_db`.
- `app/repositories/` — original Motor collection repos (everything repos in
  the new path is under `app/repositories_sqla/`).
- `app/models/` — original Pydantic doc models (reference for migration).
- `scripts/create_super_admin_mongo.py` — legacy bootstrap helper.
- `app/services/registration.py`, `app/services/stats.py` — original Mongo
  service implementations (kept for diff/audit).

`app/main.py` only activates the Mongo lifespan when `MONGO_RETAIN=true`
(default `false`). Once the migration is verified, the Mongo path can be
deleted in a follow-up cleanup PR.
