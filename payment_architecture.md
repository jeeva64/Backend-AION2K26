# Payment Architecture — AION 2K26 Backend

**Status:** FINAL — All decisions locked. Ready for implementation.
**Date:** 2026-09-21
**Supersedes:** payment_fix.md (previous session's analysis)

---

## Table of Contents

1. [Current System Summary](#1-current-system-summary)
2. [Problems Identified](#2-problems-identified)
3. [Decisions Made](#3-decisions-made)
4. [New Architecture](#4-new-architecture)
5. [Per-Event Team Size Limits](#5-per-event-team-size-limits)
6. [Registration Deadline Feature](#6-registration-deadline-feature)
7. [Post-Verification Expansion](#7-post-verification-expansion)
8. [Updated Wording](#8-updated-wording)
9. [File Changes (Implementation Checklist)](#9-file-changes)
10. [Implementation Order](#10-implementation-order)
11. [Edge Cases](#11-edge-cases)
12. [Test Plan](#12-test-plan)
13. [API Contracts](#13-api-contracts)

---

## 1. Current System Summary

### Stack

Python 3.11 / FastAPI 0.115 / SQLAlchemy 2.0 + asyncpg (Neon PostgreSQL) /
Alembic / Pydantic 2 / slowapi / PyJWT / bcrypt / boto3 (Neon Object Storage).

### Registration Rules (ALREADY IMPLEMENTED, DO NOT BREAK)

| Rule | Enforcement Location |
|---|---|
| One student max 2 events (slot 1 + slot 2) | `registration_sqla.py:109-118` (slot conflict checks) |
| Same-slot clash blocked | `registration_sqla.py:114-118` |
| Bid Mayhem = BOTH slots, exclusive with all other events | `registration_sqla.py:98-108` + DB trigger `trg_bid_mayhem` |
| 15 unique students per leader (across all events) | `registration_sqla.py:90-96` (`MAX_STUDENTS_PER_LEADER`) |
| One team per event per leader | `registration_sqla.py:47-52` (`find_leader_event`) |
| `register_number` = unique student identifier per leader | DB unique index `uq_event_registrations_leader_register` |
| `foodPreference` captured once, never overwritten | `registration_sqla.py:86-88` |
| Fee = unique_students x Rs.200 (per unique student, NOT per event) | `fees.py:16-20` (`REGISTRATION_FEE_PER_STUDENT_PAISE = 20000`) |
| One payment row per leader (bulk) | `payments` table UNIQUE on `leader_id` |

### Event Slot Map (DO NOT CHANGE)

```
EVENT_SLOT_MAP = {
    "Fixathon": "1",
    "Mute Masters": "1",
    "Treasure Titans": "1",
    "Bid Mayhem": "BOTH",
    "QRush": "2",
    "VisionX": "2",
    "ThinkSync": "2",
    "Crazy Sell": "2",
}
```

### Current Payment Flow

```
Leader registers students -> payment row created (PENDING)
Leader submits proof (UTR + screenshot) -> VERIFICATION_PENDING
Admin verifies -> SUCCESS -> all registrations = CONFIRMED
```

### Current Edit Lock (THE PROBLEM)

```python
# constants.py
PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")

# payment_sqla.py
def assert_team_edits_allowed(payment):
    if payment and payment["paymentStatus"] in PAYMENT_LOCKED_STATUSES:
        raise APIError(409, "Team changes are locked while your payment is "
                            "under review or confirmed. Contact an organizer.")
```

Called in `auth.py:1086` before every `/registerteam`. Once proof is submitted,
leader can NEVER add more students -- even after admin verification.

---

## 2. Problems Identified

| # | Problem | Impact |
|---|---|---|
| 1 | Payment lock blocks team edits permanently after proof submission | Leader can't expand team after verification |
| 2 | No registration deadline | Leaders expand indefinitely, blocking food orders |
| 3 | No per-event team size limits | Events can have arbitrarily large teams |
| 4 | Wording implies registration is confirmed before admin verification | User confusion |
| 5 | After verification, no way to add supplementary students | Inflexible |

---

## 3. Decisions Made

These are LOCKED decisions from user conversations. Do not reopen.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Remove payment-based edit lock entirely** | Replace with deadline-based lock. Payment lock was too aggressive. |
| D2 | **Add admin-set registration deadline** | Admin controls cutoff for food ordering logistics. |
| D3 | **Deadline blocks `/regleader` and `/registerteam` only** | Payment proof submission still allowed after deadline (for already-registered students). Admin actions always allowed. |
| D4 | **Deadline is global** (not per-shift, not per-event) | Single cutoff for all leaders. Admin sets via API. |
| D5 | **Admin configures deadline via API endpoint** | `PUT /admin/registration-deadline`. Super Admin only. |
| D6 | **Post-verification expansion allowed** | After SUCCESS, leader can add more students (if deadline not passed, under 15 cap). New students = PAYMENT_PENDING, need supplementary payment. |
| D7 | **Supplementary payment uses same `/payments/proof` endpoint** | Payment transitions SUCCESS -> VERIFICATION_PENDING. Admin verifies again. |
| D8 | **Per-event team size limits** | Fixathon(2), Mute Masters(2), Treasure Titans(2), Bid Mayhem(2), QRush(2), VisionX(1), ThinkSync(2), Crazy Sell(4). |
| D9 | **Update wording** to clarify registration is pending until admin confirms payment | User clarity. |
| D10 | **Keep per-event registration flow** (cart-like) | Leader calls `/registerteam` multiple times, then pays once. Don't break existing flow. |
| D11 | **Deadline enforcement = "Block everything"** for registrations | After deadline: no new leaders, no new teams, no edits. But payment submission allowed. |
| D12 | **Fee remains per unique student x Rs.200** | Not per event. Already correct in code. |

---

## 4. New Architecture

### High-Level Flow

```
+-------------------------------------------------------------------+
|  1. Register as Leader (/regleader)                                |
|     |-- CHECK: deadline not passed                                 |
|                                                                    |
|  2. Login (/loginleader)                                           |
|                                                                    |
|  3. CART PHASE -- Add students to ALL events (/registerteam)       |
|     |-- Call 1: Event 1 (2 students, slot 1)                       |
|     |-- Call 2: Event 2 (2 students, slot 2)                       |
|     |-- Call 3: Event 3 (1 student, slot 2)                        |
|     |-- ... (no verification needed between calls)                 |
|     |-- Each call validates:                                       |
|     |   [CHECK] Deadline not passed                                |
|     |   [CHECK] Per-event max (2/1/4)                              |
|     |   [CHECK] 15-student total cap                               |
|     |   [CHECK] Slot conflicts prevented                           |
|     |   [CHECK] Max 2 events per student                           |
|     |   [CHECK] Bid Mayhem exclusivity                             |
|     |   [CHECK] One team per event per leader                      |
|                                                                    |
|  4. PAY -- One bulk proof (/payments/proof)                        |
|     |-- Fee = unique_students x Rs.200                             |
|     |-- NO EDIT LOCK (payment lock removed)                        |
|                                                                    |
|  5. ADMIN VERIFIES (/admin/payments/{id}/verify)                   |
|     |-- All VERIFICATION_PENDING -> CONFIRMED                      |
|                                                                    |
|  6. EXPANSION (Optional, before deadline)                          |
|     |-- Add more students -> new = PAYMENT_PENDING                 |
|     |-- Submit supplementary proof -> SUCCESS ->                   |
|     |                VERIFICATION_PENDING                           |
|     |-- Admin verifies again -> new CONFIRMED                      |
+-------------------------------------------------------------------+
```

### Deadline Enforcement Matrix

```
+----------------------+-------------------+--------------------------+
|  Endpoint            |  BEFORE Deadline  |  AFTER Deadline          |
+----------------------+-------------------+--------------------------+
|  POST /regleader     |  Allowed          |  "Registration is        |
|                      |                   |   closed"                |
+----------------------+-------------------+--------------------------+
|  POST /registerteam  |  Allowed          |  "Registration           |
|                      |                   |   deadline has passed"   |
+----------------------+-------------------+--------------------------+
|  POST /payments/proof|  Allowed          |  Allowed                 |
|                      |                   |  (pay for already        |
|                      |                   |   registered students)   |
+----------------------+-------------------+--------------------------+
|  Admin verify/reject |  Allowed          |  Allowed                 |
+----------------------+-------------------+--------------------------+
|  Admin DELETE team   |  Allowed          |  Allowed                 |
+----------------------+-------------------+--------------------------+
```

### Payment State Machine (Updated)

```
PENDING --> VERIFICATION_PENDING --> SUCCESS
   ^              |    ^                |
   |              |    |                | Add more students
   |              v    |                | (deadline ok, under 15 cap)
   |           REJECTED|                v
   |              |    |         New regs = PAYMENT_PENDING
   |              |    |         Submit supplementary proof
   |              ^    |         SUCCESS -> VERIFICATION_PENDING
   |              |    |         Admin verifies -> SUCCESS (again)
   ^--------------+----+----------------+
   |           (reopen)
```

---

## 5. Per-Event Team Size Limits

### Limits

| Event | Slot | Max Members |
|---|---|---|
| Fixathon | 1 | 2 |
| Mute Masters | 1 | 2 |
| Treasure Titans | 1 | 2 |
| Bid Mayhem | BOTH | 2 |
| QRush | 2 | 2 |
| VisionX | 2 | **1** |
| ThinkSync | 2 | 2 |
| Crazy Sell | 2 | **4** |

### How the 15-Student Cap Aligns

Without Bid Mayhem:
- Slot 1 events: Fixathon(2) + Mute Masters(2) + Treasure Titans(2) = 6 registrations
- Slot 2 events: QRush(2) + VisionX(1) + ThinkSync(2) + Crazy Sell(4) = 9 registrations
- Total event slots: 15

A student can fill 1 slot-1 event + 1 slot-2 event -> max 15 unique students.

With Bid Mayhem:
- Bid Mayhem: 2 students (both slots, exclusive)
- + 0 other events
- -> max 2 unique students

### Validation

In `register_team`, BEFORE the 15-student cap check:

```python
EVENT_MAX_TEAM_SIZE = {
    "Fixathon": 2,
    "Mute Masters": 2,
    "Treasure Titans": 2,
    "Bid Mayhem": 2,
    "QRush": 2,
    "VisionX": 1,
    "ThinkSync": 2,
    "Crazy Sell": 4,
}

# Add after line 53 (reg_numbers extraction):
max_size = EVENT_MAX_TEAM_SIZE.get(event, 2)
if len(participants) > max_size:
    raise APIError(400, f"{event} allows a maximum of {max_size} members per team.")
```

---

## 6. Registration Deadline Feature

### New Table: `event_settings`

Single-row table (id = 1, CHECK constraint enforces this).

```sql
CREATE TABLE event_settings (
    id                  BIGINT PRIMARY KEY DEFAULT 1,
    registration_deadline TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_event_settings_single_row CHECK (id = 1)
);
```

### New Files

1. **`app/models_sqla/event_settings.py`** -- ORM model
2. **`app/repositories_sqla/event_settings_repository.py`** -- Repository with `get()` and `set_deadline()`
3. **`alembic/versions/0005_registration_deadline.py`** -- Migration

### New Admin Endpoints

```
PUT /admin/registration-deadline  (Super Admin only)
Body: { "deadline": "2026-10-01T23:59:59Z" }  // ISO 8601
  Or:  { "deadline": null }                     // removes deadline
Response: { "success": true, "message": "Registration deadline set", "deadline": "..." }

GET /admin/registration-deadline  (Super Admin only)
Response: { "success": true, "deadline": "2026-10-01T23:59:59Z" }
```

### Deadline Check Logic

```python
from datetime import datetime, timezone

async def assert_registration_open(session: AsyncSession) -> None:
    """Raise 400 if registration deadline has passed."""
    repo = EventSettingsRepositorySqla(session)
    settings = await repo.get()
    if settings and settings.get("deadline"):
        if datetime.now(timezone.utc) > settings["deadline"]:
            raise APIError(400, "Registration deadline has passed. Contact an organizer.")
```

Called in:
- `POST /regleader` -- before creating leader
- `POST /registerteam` -- before registering team

NOT called in:
- `POST /payments/proof` -- payment allowed after deadline
- `POST /admin/payments/{id}/verify` -- admin always allowed

### Leader-Facing Deadline Exposure

Add `registrationDeadline` to:
- `GET /payments/mine` response
- `GET /stats/{leader_id}` response

This allows the frontend to show a countdown and disable the register button.

---

## 7. Post-Verification Expansion

### How It Works

After admin verifies payment (SUCCESS), leader CAN add more students:

1. Leader calls `POST /registerteam` with new students
2. New students get `PAYMENT_PENDING` status
3. Existing `CONFIRMED` students are unchanged
4. Fee recalculates: `new_unique_count x 200`
5. Leader calls `POST /payments/proof` (supplementary)
6. Payment transitions: `SUCCESS -> VERIFICATION_PENDING`
7. New registrations flip: `PAYMENT_PENDING -> VERIFICATION_PENDING`
8. Admin verifies: `VERIFICATION_PENDING -> SUCCESS` (all new ones become CONFIRMED)

### Code Changes for Supplementary Flow

**`payment_sqla.py` `submit_payment_proof`:**

```python
# BEFORE (blocks SUCCESS):
if status == "SUCCESS":
    raise APIError(409, "Payment is already verified.")
if status not in ("PENDING", "REJECTED"):
    raise APIError(409, "A different payment proof is already under review.")

# AFTER (allows SUCCESS when new students exist):
if status == "SUCCESS":
    has_pending = await event_regs.has_pending_registrations(leader_id)
    if not has_pending:
        raise APIError(409, "Payment is already verified. No pending registrations found.")
    # Fall through to proof validation -- supplementary payment
elif status not in ("PENDING", "REJECTED"):
    raise APIError(409, "A different payment proof is already under review.")
```

**`payment_sqla.py` `submit_proof_update` call:**

```python
# BEFORE:
from_statuses=("PENDING", "REJECTED"),

# AFTER:
from_statuses=("PENDING", "REJECTED", "SUCCESS"),
```

**`event_registration_repository.py` -- new helper:**

```python
async def has_pending_registrations(self, leader_id: str) -> bool:
    """True when leader has students in PAYMENT_PENDING (needs supplementary pay)."""
    stmt = select(func.count()).select_from(EventRegistration).where(
        EventRegistration.leader_id == leader_id,
        EventRegistration.status == "PAYMENT_PENDING",
    )
    result = await self._session.execute(stmt)
    return int(result.scalar_one()) > 0
```

---

## 8. Updated Wording

| File | Location | Before | After |
|---|---|---|---|
| `auth.py` | `/registerteam` success msg | `f"Team of {len(payload.participants)} registered for {payload.event}."` | `f"Team of {len(payload.participants)} registered for {payload.event}. Complete payment to confirm your registration."` |
| `payment_sqla.py` | `assert_team_edits_allowed` error | `"Team changes are locked while your payment is under review or confirmed. Contact an organizer for modifications."` | **DELETE entire function** -- no payment lock |
| `auth.py` | `/payments/proof` success msg | `"Payment proof submitted for verification"` | `"Payment proof submitted. Registration will be confirmed once organizer verifies your payment."` |
| `auth.py` | `/regleader` error (new) | -- | `"Registration is closed. Contact organizer."` |
| `auth.py` | `/registerteam` error (new) | -- | `"Registration deadline has passed. Contact an organizer."` |

---

## 9. File Changes

### New Files (4)

| File | Description |
|---|---|
| `app/models_sqla/event_settings.py` | ORM model for `event_settings` table |
| `app/repositories_sqla/event_settings_repository.py` | Repository: `get()`, `set_deadline()` |
| `alembic/versions/0005_registration_deadline.py` | Migration: create `event_settings` table |
| `payment_architecture.md` | This document |

### Modified Files (14)

| File | Change | Lines Affected |
|---|---|---|
| `app/utils/constants.py` | Add `EVENT_MAX_TEAM_SIZE` dict. Remove `PAYMENT_LOCKED_STATUSES`. | ~10 lines |
| `app/services/registration_sqla.py` | Add per-event team size check in `register_team`. | ~5 lines (after line 53) |
| `app/services/payment_sqla.py` | **Delete** `assert_team_edits_allowed()`. Modify `submit_payment_proof` to allow SUCCESS->VERIFICATION_PENDING. Update `from_statuses` in `submit_proof_update` call. | ~15 lines |
| `app/repositories_sqla/event_registration_repository.py` | Add `has_pending_registrations()` method. | ~10 lines |
| `app/repositories_sqla/__init__.py` | Export `EventSettingsRepositorySqla`. | ~2 lines |
| `app/dependencies/repositories.py` | Add `get_event_settings_repo` dependency. | ~5 lines |
| `app/api/admin.py` | Add `PUT /admin/registration-deadline` and `GET /admin/registration-deadline` endpoints. Import new repo dependency. | ~30 lines |
| `app/api/auth.py` | In `/regleader`: add deadline check. In `/registerteam`: replace `assert_team_edits_allowed` with deadline check. In `/payments/mine` and `/stats/{leader_id}`: expose `registrationDeadline`. Update wording. | ~20 lines |
| `app/schemas/admin.py` | Add `SetDeadlineRequest` and `DeadlineResponse` models. | ~15 lines |
| `app/schemas/auth.py` | Update `RegisterTeamResponse` success message wording. | ~1 line |
| `tests/conftest.py` | Add `event_settings` to TRUNCATE cleanup. | ~1 line |
| `tests/payment_flow_test.py` | Remove `test_edit_lock_after_proof_submission`. Add tests: `test_post_verification_expansion`, `test_deadline_blocks_registration`, `test_supplementary_payment_flow`, `test_per_event_team_size_limits`. | ~100 lines |
| `.env.example` | Add `REGISTRATION_DEADLINE` comment (optional). | ~2 lines |

### Deleted Code

| File | What | Why |
|---|---|---|
| `payment_sqla.py` | `assert_team_edits_allowed()` function (lines 73-80) | Payment lock removed entirely |
| `constants.py` | `PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")` (line 50) | No longer needed |
| `auth.py:1086` | `assert_team_edits_allowed(await payments.find_by_leader(payload.leaderId))` | Replaced with deadline check |

---

## 10. Implementation Order

| Step | Task | Files | Depends On |
|---|---|---|---|
| 1 | Add `EVENT_MAX_TEAM_SIZE` to constants, remove `PAYMENT_LOCKED_STATUSES` | `constants.py` | -- |
| 2 | Add per-event team size validation in `register_team` | `registration_sqla.py` | Step 1 |
| 3 | Delete `assert_team_edits_allowed` | `payment_sqla.py` | Step 1 |
| 4 | Add `has_pending_registrations` to event registration repo | `event_registration_repository.py` | -- |
| 5 | Modify `submit_payment_proof` for supplementary flow | `payment_sqla.py` | Step 4 |
| 6 | Create `EventSettings` ORM model | `models_sqla/event_settings.py` | -- |
| 7 | Create `EventSettingsRepositorySqla` | `repositories_sqla/event_settings_repository.py` | Step 6 |
| 8 | Create Alembic migration 0005 | `alembic/versions/0005_registration_deadline.py` | Step 6 |
| 9 | Wire new repo in `__init__.py` and `dependencies/repositories.py` | `repositories_sqla/__init__.py`, `dependencies/repositories.py` | Step 7 |
| 10 | Add deadline admin endpoints | `api/admin.py` | Step 9 |
| 11 | Add deadline check to `/regleader` and `/registerteam`, expose deadline, update wording | `api/auth.py` | Steps 2, 3, 9 |
| 12 | Add schemas | `schemas/admin.py`, `schemas/auth.py` | -- |
| 13 | Update tests | `tests/conftest.py`, `tests/payment_flow_test.py` | All above |
| 14 | Run `alembic upgrade head` + `pytest tests -v` | -- | Step 13 |

---

## 11. Edge Cases

| Scenario | Behavior | Enforcement |
|---|---|---|
| Leader tries Fixathon with 3 students | 400 "Fixathon allows a maximum of 2 members per team" | Per-event size check |
| Leader tries Crazy Sell with 5 students | 400 "Crazy Sell allows a maximum of 4 members per team" | Per-event size check |
| Leader tries VisionX with 2 students | 400 "VisionX allows a maximum of 1 member per team" | Per-event size check |
| Leader at 15 students, tries to add more | 409 "15-student limit reached" | Existing `MAX_STUDENTS_PER_LEADER` |
| Leader registers before deadline, deadline passes | Can still PAY, cannot add new students | Deadline check only on `/registerteam` |
| Leader adds students while admin reviews first proof | Fee increases, admin sees expected > submitted mismatch | No payment lock |
| Admin rejects after some CONFIRMED + some VERIFICATION_PENDING | Only VERIFICATION_PENDING revert; CONFIRMED stay | `from_statuses` guard |
| No deadline set (null) | Registrations always open | Null check in deadline logic |
| Bid Mayhem + any other event | 409 "Bid Mayhem cannot be combined" | Existing validation |
| Student in 2 slot-1 events | 409 "already has {event} in the same time slot" | Existing validation |
| Supplementary proof, no pending registrations | 409 "Payment is already verified. No pending registrations found." | New `has_pending_registrations` check |
| Admin sets deadline to past date | Immediately blocks all registrations | `datetime.now(timezone.utc) > deadline` |
| Admin sets deadline then removes it (null) | Registrations reopen | Null = no deadline |
| Two concurrent `/registerteam` calls | Both succeed if under 15 cap (race-safe via single transaction) | Existing transaction safety |
| Leader at 11 students after verification, wants 15 | Add 4 more (deadline permitting), supplementary payment | Post-verification expansion |

---

## 12. Test Plan

### New Tests to Add

```python
def test_per_event_team_size_limits(client):
    """Each event enforces its max team size."""
    leader_id, token = _register_leader(client, "size")

    # Fixathon max 2
    r = _register_team(client, token, leader_id, "Fixathon", count=3)
    assert r.status_code == 400 and "maximum of 2" in r.json()["message"]

    # VisionX max 1
    r = _register_team(client, token, leader_id, "VisionX", count=2)
    assert r.status_code == 400 and "maximum of 1" in r.json()["message"]

    # Crazy Sell max 4
    r = _register_team(client, token, leader_id, "Crazy Sell", count=5)
    assert r.status_code == 400 and "maximum of 4" in r.json()["message"]

    # Within limits succeeds
    assert _register_team(client, token, leader_id, "Fixathon", count=2).status_code == 200
    assert _register_team(client, token, leader_id, "VisionX", count=1).status_code == 200
    assert _register_team(client, token, leader_id, "Crazy Sell", count=4).status_code == 200


def test_deadline_blocks_registration(client):
    """After deadline, /regleader and /registerteam are blocked."""
    # Set deadline in the past
    sa = _super_admin_headers(client)
    r = client.put("/admin/registration-deadline",
                   headers=sa,
                   json={"deadline": "2020-01-01T00:00:00Z"})
    assert r.status_code == 200

    # New leader registration blocked
    r = client.post("/regleader", json={...})
    assert r.status_code == 400 and "closed" in r.json()["message"].lower()

    # Existing leader can't add teams
    r = _register_team(client, token, leader_id, "Fixathon", count=1)
    assert r.status_code == 400 and "deadline" in r.json()["message"].lower()

    # But can still submit proof
    r = _submit_proof(client, token, amount=fee, content=_png_bytes())
    assert r.status_code == 200


def test_deadline_removed_reopens(client):
    """Removing deadline reopens registration."""
    sa = _super_admin_headers(client)

    # Set and verify blocked
    client.put("/admin/registration-deadline",
               headers=sa, json={"deadline": "2020-01-01T00:00:00Z"})

    # Remove deadline
    r = client.put("/admin/registration-deadline",
                   headers=sa, json={"deadline": None})
    assert r.status_code == 200

    # Registration allowed again
    r = _register_team(client, token, leader_id, "Fixathon", count=1)
    assert r.status_code == 200


def test_post_verification_expansion(client):
    """After admin verifies, leader can add more students."""
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "expand")
    headers = {"Authorization": f"Bearer {token}"}

    # Register 2 students, pay, verify
    assert _register_team(client, token, leader_id, "VisionX", count=1).status_code == 200
    assert _register_team(client, token, leader_id, "QRush", count=2).status_code == 200
    assert _submit_proof(client, token, amount=3*fee, content=_png_bytes()).status_code == 200

    sa = _super_admin_headers(client)
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    pid = next(p for p in listed["data"] if p["leaderId"] == leader_id)["_id"]
    assert client.post(f"/admin/payments/{pid}/verify", headers=sa).status_code == 200

    # All 3 confirmed
    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    assert all(d["status"] == "CONFIRMED" for d in cands["data"])

    # Add 2 more students (expansion)
    assert _register_team(client, token, leader_id, "ThinkSync", count=2).status_code == 200

    # New 2 are PAYMENT_PENDING, old 3 stay CONFIRMED
    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    statuses = {d["status"] for d in cands["data"]}
    assert "CONFIRMED" in statuses and "PAYMENT_PENDING" in statuses

    # Submit supplementary proof
    r = _submit_proof(client, token, utr=f"SUPP{uuid.uuid4().hex[:4].upper()}",
                      amount=5*fee, content=_png_bytes())
    assert r.status_code == 200

    # Admin verifies supplementary
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    pid = next(p for p in listed["data"] if p["leaderId"] == leader_id)["_id"]
    assert client.post(f"/admin/payments/{pid}/verify", headers=sa).status_code == 200

    # All 5 confirmed
    cands = client.post("/getcandidates", headers=headers, json={"user_id": leader_id}).json()
    assert all(d["status"] == "CONFIRMED" for d in cands["data"])
    assert len(cands["data"]) == 5


def test_supplementary_proof_blocked_when_no_pending(client):
    """Can't submit supplementary proof if all students are already confirmed."""
    fee = settings.REGISTRATION_FEE_PER_STUDENT_PAISE
    leader_id, token = _register_leader(client, "nosupp")

    assert _register_team(client, token, leader_id, "Fixathon", count=1).status_code == 200
    assert _submit_proof(client, token, amount=fee, content=_png_bytes()).status_code == 200

    sa = _super_admin_headers(client)
    listed = client.get("/admin/payments?status=VERIFICATION_PENDING", headers=sa).json()
    pid = next(p for p in listed["data"] if p["leaderId"] == leader_id)["_id"]
    assert client.post(f"/admin/payments/{pid}/verify", headers=sa).status_code == 200

    # Try supplementary proof with no new students
    r = _submit_proof(client, token, utr=f"X{uuid.uuid4().hex[:8].upper()}",
                      amount=fee, content=_png_bytes())
    assert r.status_code == 409 and "No pending" in r.json()["message"]
```

### Existing Tests to Update

| Test | Change |
|---|---|
| `test_edit_lock_after_proof_submission` | **DELETE** -- payment lock no longer exists |
| `test_full_payment_lifecycle` | No change needed (flow unchanged) |
| `test_proof_validation_errors` | No change needed |
| `test_duplicate_utr_across_leaders` | No change needed |
| `test_amount_mismatch_goes_to_manual_review` | No change needed |
| `test_reject_resubmit_and_invalid_transitions` | No change needed |
| `test_reopen_rejected_payment_super_admin_only` | No change needed |

---

## 13. API Contracts

### Modified Endpoints

#### `POST /registerteam` (Response change)

```json
// BEFORE:
{ "success": true, "message": "Team of 2 registered for Fixathon.", ... }

// AFTER:
{ "success": true, "message": "Team of 2 registered for Fixathon. Complete payment to confirm your registration.", ... }
```

#### `POST /payments/proof` (Response change)

```json
// BEFORE:
{ "success": true, "message": "Payment proof submitted for verification", ... }

// AFTER:
{ "success": true, "message": "Payment proof submitted. Registration will be confirmed once organizer verifies your payment.", ... }
```

#### `GET /payments/mine` (New field)

```json
{
  "success": true,
  "uniqueStudents": 11,
  "amountDuePaises": 220000,
  "upiUri": "upi://pay?...",
  "registrationDeadline": "2026-10-01T23:59:59Z",
  "data": { ... }
}
```

#### `GET /stats/{leader_id}` (New field)

```json
{
  "success": true,
  "stats": {
    "totalStudents": 11,
    "studentsRemaining": 4,
    "eventsRegistered": 7,
    "registeredEvents": [...],
    "registrationDeadline": "2026-10-01T23:59:59Z"
  }
}
```

### New Endpoints

#### `PUT /admin/registration-deadline`

Super Admin only.

```
Request:  { "deadline": "2026-10-01T23:59:59Z" }  // ISO 8601
  Or:     { "deadline": null }                       // removes deadline

Response: { "success": true, "message": "Registration deadline set", "deadline": "2026-10-01T23:59:59Z" }
```

#### `GET /admin/registration-deadline`

Super Admin only.

```
Response: { "success": true, "deadline": "2026-10-01T23:59:59Z" }
  Or:     { "success": true, "deadline": null }
```

### Deleted Code

#### `POST /registerteam` -- Removed check

```python
# DELETED (was at auth.py:1086):
assert_team_edits_allowed(await payments.find_by_leader(payload.leaderId))

# REPLACED WITH:
await assert_registration_open(session)
```

#### `assert_team_edits_allowed` -- Function deleted

```python
# DELETED from payment_sqla.py (lines 73-80):
def assert_team_edits_allowed(payment: dict | None) -> None:
    if payment and payment["paymentStatus"] in PAYMENT_LOCKED_STATUSES:
        raise APIError(409, "Team changes are locked...")
```

---

## Appendix: Complete Example Flow

### Leader Registers for 7 Events (11 Unique Students)

```
Call 1: Fixathon -- 2 students (slot 1)
  -> A (slot 1: Fixathon), B (slot 1: Fixathon)
  -> Fee: 2 x 200 = Rs.400

Call 2: Mute Masters -- 2 students (slot 1)
  -> C (slot 1: Mute Masters), D (slot 1: Mute Masters)
  -> Fee: 4 x 200 = Rs.800

Call 3: Treasure Titans -- 2 students (slot 1)
  -> E (slot 1: Treasure Titans), F (slot 1: Treasure Titans)
  -> Fee: 6 x 200 = Rs.1200

Call 4: QRush -- 2 students (slot 2)
  -> G (slot 2: QRush), H (slot 2: QRush)
  -> Fee: 8 x 200 = Rs.1600

Call 5: VisionX -- 1 student (slot 2)
  -> A (slot 2: VisionX) <- A now in 2 events!
  -> Fee: 8 x 200 = Rs.1600 (A already counted)

Call 6: ThinkSync -- 2 students (slot 2)
  -> B (slot 2: ThinkSync) <- B now in 2 events!
  -> I (slot 2: ThinkSync) <- new
  -> Fee: 9 x 200 = Rs.1800

Call 7: Crazy Sell -- 4 students (slot 2)
  -> C (slot 2: Crazy Sell) <- C in 2 events!
  -> D (slot 2: Crazy Sell) <- D in 2 events!
  -> J (slot 2: Crazy Sell), K (slot 2: Crazy Sell) <- new
  -> Fee: 11 x 200 = Rs.2200

Pay: UTR + Rs.2200 screenshot -> VERIFICATION_PENDING
Admin verify -> ALL 11 CONFIRMED across 7 events
```

### Result

```
Students: 11 unique across 7 events
A: Fixathon (slot 1) + VisionX (slot 2)
B: Fixathon (slot 1) + ThinkSync (slot 2)
C: Mute Masters (slot 1) + Crazy Sell (slot 2)
D: Mute Masters (slot 1) + Crazy Sell (slot 2)
E: Treasure Titans (slot 1)
F: Treasure Titans (slot 1)
G: QRush (slot 2)
H: QRush (slot 2)
I: ThinkSync (slot 2)
J: Crazy Sell (slot 2)
K: Crazy Sell (slot 2)

Events:
  Fixathon:     A, B        (2/2)
  Mute Masters: C, D        (2/2)
  Treasure:     E, F        (2/2)
  QRush:        G, H        (2/2)
  VisionX:      A           (1/1)
  ThinkSync:    B, I        (2/2)
  Crazy Sell:   C, D, J, K  (4/4)
```
