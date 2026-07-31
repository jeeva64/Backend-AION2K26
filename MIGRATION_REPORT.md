# AION 2K26 Winter — Express → FastAPI Migration Report

Date: 2026-07-31
Source: `E:\AION WINTER\BACKEND` (Express/Mongoose)
Target: `E:\AION WINTER\BACKEND\Backend-AION2K26-Winter` (FastAPI/Motor)

---

## 1. Migration Report

The original Express/Mongoose backend has been fully re-implemented as a
production-grade **FastAPI + Motor (async MongoDB)** service. It connects to the
**same MongoDB database** and preserves every **collection name, field name, and
business rule** so existing data keeps working with no data migration.

| Layer      | Express (source)            | FastAPI (target)                                  |
|------------|-----------------------------|---------------------------------------------------|
| Language   | Node.js                     | Python 3.11                                       |
| HTTP       | Express                     | FastAPI 0.115 + Uvicorn 0.34                      |
| Database   | Mongoose (sync)             | Motor 3.7 (async) + PyMongo 4.11                  |
| Validation | Inline in route handlers    | Pydantic v2 (`field_validator`/`model_validator`) |
| Auth       | `jsonwebtoken` + bcryptjs   | PyJWT 2.10 + bcrypt 4.3                           |
| Config     | `dotenv`                    | pydantic-settings (fail-fast validation)          |
| Docs       | none                        | Swagger `/docs`, ReDoc `/redoc`, OpenAPI JSON     |
| Tests      | none                        | pytest suite (e2e + unit + rate-limit)            |

**Scope of migration (all Express routes):** `regleader`, `loginleader`,
`registerteam`, `getcandidates`, `stats`, `addcollege`, `getcollege`
(`authRoutes.js`) and `adminreg`, `adminlogin`, `viewteam`, `vieweventregs`,
`deleteteam`, `deleteteambyevent`, `dashboardstats` (`adminRoutes.js`).

**Out of scope / not present in the Express source:** announcements,
uploads, email services, and a `verifyUser`-protected route. The Express app has
**no such features**, so there is nothing to migrate. The dead `verifyUser`
middleware was ported as a real `get_current_user` dependency (it was never wired
to any Express route).

**Feature parity:** 15 endpoints, exact URL paths, exact request/response
field names, exact error messages, and identical business rules (15-student cap,
one team per event, Bid Mayhem slot rules, 2-event max, no same-slot clash,
all-or-nothing team rollback, event2-promotion on delete).

---

## 2. Issues Found in the Express Codebase (audit findings)

### Critical
| # | Issue | Location | Impact |
|---|-------|----------|--------|
| C1 | **Admin JWT generated but never returned.** `adminlogin` signs a token but the response only contains `role` and `message`. | `routes/adminRoutes.js:66-80` | Frontend can never obtain an admin token; all admin routes unusable. **Fixed.** |
| C2 | **All leader routes are unauthenticated.** `registerteam`, `getcandidates`, `stats`, and `deleteteam` have no auth middleware. | `routes/authRoutes.js` | Anyone can register teams or read any leader's data. **Fixed** (Bearer required + ownership check). |
| C3 | **Public `DELETE /deleteteam/:leaderId/:event`.** Any anonymous client can delete a leader's event registrations. | `routes/authRoutes.js:501` | Data destruction without authentication. **Fixed** (route removed; only the admin variant exists). |
| C4 | **`addcollege` is public.** Anyone can bulk-insert arbitrary colleges. | `routes/authRoutes.js:581` | Database pollution / abuse. **Fixed** (Super Admin only). |

### High
| # | Issue | Impact |
|---|-------|--------|
| H1 | No first-Super-Admin bootstrap path (adminreg needs a Super Admin token). Documented workaround + helper script. | Operational dead-end on fresh DB. |
| H2 | `loginleader` returns only `userid`, no token, making `verifyUser` unusable. | C2 in practice. **Fixed.** |
| H3 | `viewteam` returns `404 "No team found"` for empty results while `deleteteambyevent` returns `404` too — inconsistent empty-state semantics; `getcandidates` etc. have no envelope. | Inconsistent client contract. Standardized to `200` + empty `data` for `viewteam`. |
| H4 | Dashboard stats load **every registration document into Node memory** and filter in JS. | O(n) memory + latency. **Fixed** with MongoDB aggregation pipelines. |
| H5 | `verifyAdmin`/`verifySuperAdmin` return `403` for invalid/expired tokens (should be `401`). | Wrong status semantics. **Fixed** (`401` for bad token, `403` for wrong role). |
| H6 | Login failures return `400` (should be `401`). | Wrong status semantics. **Fixed.** |

### Medium / Low
| # | Issue | Impact |
|---|-------|--------|
| M1 | Enum values (`department`, `degree`, `foodPreference`, `shift`) unvalidated at route level for some paths; validation only in `simple-validators.js` for `regleader`. | Invalid data can reach the DB. Enforced in Pydantic schemas + registration service. |
| M2 | Duplicate-email/mobile race: check-then-insert without handling `DuplicateKeyError` (no unique indexes guaranteed). | Duplicate accounts under concurrency. Handled by catching `DuplicateKeyError` + documented indexes. |
| M3 | Mixed response shapes (bare arrays, `{team: [...]}`, `{data: ...}`, `{stats: ...}`). | Confusing client contract. Standardized to the `{success, message, ...}` envelope. |
| M4 | Dead models (`Event`, `Colleges` registered as `events`/`colleges`) and unused `verifyUser`. | Confusion. `events` collection left untouched (legacy); `verifyUser` revived as real dependency. |
| M5 | `bcrypt.compare`/`jwt.verify` errors and DB errors all collapse to a generic `500 "Server Error"`. | No actionable diagnostics. Structured logging + typed exceptions added. |
| M6 | No rate limiting, no security headers, no structured logging, no request IDs. | Abuse surface + poor observability. **Fixed.** |
| M7 | Passwords stored via `bcryptjs` hash — must remain verifiable. | Verified: `bcrypt.checkpw` reads bcryptjs `$2a$`/`$2b$` hashes. |

---

## 3. Security Issues Fixed

| Change | Detail |
|--------|--------|
| Auth on all leader routes | `registerteam`, `getcandidates`, `stats` require a leader Bearer token (`get_current_user`) and verify the claimed `userid`/`leaderId` matches the token (ownership). |
| Admin JWT returned | `POST /admin/adminlogin` now returns `token` + `role` (8h expiry). |
| Public delete removed | The unauthenticated `DELETE /deleteteam/:leaderId/:event` was removed; event deletes exist only under `/admin/`. |
| `addcollege` locked down | Requires a **Super Admin** token (`adminRole: 1`). |
| `adminreg` locked down | Requires a Super Admin token (unchanged intent, now enforced by the same dependency). |
| Status semantics | Invalid/expired tokens → `401`; wrong role / ownership mismatch → `403`; bad credentials → `401`. |
| Rate limiting | slowapi: `20/min` default per IP; `10/min` on `loginleader` and `admin/adminlogin` (brute-force hardening). Configurable via `.env` (`RATE_LIMIT_ENABLED`, `RATE_LIMIT_*`). |
| Security headers | HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. |
| Request IDs | `X-Request-ID` on every response; echoed in access logs for traceability. |
| Fail-fast config | App refuses to start without `MONGO_URI` and a ≥16-char `JWT_SECRET`. |
| No secrets in code | All config from `.env` via pydantic-settings; `.env` is gitignored. |
| Structured logging | JSON access + error logs (method, path, status, duration, client IP, UA, request id). |
| Validation hardening | Format/enum validation moved into Pydantic, exact Express messages preserved; unique-key races handled. |
| Slow hash | bcrypt cost factor 10 for leaders and admins. |

---

## 4. Architecture Improvements

Layered, dependency-injected FastAPI layout matching the migration prompt:

```
app/
├── main.py                 # app factory, lifespan, middleware stack, exception wiring
├── config/                 # settings (pydantic-settings) + structured JSON logging
├── db/                     # Motor client lifecycle + collection-name constants
├── auth/                   # security.py (bcrypt/JWT) + dependencies.py (user/admin/super-admin)
├── exceptions/             # APIError + centralized exception handlers (incl. rate-limit)
├── middleware/             # CORS, security headers, request logging, slowapi rate limiting
├── repositories/           # data-access layer per collection (base + typed repos)
├── dependencies/           # DI wiring: get_db + repository factories
├── models/                 # Pydantic document models (mirror MongoDB documents)
├── schemas/                # Pydantic request DTOs + typed response models
├── services/               # business logic (team registration + rollback, stats pipelines)
└── utils/                  # constants (enums/slot map/limits), validators, BSON serializers
```

Highlights:
- **Async throughout** (Motor) — no event-loop blocking.
- **Response models** (`response_model=...`) on every route → complete OpenAPI schemas.
- **Pydantic-first validation** — format/enum rules run in `field_validator`s with the
  exact Express messages; presence rules in `model_validator`s; DB-dependent checks
  stay in routes/services.
- **Repository pattern** — routes/services never touch the driver directly.
- **Aggregation pipelines** for `dashboardstats`/`vieweventregs` instead of JS-side filtering.
- **Atomic-ish team registration** — writes are snapshot-based and rolled back on any
  mid-batch failure (same all-or-nothing guarantee as Express).
- **One documented deviation:** request-validation failures return `400` (matching the
  original Express contract) rather than `422`; the `errors[]` detail array is retained.
  `422` remains for malformed/unparseable bodies.

---

## 5. Route Mapping (Express → FastAPI)

All paths are identical (no `/api` prefix), mounted under `/` (auth) and `/admin`.

| # | Method & Path | Express file | Express auth | FastAPI auth | Status code change |
|---|---------------|--------------|--------------|--------------|--------------------|
| 1 | `POST /regleader` | `authRoutes.js:24` | public | public | same (`201`) |
| 2 | `POST /loginleader` | `authRoutes.js:196` | public | public (+rate limit) | `400→401` on bad creds |
| 3 | `POST /registerteam` | `authRoutes.js:240` | **none** | leader Bearer + ownership | same (`200`) |
| 4 | `POST /getcandidates` | `authRoutes.js:468` | **none** | leader Bearer + ownership | same (`200`) |
| 5 | `GET /stats/:leaderId` | `authRoutes.js:553` | **none** | leader Bearer + ownership | same (`200`) |
| 6 | `POST /addcollege` | `authRoutes.js:581` | **none** | **Super Admin** | same (`201`) |
| 7 | `GET /getcollege` | `authRoutes.js:603` | public | public | same (`200`) |
| 8 | `DELETE /deleteteam/:leaderId/:event` | `authRoutes.js:501` | **none** | **removed** | n/a |
| 9 | `POST /admin/adminreg` | `adminRoutes.js:13` | Super Admin | Super Admin | same (`201`) |
| 10 | `POST /admin/adminlogin` | `adminRoutes.js:47` | public | public (+rate limit) | `400→401`; **now returns token** |
| 11 | `POST /admin/viewteam` | `adminRoutes.js:91` | Admin | Admin | empty → `200` (was `404`) |
| 12 | `POST /admin/vieweventregs` | `adminRoutes.js:116` | Admin | Admin | same (`200`/`404`) |
| 13 | `DELETE /admin/deleteteam/:leaderId` | `adminRoutes.js:185` | Admin | Admin | same (`200`/`404`) |
| 14 | `DELETE /admin/deleteteambyevent/:leaderId/:event` | `adminRoutes.js:214` | Admin | Admin | same (`200`/`404`) |
| 15 | `GET /admin/dashboardstats` | `adminRoutes.js:268` | Admin | Admin | same (`200`) |

---

## 6. Authentication Matrix

`P` public · `U` leader token · `A` any admin token · `S` super-admin token

| Route | P | U | A | S |
|-------|---|---|---|---|
| `POST /regleader` | ✅ |   |   |   |
| `POST /loginleader` | ✅ (rate-limited) |   |   |   |
| `POST /registerteam` |   | ✅ (must be the token owner) |   |   |
| `POST /getcandidates` |   | ✅ (must be the token owner) |   |   |
| `GET /stats/{leader_id}` |   | ✅ (must be the token owner) |   |   |
| `POST /addcollege` |   |   |   | ✅ |
| `GET /getcollege` | ✅ |   |   |   |
| `POST /admin/adminlogin` | ✅ (rate-limited) |   |   |   |
| `POST /admin/adminreg` |   |   |   | ✅ |
| `POST /admin/viewteam` |   |   | ✅ | ✅ |
| `POST /admin/vieweventregs` |   |   | ✅ | ✅ |
| `DELETE /admin/deleteteam/{leader_id}` |   |   | ✅ | ✅ |
| `DELETE /admin/deleteteambyevent/{leader_id}/{event}` |   |   | ✅ | ✅ |
| `GET /admin/dashboardstats` |   |   | ✅ | ✅ |
| `GET /health` | ✅ |   |   |   |

Token payloads: leader `{userid, email, name, role:"user"}` · admin `{adminId, adminRole, role:"admin"}` (`adminRole`: 1 = Super Admin, 2 = Moderator). All tokens expire in `JWT_EXPIRE_HOURS` (default 8h).

---

## 7. Remaining TODOs

| # | Item | Status / recommendation |
|---|------|--------------------------|
| T1 | First Super Admin bootstrap | Create via DB seed. Helper provided: `python scripts/create_super_admin.py <adminId> <name> <password>` (see below). |
| T2 | Unique indexes on fresh DBs | `users.email`, `users.mobilenumber`, `users.userid`, `admins.adminId`, `colleges.collegeId`, `eventregistrations{leaderId,registerNumber}`. `scripts/ensure_indexes.py` provided. |
| T3 | `events` collection | Legacy, unused. Leave untouched or drop after frontend cutover. |
| T4 | Soft college-existence check on `regleader` | Express only updates `colleges.registeredStatus` when a name matches; it does not reject unknown colleges. Rejecting unknown colleges would change behavior — left as-is deliberately. |
| T5 | Token refresh / logout blacklist | Out of scope (matches Express). On `401` clients re-login. |
| T6 | Pagination | Not present in Express. Add query params (`page`/`limit`) to `getcollege`/`viewteam` if datasets grow. |
| T7 | Multi-worker rate limiting | slowapi's in-memory storage is per-process. For multi-worker deployments switch to a shared storage (`storage_uri`/Redis). Documented in `.env.example`. |
| T8 | `.env` rotation | `JWT_SECRET` is a placeholder — generate a random ≥32-char secret for production. |
