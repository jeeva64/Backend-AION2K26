# Integrations Guide — Client Side

How the frontend should talk to the AION 2K26 Winter backend. Covers bearer-token flow, response handling, and per-endpoint client conditions.

## Base URL

```
http://localhost:5000
```

In production, replace with the deployed host. All requests are JSON (`Content-Type: application/json`).

## Response Envelope (read this first)

Every endpoint returns `{ "success": boolean, "message": string, ... }`.

**Always check `success` first, never rely on HTTP status alone.**

```js
const res = await fetch(url, opts);
const body = await res.json();

if (body.success === true) {
  // handle body.userid, body.token, body.data, ...
} else {
  // show body.message to the user
}
```

Error responses use these fields:

```json
{ "success": false, "message": "Reason" }
```

Validation errors (`400`) additionally include an `errors` array:

```json
{ "success": false, "message": "field: detail", "errors": [ ... ] }
```

> All validation failures return `400` (matching the original Express contract)
> with the exact Express message. `422` only appears for bodies that are not JSON
> or not the expected shape.

## HTTP Status → Client Action

| Status | Meaning                     | Client handling                                 |
|--------|------------------------------|-------------------------------------------------|
| 200    | OK                           | Use the payload                                 |
| 201    | Created                      | Use the payload                                 |
| 400    | Bad request / rule violation | Show `message` to the user; keep form open      |
| 401    | Not authenticated            | Redirect to login (token expired or missing)    |
| 403    | Forbidden / ID mismatch      | Show `message`; token is valid but not allowed  |
| 404    | Not found                    | Show `message` / empty state                    |
| 409    | Conflict                     | Show `message` (already registered, limit, slot)|
| 429    | Too many requests            | Show `message`; back off and retry later        |
| 500    | Server error                 | Show generic error, retry later                 |

## Auth Flow (Bearer Tokens)

### 1. Leader login

```js
const res = await fetch(`${BASE}/loginleader`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ email, password }),
});
const body = await res.json();

// body.token  -> store it
// body.userid -> leader ID used in later calls
localStorage.setItem("leader_token", body.token);
localStorage.setItem("leader_id", body.userid);
```

### 2. Admin login

```js
const res = await fetch(`${BASE}/admin/adminlogin`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ adminId, password }),
});
const body = await res.json();

// body.token -> store it
// body.role  -> 1 (Super Admin) or 2 (Moderator); drives admin UI permissions
localStorage.setItem("admin_token", body.token);
localStorage.setItem("admin_role", String(body.role));
```

### 3. Send the token on every protected call

```js
const res = await fetch(`${BASE}/registerteam`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("leader_token")}`,
  },
  body: JSON.stringify(payload),
});
```

> The header value must be exactly `Bearer <token>` — a space between `Bearer` and the token.

### 4. Handle expiry / invalid token (401)

Tokens last **8 hours** (`JWT_EXPIRE_HOURS`). On a `401`, the message is one of:

- `Access denied. No token provided.`
- `Session expired. Please login again.`
- `Invalid token.`

Client behavior: clear stored tokens and redirect to the login screen.

### 5. Handle wrong-role (403)

If a token is valid but for the wrong audience the API returns `403`. Example messages:

- `Access denied. User only.`
- `Access denied. Admin only.`
- `Access denied. Super Admin only.`
- `Access denied. Leader ID mismatch.`
- `Access denied. User ID mismatch.`

## Protected vs Public Routes

| Route                          | Auth required                     |
|--------------------------------|-----------------------------------|
| `POST /regleader`              | None (public)                     |
| `POST /loginleader`            | None (public)                     |
| `POST /registerteam`           | Leader Bearer                     |
| `POST /getcandidates`          | Leader Bearer                     |
| `GET /stats/{leader_id}`       | Leader Bearer                     |
| `POST /addcollege`             | Super Admin Bearer (`adminRole: 1`) |
| `GET /getcollege`              | None (public)                     |
| `POST /admin/adminreg`         | Super Admin Bearer (`adminRole: 1`) |
| `POST /admin/adminlogin`       | None (public)                     |
| `POST /admin/viewteam`         | Admin Bearer (any role)           |
| `POST /admin/vieweventregs`    | Admin Bearer (any role)           |
| `DELETE /admin/deleteteam/{leader_id}`        | Admin Bearer (any role) |
| `DELETE /admin/deleteteambyevent/{leader_id}/{event}` | Admin Bearer (any role) |
| `GET /admin/dashboardstats`    | Admin Bearer (any role)           |

## Per-Endpoint Client Conditions

### `POST /regleader`

- Send all 8 fields. Omission → `400 "All fields are required"`.
- Normalize before sending: `email` lowercased is fine (server does it anyway), `mobilenumber` as digits.
- `password` rules: 8–128 chars, ≥1 uppercase, ≥1 lowercase, ≥1 digit, ≥1 special char, no spaces.
- `confirmpassword` must equal `password`.
- `department` must be `cs | it | ai | ds | ca`; `shift` must be `1 | 2`.
- On `400` show `message` verbatim (it explains which rule failed).
- On `201` save `userid`.

### `POST /loginleader`

- Send `email` and `password`.
- `401` = invalid credentials — show `Invalid Email or Password`.
- Trim email client-side to avoid accidental mismatch.

### `POST /registerteam` (Leader)

- **Must send the leader token** from `/loginleader`.
- Send `leaderId` exactly as received from login; a mismatch with the token yields `403`.
- `event` must be one of the 8 known events, else `400 Invalid event selected`.
- `participants` is a non-empty array.
- Per participant:
  - `name`, `registerNumber`, `mobile`, `degree` always required.
  - `mobile`: 10 digits starting 6–9.
  - `degree`: `ug` or `pg`.
  - `foodPreference` (`vegetarian` | `non-vegetarian`) required **only for students new to this leader**. For students already registered, it is ignored — send it or omit it, no error either way.
- Client should pre-check and surface conflicts before sending to reduce `409`s:
  - Team already registered for the event.
  - Leader would exceed 15 students.
  - Student already in 2 events.
  - Student in Bid Mayhem cannot join other events; Bid Mayhem cannot combine with another event.
  - Same-slot clash (both events in slot `1`, or both in slot `2`).
- `created` / `updated` in the response tell you how many were inserted vs. updated in place.

### `POST /getcandidates`

- Send `user_id` equal to the logged-in leader's `userid`, else `403`.
- `data` is an array of EventRegistration documents (one per student) including `foodPreference`, `event1/slot1`, `event2/slot2`.
- Use `registeredEvents` to build "already registered" UI states.

### `GET /stats/{leader_id}`

- Put the leader id in the URL path; must match the token's `userid`, else `403`.
- `studentsRemaining = 15 - totalStudents`; disable registration when it reaches 0.

### `POST /addcollege` (Super Admin only)

- Body is a **bare JSON array** of college objects — do not wrap it in an object.
- Each item needs `collegeId` and `name` (`state`/`district` recommended). Items missing them → `400`.
- Duplicate `collegeId` values are skipped; `count` tells you how many were actually inserted.

### `POST /admin/viewteam`

- Send `college` and `department`.
- Empty result returns `200` with an empty `data` array — handle as "no team", not as an error.

### `POST /admin/vieweventregs`

- Send `eventName` exactly (e.g. `Fixathon`, `Bid Mayhem`).
- No registrations → `404` — show an empty state.
- `data` is grouped by leader: each entry has `leaderId`, `college`, `department`, and `members[]`.

### `DELETE /admin/deleteteam/{leader_id}`

- Returns `deletedCount`. Confirmation dialog recommended — irreversible.

### `DELETE /admin/deleteteambyevent/{leader_id}/{event}`

- **URL-encode event names with spaces**: `Bid Mayhem` → `Bid%20Mayhem`.
- Returns `updatedCount` and `deletedCount`.

### `GET /admin/dashboardstats`

- Response `stats` contains all report numbers; render once per dashboard load.

## Common Client Pitfalls

1. **Forgetting the `Bearer ` prefix** — the API rejects with `401`.
2. **Not checking `success`** — always branch on `body.success`, not just `res.ok`.
3. **Sending `leaderId`/`user_id` that differs from the token** — `403`.
4. **Wrapping `addcollege` body in an object** — it must be an array, else `422`.
5. **Expecting a bare array from `getcollege`** — it now returns `data: [...]`.
6. **Storing tokens in plaintext** — fine for this scope; use `sessionStorage`/`localStorage` consistently and clear on logout.

## CORS

- Default: `*` (any origin). In production set `CORS_ORIGINS` in `.env` to a comma-separated allowlist, e.g. `CORS_ORIGINS=https://app.example.com,https://admin.example.com`.
- The API does not use cookies; keep `credentials` handling simple (tokens in headers).
