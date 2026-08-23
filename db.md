# Database — MongoDB Schema Reference

> **LEGACY — migration window only.** The runtime no longer uses MongoDB; the
> active persistence layer is PostgreSQL (schema owned by Alembic). This page
> documents the legacy Mongo collections that
> `scripts/migrate_mongo_to_postgres.py` reads as its source. For the current
> schema see `MIGRATION.md` §1 and `alembic/versions/`.

The backend uses MongoDB via the async Motor driver. It connects to the **same database as the original Express/Mongoose backend**, so all collection and field names are unchanged.

## Connection

- Configured by `MONGO_URI` in `.env` (must include the database name).
- Optional `MONGO_DB` overrides the database name when it is not part of the URI.
- The app verifies connectivity with a `ping` during startup (lifespan) and fails fast if MongoDB is unreachable.

## Collections

| Collection            | Created by   | Purpose                                          |
|-----------------------|--------------|--------------------------------------------------|
| `users`               | Mongoose     | Leader accounts                                  |
| `admins`              | Mongoose     | Admin accounts (Super Admin / Moderator)         |
| `colleges`            | Mongoose     | College master list + registered status          |
| `events`              | Mongoose     | Legacy/unused (kept untouched)                   |
| `eventregistrations`  | Mongoose     | One document per registered student              |

Collection names are declared once in `app/db/mongo.py`:

```python
USERS = "users"
ADMINS = "admins"
COLLEGES = "colleges"
EVENTS = "events"
EVENT_REGISTRATIONS = "eventregistrations"
```

---

## `users` — Leaders

```json
{
  "_id": "ObjectId(...)",
  "userid": "LD1735000000000123",
  "name": "Arjun Kumar",
  "email": "arjun@example.com",
  "mobilenumber": "9876543210",
  "department": "cs",
  "college": "Anna University",
  "shift": "1",
  "password": "$2b$10$...bcrypt hash...",
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z"
}
```

| Field          | Type   | Constraints                                      |
|----------------|--------|--------------------------------------------------|
| `userid`       | string | **Unique**; auto-generated `LD<timestamp><random>` |
| `name`         | string | Required, 2–100 chars                            |
| `email`        | string | **Unique**; stored lowercased                    |
| `mobilenumber` | string | Stored as 10 digits, starts with 6–9             |
| `department`   | string | Enum: `cs`, `it`, `ai`, `ds`, `ca`               |
| `college`      | string | Free text matching a `colleges.name` ideally     |
| `shift`        | string | Enum: `1`, `2`                                   |
| `password`     | string | bcrypt hash (bcryptjs-compatible format)         |
| `createdAt` / `updatedAt` | date | auto timestamps                        |

Uniqueness rules enforced by the API:
- email unique
- mobilenumber unique
- one leader per `college + department + shift`

---

## `admins` — Admin Accounts

```json
{
  "_id": "ObjectId(...)",
  "adminId": "SA1",
  "name": "Root",
  "role": 1,
  "password": "$2b$10$...bcrypt hash...",
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z"
}
```

| Field    | Type   | Constraints                              |
|----------|--------|------------------------------------------|
| `adminId`| string | **Unique** (login identifier)            |
| `name`   | string | Required                                 |
| `role`   | number | `1` = Super Admin, `2` = Moderator       |
| `password` | string | bcrypt hash                           |

> First Super Admin: since `/admin/adminreg` requires a Super Admin token, seed the first admin directly:
> ```bash
> mongosh --uri <MONGO_URI>
> db.admins.insertOne({ adminId: "SA1", name: "Root", role: 1, password: "<bcrypt hash>" })
> ```
> Generate the hash with the project's helper:
> ```bash
> .venv\Scripts\python -c "from app.auth.security import hash_password; print(hash_password('YourPassword'))"
> ```
> Or run `scripts\create_super_admin.py SA1 Root "YourPassword"` which does both steps.

---

## `colleges` — College Master List

```json
{
  "_id": "ObjectId(...)",
  "collegeId": "C001",
  "name": "Anna University",
  "state": "TN",
  "district": "Chennai",
  "registeredStatus": false,
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z"
}
```

| Field              | Type    | Constraints                          |
|--------------------|---------|--------------------------------------|
| `collegeId`        | string  | **Unique**                           |
| `name`             | string  | Required; sorted for `/getcollege`   |
| `state`            | string  | Required                             |
| `district`         | string  | Required                             |
| `registeredStatus` | boolean | Default `false`; set `true` once a leader registers from this college |

Notes:
- `registeredStatus` is updated by `/regleader` when the registering college matches an existing `colleges.name`.
- `/addcollege` inserts with `ordered: false`, so duplicate `collegeId` values are skipped without aborting the rest.

---

## `eventregistrations` — Student Registrations (core collection)

```json
{
  "_id": "ObjectId(...)",
  "leaderId": "LD1735000000000123",
  "name": "Student One",
  "registerNumber": "RA2111003010101",
  "mobile": "9123456789",
  "college": "Anna University",
  "department": "cs",
  "degree": "ug",
  "foodPreference": "vegetarian",
  "event1": "Fixathon",
  "slot1": "1",
  "event2": null,
  "slot2": null,
  "createdAt": "2026-01-01T00:00:00.000Z",
  "updatedAt": "2026-01-01T00:00:00.000Z"
}
```

| Field             | Type    | Constraints                                         |
|-------------------|---------|-----------------------------------------------------|
| `leaderId`        | string  | The leader who registered the student               |
| `name`            | string  | Required                                            |
| `registerNumber`  | string  | Stored **uppercased**; unique per leader            |
| `mobile`          | string  | 10 digits, starts with 6–9                          |
| `college`         | string  | Copied from the leader at registration time         |
| `department`      | string  | Enum: `cs`, `it`, `ai`, `ds`, `ca` (from leader)    |
| `degree`          | string  | Enum: `ug`, `pg` (per participant)                  |
| `foodPreference`  | string  | Enum: `vegetarian`, `non-vegetarian`; captured once |
| `event1`          | string  | First (always present) event                        |
| `slot1`           | string  | Enum: `1`, `2`, `BOTH`                              |
| `event2`          | string  | `null` until added to a second event                |
| `slot2`           | string  | Enum: `1`, `2`, `BOTH`; `null` when `event2` is null|

### Indexes

| Index                        | Type     | Purpose                                             |
|------------------------------|----------|-----------------------------------------------------|
| `{ leaderId: 1, registerNumber: 1 }` | **unique** | One document per student per leader |
| `{ leaderId: 1, event1: 1 }` | regular  | "One team per event" lookups                        |
| `{ leaderId: 1, event2: 1 }` | regular  | Same for the second event                           |

> The unique index backs the "one doc per student per leader" rule. The unique compound index is normally created by Mongoose on app boot; if you are starting from a fresh DB, ensure it exists:
> ```bash
> mongosh --uri <MONGO_URI>
> db.eventregistrations.createIndex({ leaderId: 1, registerNumber: 1 }, { unique: true })
> db.eventregistrations.createIndex({ leaderId: 1, event1: 1 })
> db.eventregistrations.createIndex({ leaderId: 1, event2: 1 })
> ```

### Business rules stored in the data model

- **Max 15 students per leader** — enforced by counting `eventregistrations` for a `leaderId`.
- **One team per event per leader** — a leader cannot register the same event twice (checked against `event1`/`event2`).
- **Bid Mayhem occupies both slots** — a student with `event1 = "Bid Mayhem"` (or `event2`) cannot join other events; a student with any existing event cannot join Bid Mayhem.
- **Max 2 events per student** — `event2` fills the second slot; a third event is rejected.
- **No same-slot clash** — `slot1` vs. incoming slot must differ.
- **`foodPreference` captured once** — set when the document is created and never overwritten when the student is later added to a second event.

---

## `events` — Legacy Collection

```json
{
  "_id": "ObjectId(...)",
  "leaderId": "...",
  "name": "...",
  "registerNumber": "...",
  "department": "cs",
  "college": "...",
  "degree": "ug",
  "event1": "...",
  "event2": "..."
}
```

Not used by the new backend. Left untouched for safety — all active logic uses `eventregistrations`. Safe to ignore (or drop) once the frontend no longer references it.

---

## Shared Enums (used across collections)

| Concept         | Allowed values                                   |
|-----------------|--------------------------------------------------|
| Department      | `cs`, `it`, `ai`, `ds`, `ca`                     |
| Degree          | `ug`, `pg`                                       |
| Shift (leaders) | `1`, `2`                                         |
| Slot            | `1`, `2`, `BOTH`                                 |
| Food preference | `vegetarian`, `non-vegetarian`                   |
| Admin role      | `1` (Super Admin), `2` (Moderator)               |

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

## Query Patterns (how the app reads the data)

| Need                                  | Query                                        |
|---------------------------------------|----------------------------------------------|
| Leader by email (login)               | `users.find({ email })`                       |
| Leader by id                          | `users.find({ userid })`                      |
| Student docs for a leader             | `eventregistrations.find({ leaderId })`       |
| Team already in an event              | `eventregistrations.find({ leaderId, $or: [{ event1 }, { event2 }] })` |
| Existing students by reg numbers      | `eventregistrations.find({ leaderId, registerNumber: { $in: [...] } })` |
| Registrations for college + dept      | `eventregistrations.find({ college, department })` |
| Registrations for one event           | `eventregistrations.find({ $or: [{ event1: e }, { event2: e }] })` |
| Dashboard stats (aggregation)         | see `app/services/stats.py`                   |

## ObjectId Serialization

Raw driver results include `ObjectId` and `datetime` values. `app/utils/serializers.py` converts them to JSON-safe values (`ObjectId → str`, `datetime → ISO string`) before responses are sent, so the frontend always receives plain JSON.
