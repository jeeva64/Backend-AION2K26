# AION 2K26 : Backend

FastAPI + Motor (async MongoDB) backend for the AION 2K26 Winter event.

This is a full migration of the original Express/Mongoose backend. It connects to the **same MongoDB database** and keeps the **same collection names and field names**, so existing data works without any migration.

## Tech Stack

- Python 3.11
- FastAPI 0.115
- Motor 3.7 (async MongoDB driver)
- PyMongo 4.11
- PyJWT 2.10 (JWT auth)
- bcrypt 4.3 (password hashing)
- Pydantic 2.11 + pydantic-settings 2.8
- slowapi 0.1.9 (rate limiting)

## Folder Structure

```
Backend-AION2K26-Winter/
├── requirements.txt        # runtime deps
├── requirements-dev.txt    # + pytest, httpx, pytest-asyncio
├── .env.example            # copy to .env and fill real values
├── .env                    # local config (gitignored)
├── run.py                  # uvicorn entry point
├── scripts/
│   ├── create_super_admin.py  # seed the first Super Admin (Mongo)
│   └── ensure_indexes.py      # create the unique indexes
└── app/
    ├── main.py             # app factory, middleware stack, exception wiring
    ├── config/
    │   ├── settings.py     # environment/settings (pydantic-settings)
    │   └── logging.py      # structured JSON logging
    ├── db/
    │   └── mongo.py        # Motor client lifecycle + collection names
    ├── auth/
    │   ├── security.py     # bcrypt + JWT helpers
    │   └── dependencies.py # Bearer-token deps (user/admin/super-admin)
    ├── exceptions/
    │   ├── api_error.py    # APIError (status_code + message)
    │   └── handlers.py     # centralized exception handlers
    ├── middleware/
    │   ├── cors.py             # CORS
    │   ├── security_headers.py # HSTS/nosniff/frame/COOP headers
    │   ├── request_logging.py  # JSON access log + X-Request-ID
    │   └── rate_limit.py       # slowapi limiter + middleware
    ├── repositories/       # data-access layer per collection
    │   ├── base.py
    │   ├── user_repository.py
    │   ├── admin_repository.py
    │   ├── college_repository.py
    │   └── event_registration_repository.py
    ├── dependencies/       # DI wiring (get_db, repository factories)
    ├── models/             # Pydantic document models (mirror MongoDB)
    ├── schemas/            # request DTOs + typed response models
    ├── api/
    │   ├── auth.py         # leader-facing routes
    │   └── admin.py        # admin routes (prefix /admin)
    ├── services/
    │   ├── registration.py # team registration business logic + rollback
    │   └── stats.py        # aggregation pipelines for reports
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

| Variable             | Required | Description                                              |
|----------------------|----------|----------------------------------------------------------|
| `MONGO_URI`          | Yes      | MongoDB connection string, must include database name    |
| `MONGO_DB`           | No       | Optional database override if not part of `MONGO_URI`    |
| `JWT_SECRET`         | Yes      | Secret for signing JWTs (min 16 characters)              |
| `JWT_ALGORITHM`      | No       | Default `HS256`                                          |
| `JWT_EXPIRE_HOURS`   | No       | Token lifetime in hours, default `8`                     |
| `CORS_ORIGINS`       | No       | Comma-separated origins, or `*` (default)                |
| `PORT`               | No       | Default `5000`                                           |
| `ENVIRONMENT`        | No       | `development` / `production`                             |
| `LOG_LEVEL`          | No       | `INFO` default; structured JSON logs                     |
| `RATE_LIMIT_ENABLED` | No       | Enable slowapi rate limiting (`false` default)           |
| `RATE_LIMIT_DEFAULT` | No       | Per-IP default limit, e.g. `20/minute`                   |
| `RATE_LIMIT_LOGIN`   | No       | Tighter limit for login endpoints, e.g. `10/minute`      |

The app fails to start if `MONGO_URI` or a valid `JWT_SECRET` is missing.

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
- **Env hardening**: config from `.env` only; fail-fast on missing `MONGO_URI` /
  short `JWT_SECRET`.

## Testing

```bash
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest tests -v
```

Requires MongoDB (default `mongodb://localhost:27017`). The suite drops and
reseeds its own `aion_pytest_test` database. Covers all 15 routes, the auth
matrix, Bid Mayhem / slot rules, rollback, rate limiting, and unit tests for
validators and JWT/bcrypt.

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

- `role`: `1` (Super Admin) or `2` (Moderator).
- `adminId` must be unique.

Success `201`: `{ "success": true, "message": "Admin registered successfully" }`

> **Bootstrap note:** the very first Super Admin cannot be created through the API (it requires a Super Admin token). Insert it directly into MongoDB:
> ```js
> db.admins.insertOne({ adminId: "SA1", name: "Root", role: 1, password: "<bcrypt hash>" })
> ```
> Or use the helper:
> ```bash
> .venv\Scripts\python scripts\create_super_admin.py SA1 Root "YourPassword"
> ```

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

Invalid credentials → `401`.

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
Overall event statistics. **Requires admin Bearer token.** Computed with MongoDB aggregation pipelines.

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
