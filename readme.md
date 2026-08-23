# AION 2K26 : Backend

FastAPI + SQLAlchemy 2.0 (async PostgreSQL) backend for the AION 2K26 Winter event.

This is a full migration of the original Express/Mongoose backend. The runtime now
persists to **PostgreSQL** via SQLAlchemy 2.0 + asyncpg, with the schema owned by
**Alembic**. The legacy MongoDB code is kept dormant for the migration window — see
`MIGRATION.md` for the full migration guide and rollback strategy.

## Tech Stack

- Python 3.11
- FastAPI 0.115
- SQLAlchemy 2.0 (async engine) + asyncpg — **primary persistence**
- Alembic 1.14 (schema migrations; seeds `event_slots`/`events` reference data)
- PyJWT 2.10 (JWT auth)
- bcrypt 4.3 (password hashing)
- Pydantic 2.11 + pydantic-settings 2.8
- slowapi 0.1.9 (rate limiting)
- Motor 3.7 / PyMongo 4.11 *(legacy, migration window only — used by `scripts/migrate_mongo_to_postgres.py`)*

## Folder Structure

```
Backend-AION2K26-Winter/
├── requirements.txt        # runtime deps
├── requirements-dev.txt    # + pytest, httpx, pytest-asyncio, psycopg2-binary
├── .env.example            # copy to .env and fill real values
├── .env                    # local config (gitignored)
├── run.py                  # uvicorn entry point
├── alembic.ini
├── alembic/
│   ├── env.py              # async Alembic env (DATABASE_URL from settings)
│   └── versions/
│       ├── 0001_initial_schema.py          # all tables/CHECKs/indexes/trigger + seeds
│       ├── 0002_seed_super_admin.py        # no-op placeholder (seeder is explicit)
│       └── 0003_bid_mayhem_bidirectional.py# trg_bid_mayhem: BOTH rejected in either column
├── scripts/
│   ├── create_super_admin.py           # seed the first Super Admin (Postgres)
│   ├── seed_reference_data.py          # re-seed events/slots (idempotent)
│   ├── migrate_mongo_to_postgres.py    # one-time data migration (--force/--dry-run)
│   └── create_super_admin_mongo.py     # legacy bootstrap helper (migration window)
└── app/
    ├── main.py             # app factory, middleware stack, exception wiring
    ├── config/
    │   ├── settings.py     # environment/settings (pydantic-settings)
    │   └── logging.py      # structured JSON logging
    ├── db/
    │   ├── sqlalchemy.py   # async engine + session factory (primary)
    │   └── mongo.py        # Motor client lifecycle (dormant; MONGO_RETAIN=true)
    ├── auth/
    │   ├── security.py     # bcrypt + JWT helpers
    │   └── dependencies.py # Bearer-token deps (user/admin/super-admin)
    ├── exceptions/
    │   ├── api_error.py    # APIError (status_code + message)
    │   └── handlers.py     # centralized exception handlers (400-not-422 contract)
    ├── middleware/
    │   ├── cors.py             # CORS
    │   ├── security_headers.py # HSTS/nosniff/frame/COOP headers
    │   ├── request_logging.py  # JSON access log + X-Request-ID
    │   └── rate_limit.py       # slowapi limiter + middleware
    ├── dependencies/       # DI wiring (AsyncSessionDep, repository factories)
    ├── models_sqla/        # SQLAlchemy ORM models (snake_case columns)
    ├── models/             # legacy Pydantic doc models (reference only)
    ├── schemas/            # request DTOs + typed response models (camelCase)
    ├── api/
    │   ├── auth.py         # leader-facing routes
    │   └── admin.py        # admin routes (prefix /admin)
    ├── repositories_sqla/  # async repos returning camelCase dicts (primary)
    ├── repositories/       # legacy Motor repos (dormant, migration window)
    ├── services/
    │   ├── registration_sqla.py # team registration business logic (1 transaction)
    │   ├── stats_sqla.py        # SQL GROUP BY report queries
    │   ├── registration.py      # legacy Mongo implementation (kept for audit)
    │   └── stats.py             # legacy Mongo aggregations (kept for audit)
    └── utils/
        ├── constants.py    # enums, event→slot map, limits
        ├── validators.py   # ported from simple-validators.js
        ├── serializers.py  # ObjectId/datetime → JSON-safe conversion
        └── response.py     # MongoJSONResponse
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set real values:

| Variable             | Required | Description                                                              |
|----------------------|----------|--------------------------------------------------------------------------|
| `DATABASE_URL`       | Yes      | PostgreSQL DSN, async form: `postgresql+asyncpg://user:pass@host:5432/db`|
| `SQLA_ECHO`          | No       | Echo SQL in development (`false` default)                                |
| `REGISTRATION_FEE_PER_STUDENT_PAISE` | No | Registration fee in integer paise (`20000` = Rs.200/student)    |
| `PROOF_MAX_MB`       | No       | Payment screenshot size cap in MB (default `5`)                          |
| `PROOF_STORAGE_BACKEND` | No    | `local` (dev/tests) or `b2` (Backblaze B2, production)                   |
| `PROOF_LOCAL_DIR`    | No       | Local proof dir when backend is `local` (default `payment_proofs_local`) |
| `B2_BUCKET` / `B2_REGION` / `B2_ACCESS_KEY_ID` / `B2_SECRET_ACCESS_KEY` | When `b2` | Private B2 bucket credentials (S3-compatible) |
| `UPI_VPA`            | No       | UPI ID shown to leaders; empty disables the QR/intent URI                |
| `UPI_PAYEE_NAME`     | No       | Payee name embedded in the UPI intent URI                                |
| `MONGO_URI`          | No       | Legacy source DB for the one-time migration script only                  |
| `MONGO_DB`           | No       | Optional database override if not part of `MONGO_URI`                    |
| `MONGO_RETAIN`       | No       | `true` keeps the Mongo lifespan active (default `false`)                 |
| `JWT_SECRET`         | Yes      | Secret for signing JWTs (min 16 characters)                              |
| `JWT_ALGORITHM`      | No       | Default `HS256`                                                          |
| `JWT_EXPIRE_HOURS`   | No       | Token lifetime in hours, default `8`                                     |
| `CORS_ORIGINS`       | No       | Comma-separated origins, or `*` (default)                                |
| `PORT`               | No       | Default `5000`                                                           |
| `ENVIRONMENT`        | No       | `development` / `production`                                             |
| `LOG_LEVEL`          | No       | `INFO` default; structured JSON logs                                     |
| `RATE_LIMIT_ENABLED` | No       | Enable slowapi rate limiting (`false` default)                           |
| `RATE_LIMIT_DEFAULT` | No       | Per-IP default limit, e.g. `20/minute`                                   |
| `RATE_LIMIT_LOGIN`   | No       | Tighter limit for login endpoints, e.g. `10/minute`                      |

The app fails to start if `DATABASE_URL` is missing/not a PostgreSQL DSN or a
valid `JWT_SECRET` is missing. On startup it pings Postgres (`SELECT 1`) and
aborts when unreachable.

### First-run setup

```bash
# 1. create role + database (run once as a PostgreSQL superuser)
psql -U postgres -c "CREATE ROLE aion WITH LOGIN PASSWORD 'aion' CREATEDB;"
psql -U postgres -c "CREATE DATABASE aion2026 OWNER aion;"

# 2. apply the schema (Alembic owns every table/index/CHECK/trigger)
.venv\Scripts\python -m alembic upgrade head

# 3. seed the bootstrap Super Admin (chicken-and-egg: /admin/adminreg needs
#    a Super Admin token, so the first one is created out-of-band)
.venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"

# 4. (optional) re-seed events/slots reference data after a schema bump
.venv\Scripts\python scripts\seed_reference_data.py
```

> Rate limiting uses an in-memory store — valid per single uvicorn process. For
> multi-worker deployments configure a shared store (Redis) via slowapi's
> `storage_uri`.

## Run

```bash
.venv\Scripts\python run.py
```

Or directly:

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload
```

- API: `http://localhost:5000`
- Interactive docs (Swagger): `http://localhost:5000/docs`
- ReDoc: `http://localhost:5000/redoc`
- OpenAPI JSON: `http://localhost:5000/openapi.json`
- Health check: `GET /health`

## Response Envelope

Every endpoint returns a JSON object. Success:

```json
{
  "success": true,
  "message": "Human readable message",
  "...": "additional endpoint-specific fields"
}
```

Error (every non-2xx):

```json
{
  "success": false,
  "message": "Reason for the failure"
}
```

Validation errors (`400`) additionally include an `errors` array with the failed field details:

```json
{
  "success": false,
  "message": "field: detail",
  "errors": [ "...pydantic error objects..." ]
}
```

## HTTP Status Codes

| Code | Meaning                                                         |
|------|-----------------------------------------------------------------|
| 200  | OK                                                              |
| 201  | Created (leader/admin/college)                                  |
| 400  | Validation failure (Pydantic/route rules, matching the original Express contract) |
| 401  | Missing, invalid, or expired token; bad credentials             |
| 403  | Wrong role, or leader/user ID mismatch with the token           |
| 404  | Resource not found                                              |
| 409  | Conflict (already registered, limit exceeded, slot clash)       |
| 429  | Too many requests (rate limited)                                |
| 500  | Internal server error                                           |

> All request-validation failures return `400` with the exact Express error
> message, so existing frontend logic keeps working unchanged. `422` is used
> only for bodies that are not JSON or not the expected shape.

## Authentication

- **Leader routes**: JWT returned by `POST /loginleader`.
- **Admin routes**: JWT returned by `POST /admin/adminlogin`.
- Send the token on every protected request:

```
Authorization: Bearer <token>
```

Token payloads:

| Token type | Payload                                                     |
|------------|-------------------------------------------------------------|
| Leader     | `{ userid, email, name, role: "user" }`                     |
| Admin      | `{ adminId, adminRole, role: "admin" }` (`adminRole`: 1 = Super Admin, 2 = Moderator) |

## Security

- **Rate limiting** (slowapi): `20/min` per IP by default, `10/min` on
  `/loginleader` and `/admin/adminlogin`. Enable with `RATE_LIMIT_ENABLED=true`.
- **Security headers**: HSTS, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`,
  `Cross-Origin-Opener-Policy`.
- **Request IDs**: every response carries `X-Request-ID`; the value is also in
  the access log for correlating errors.
- **Structured logging**: JSON lines to stdout (timestamp, level, logger,
  message) plus JSON access logs (method, path, status, duration, client IP, UA).
- **Env hardening**: config from `.env` only; fail-fast on missing/invalid
  `DATABASE_URL` / short `JWT_SECRET`.

## Testing

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -v
```

Requires **PostgreSQL** running at `localhost:5432` with role `aion:aion`
(CREATEDB). The suite drops and rebuilds its own `aion_pytest_test` database by
running `alembic upgrade head` per session (exercising the real migration), then
seeds one Super Admin (`SA1` / `Admin@12345`, `role: 1`). Covers all 18 routes,
the auth matrix, Bid Mayhem / slot rules (service layer + DB trigger), DB
constraints, registration races, rollback, rate limiting, and unit tests for
validators and JWT/bcrypt. `tests/migration_test.py` self-skips when the legacy
MongoDB is unreachable, so the rest of the suite runs Mongo-less.

---

## Routes — Leader / Auth

### `POST /regleader`
Register a new leader.

Request body:

```json
{
  "name": "Arjun Kumar",
  "email": "arjun@example.com",
  "mobilenumber": "9876543210",
  "department": "cs",
  "college": "Anna University",
  "shift": "1",
  "password": "Passw0rd!",
  "confirmpassword": "Passw0rd!"
}
```

Validation:
- All fields required (`400`).
- `name`: 2–100 chars, letters/spaces/dots/hyphens/apostrophes only.
- `email`: valid email format; stored lowercased; must be unique.
- `mobilenumber`: 10 digits starting with 6–9; stored stripped of non-digits; must be unique.
- `department`: one of `cs`, `it`, `ai`, `ds`, `ca`.
- `college`: 2–100 chars.
- `shift`: `1` or `2`.
- `password`: 8–128 chars, at least one uppercase, one lowercase, one digit, one special char, no spaces.
- `confirmpassword` must match `password`.
- Only **one leader per college + department + shift** (`400`).

Success `201`:

```json
{
  "success": true,
  "message": "Leader registered successfully",
  "userid": "LD1735000000000123"
}
```

Also marks the college as registered (`registeredStatus: true`) when a matching college document exists.

### `POST /loginleader`
Leader login. Public.

Request body:

```json
{ "email": "arjun@example.com", "password": "Passw0rd!" }
```

Success `200`:

```json
{
  "success": true,
  "message": "Login successful",
  "userid": "LD1735000000000123",
  "name": "Arjun Kumar",
  "token": "<jwt>"
}
```

Invalid credentials → `401`. Use the returned token for all protected leader routes.

### `POST /registerteam`
Register a whole team for one event. **Requires leader Bearer token.**

Request body:

```json
{
  "leaderId": "LD1735000000000123",
  "event": "Fixathon",
  "participants": [
    {
      "name": "Student One",
      "registerNumber": "ra2111003010101",
      "mobile": "9123456789",
      "degree": "ug",
      "foodPreference": "vegetarian"
    }
  ]
}
```

- `leaderId` must match the token's `userid`, otherwise `403`.
- `foodPreference` is **required only for brand-new students** (ignored for students already registered under this leader). `vegetarian` or `non-vegetarian`.
- `degree`: `ug` or `pg`.
- `mobile`: 10 digits starting with 6–9.
- `registerNumber` is uppercased automatically and must be unique within the team and unique per leader.

Rules enforced (`409` on violation):
- Only one team per event per leader.
- Max **15 students** total per leader.
- **Bid Mayhem** occupies both slots — a student in Bid Mayhem cannot join other events, and Bid Mayhem cannot be combined with any other event.
- Each student max **2 events**, no same-slot clash.

Success `200`:

```json
{
  "success": true,
  "message": "Team of 1 registered for Fixathon.",
  "created": 1,
  "updated": 0
}
```

Write failures mid-team are rolled back automatically (`500`).

### `POST /getcandidates`
List all registered students for a leader. **Requires leader Bearer token.**

Request body:

```json
{ "user_id": "LD1735000000000123" }
```

- `user_id` must match the token's `userid`, otherwise `403`.

Success `200`:

```json
{
  "success": true,
  "message": "Candidates fetched successfully",
  "totalStudents": 2,
  "registeredEvents": ["Fixathon"],
  "data": [ { "...one EventRegistration document per student..." } ]
}
```

### `GET /stats/{leader_id}`
Dashboard statistics for a leader. **Requires leader Bearer token.**

- `leader_id` must match the token's `userid`, otherwise `403`.

Success `200`:

```json
{
  "success": true,
  "message": "Stats fetched successfully",
  "stats": {
    "totalStudents": 2,
    "studentsRemaining": 13,
    "eventsRegistered": 1,
    "registeredEvents": ["Fixathon"]
  }
}
```

### `POST /addcollege`
Bulk-add colleges. **Requires Super Admin Bearer token** (`adminRole: 1`).

Request body (array):

```json
[
  { "collegeId": "C001", "name": "Anna University", "state": "TN", "district": "Chennai" },
  { "collegeId": "C002", "name": "SRM Institute", "state": "TN", "district": "Chengalpattu" }
]
```

- Every item must have `collegeId` and `name`.
- `registeredStatus` defaults to `false`.
- Duplicate `collegeId` values are skipped (partial inserts allowed).

Success `201`:

```json
{
  "success": true,
  "message": "Colleges added successfully",
  "count": 2
}
```

### `GET /getcollege`
List colleges (public).

Success `200`:

```json
{
  "success": true,
  "message": "Colleges fetched successfully",
  "data": [
    { "collegeId": "C001", "name": "Anna University", "district": "Chennai", "registeredStatus": false }
  ]
}
```

Sorted by `name`.

---

## Routes — Admin (prefix `/admin`)

### `POST /admin/adminreg`
Create a new admin. **Requires Super Admin Bearer token.**

Request body:

```json
{
  "adminId": "MOD1",
  "name": "Moderator",
  "role": 2,
  "password": "Admin@12345"
}
```

- `role`: **only `2` (Moderator)** may be created via this endpoint. Super
  Admins (`role: 1`) are created exclusively via the seeder script.
- `adminId` must be unique.

Success `201`: `{ "success": true, "message": "Admin registered successfully" }`

> **Bootstrap note:** the very first Super Admin cannot be created through the API (it requires a Super Admin token, and `/admin/adminreg` only creates Moderators). Seed it directly against PostgreSQL:
> ```bash
> .venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"
> ```
> The legacy Mongo variant is `scripts/create_super_admin_mongo.py` (migration window only).

### `POST /admin/adminlogin`
Admin login. Public.

Request body:

```json
{ "adminId": "SA1", "password": "Admin@12345" }
```

Success `200`:

```json
{
  "success": true,
  "message": "Super Admin logged in",
  "role": 1,
  "token": "<jwt>"
}
```

`message` is `"Super Admin logged in"` for role 1 and `"Organizer logged in"`
for role 2. Invalid credentials → `401`.

### `POST /admin/changepassword`
Change the logged-in admin's own password. **Requires admin Bearer token** (any role).

Request body:

```json
{
  "currentPassword": "Admin@12345",
  "newPassword": "NewPass@123",
  "confirmPassword": "NewPass@123"
}
```

Validation (`400` on failure):
- All three fields required.
- `newPassword`: same strength rules as leader passwords (8–128 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit, ≥1 special char, no spaces).
- `currentPassword` must match the stored password.
- `newPassword` must differ from `currentPassword`.
- `newPassword` must equal `confirmPassword`.

Success `200`: `{ "success": true, "message": "Password updated successfully" }`

Existing tokens stay valid until they expire (JWTs carry no password version).

### `PUT /admin/college/{collegeId}`
Update a college's fields. **Requires Super Admin Bearer token** (`adminRole: 1`).

Request body (any subset; at least one field):

```json
{ "name": "Anna University", "state": "TN", "district": "Chennai" }
```

- Empty/omitted body → `400 No fields to update`.
- Unknown `collegeId` → `404 College not found`.

Success `200`: `{ "success": true, "message": "College updated successfully" }`

### `GET /admin/leader-college-depts`
Distinct college → departments pairs derived from registered leaders. **Requires admin Bearer token** (any role).

Success `200`:

```json
{
  "success": true,
  "message": "College departments fetched successfully",
  "data": [
    { "college": "Anna University", "departments": ["cs", "it"] },
    { "college": "SRM Institute", "departments": ["ai"] }
  ]
}
```

Sorted by college name.

### `POST /admin/viewteam`
View registrations for a college + department. **Requires admin Bearer token.**

Request body:

```json
{ "college": "Anna University", "department": "cs" }
```

Success `200` (empty array when no team exists):

```json
{
  "success": true,
  "message": "Team fetched successfully",
  "data": [ "...EventRegistration documents..." ]
}
```

### `POST /admin/vieweventregs`
View registrations grouped by leader for one event. **Requires admin Bearer token.**

Request body:

```json
{ "eventName": "Fixathon" }
```

Success `200`:

```json
{
  "success": true,
  "message": "Registrations fetched successfully",
  "event": "Fixathon",
  "totalTeams": 3,
  "data": [
    {
      "leaderId": "LD1735000000000123",
      "college": "Anna University",
      "department": "cs",
      "members": [
        {
          "name": "Student One",
          "registerNumber": "RA2111003010101",
          "mobile": "9123456789",
          "degree": "ug",
          "foodPreference": "vegetarian",
          "event1": "Fixathon",
          "slot1": "1",
          "event2": null,
          "slot2": null
        }
      ]
    }
  ]
}
```

No registrations → `404`.

### `DELETE /admin/deleteteam/{leader_id}`
Delete every registration of a leader. **Requires admin Bearer token.**

Success `200`:

```json
{
  "success": true,
  "message": "Deleted 2 team member(s) for leader LD1735000000000123",
  "deletedCount": 2
}
```

No team → `404`.

### `DELETE /admin/deleteteambyevent/{leader_id}/{event}`
Remove a leader's team from one specific event. **Requires admin Bearer token.**

Behavior:
- Member in `event1` with a second event → the second event is promoted to `event1` (`updated`).
- Member in `event1` with no second event → document deleted (`deleted`).
- Member in `event2` → only `event2`/`slot2` cleared (`updated`).

Event names with spaces must be URL-encoded, e.g. `Bid%20Mayhem`.

Success `200`:

```json
{
  "success": true,
  "message": "Team removed from Fixathon. 1 member(s) updated, 1 member(s) deleted.",
  "updatedCount": 1,
  "deletedCount": 1
}
```

No registrations → `404`.

### `GET /admin/dashboardstats`
Overall event statistics. **Requires admin Bearer token.** Computed with set-based
SQL aggregates (GROUP BY / COUNT over both event columns).

Success `200`:

```json
{
  "success": true,
  "message": "Dashboard stats fetched successfully",
  "stats": {
    "totalMembers": 120,
    "totalTeams": 45,
    "vegCount": 70,
    "nonVegCount": 50,
    "ugCount": 90,
    "pgCount": 30,
    "eventCounts": {
      "Fixathon": 12,
      "Mute Masters": 10,
      "Treasure Titans": 9,
      "VisionX": 8,
      "QRush": 11,
      "ThinkSync": 7,
      "Bid Mayhem": 6,
      "Crazy Sell": 5
    },
    "collegeStats": [
      { "college": "Anna University", "department": "cs", "members": 10, "veg": 6, "nonVeg": 4 }
    ],
    "deptCounts": { "cs": 40, "it": 30, "ai": 25, "ds": 15, "ca": 10 }
  }
}
```

### `GET /health`
Liveness check. Public.

```json
{ "success": true, "message": "Server is running" }
```

---

## Event → Slot Map

| Event          | Slot |
|----------------|------|
| Fixathon       | 1    |
| Mute Masters   | 1    |
| Treasure Titans| 1    |
| Bid Mayhem     | BOTH |
| QRush          | 2    |
| VisionX        | 2    |
| ThinkSync      | 2    |
| Crazy Sell     | 2    |

An event not in this map is rejected with `400` on `/registerteam`.

---

## Registration Payment Workflow

Registration is **not confirmed until the payment passes manual verification**.

```
/registerteam ──► rows created with status = PAYMENT_PENDING
                  payment row created (one per leader, UNIQUE)
                  amount = ₹200 × unique students (backend-calculated)
        ↓
Leader pays via UPI (QR / intent URI from GET /payments/mine)
        ↓
POST /payments/proof  (UTR + amount + screenshot)
  payment → VERIFICATION_PENDING, registrations → VERIFICATION_PENDING
  team edits are LOCKED while under review
        ↓
Super Admin reviews at GET /admin/payments
  ├── POST .../verify  → payment SUCCESS + registrations CONFIRMED (atomic)
  └── POST .../reject {reason} → payment REJECTED + registrations back to
      PAYMENT_PENDING (leader may resubmit; Super Admin may reopen)
```

Key rules:

- **Fee** = `REGISTRATION_FEE_PER_STUDENT_PAISE` × unique student count
  (`COUNT(DISTINCT upper(register_number))`). The backend is the only source of
  truth for the count and the amount — frontend values are cosmetic.
- **Money is integer paise** everywhere (`expectedAmountPaises`,
  `submittedAmountPaises`). Never floats.
- **UTR** is required, trimmed, normalized to uppercase, validated
  (`8–22` alphanumeric) and **globally UNIQUE** across payments (partial unique
  index). Duplicate UTRs are rejected with `409`.
- **Amount mismatch never auto-fails**: submitted vs expected amounts are both
  stored and surfaced to the admin (Expected / Submitted / Difference); the
  Super Admin decides. A screenshot alone can never mark a payment successful.
- **Proofs** (JPG/PNG/WebP, ≤ `PROOF_MAX_MB`, content-sniffed via Pillow) are
  stored in a **private** B2 bucket (`PROOF_STORAGE_BACKEND=b2`) or on local
  disk for dev/tests. Admin access is authenticated-only — signed URL or an
  authorized streaming endpoint; screenshots are never public URLs.
- Every action (created / proof submitted / verified / rejected / reopened) is
  recorded in the append-only `payment_audit` table.
- Abandoned registrations stay in `PAYMENT_PENDING` forever — nothing is
  auto-deleted.

### Payment endpoints

Leader (Bearer token):

- `GET /payments/mine` — status, payable amount, UPI intent URI.
- `POST /payments/proof` — multipart: `utr`, `amountPaises`, `screenshot`.

Super Admin only (`adminRole: 1`):

- `GET /admin/payments?status=PENDING|VERIFICATION_PENDING|SUCCESS|REJECTED`
- `GET /admin/payments/{payment_id}` — detail + audit trail.
- `GET /admin/payments/{payment_id}/proof` — proof access descriptor (URL).
- `GET /admin/payments/{payment_id}/proof/content` — authorized image stream.
- `POST /admin/payments/{payment_id}/verify`
- `POST /admin/payments/{payment_id}/reject` — body `{ "reason": "..." }`.
- `POST /admin/payments/{payment_id}/reopen`

---
