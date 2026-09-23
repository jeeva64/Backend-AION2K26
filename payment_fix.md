# Student leader event payment architecture

**Session ID:** ses_f4601a3b1ffeGw7BeoyVagu4hN
**Created:** 9/19/2026, 7:37:29 PM
**Updated:** 9/19/2026, 7:40:33 PM

---

## User

review the student leader payment on the their dashboard. the payment should be done by the student leader as one event team upto the admin verfications, the other event registrations are blocked on the my demo test for the student leader. is it correct practice. plan the me the right architecture. here total allowed members for registration is 15, so shall we get the payment as one bulk. but there maybe chances of registrations less than 15 members too. how to handle this situations. or option 2 is to remove blocking of other event registrations by the student leader to pay. but it is tedious on the admin side due to the verifications of upi payment with proof for each individual event. so i am prefering to have one bulk payment to the student leader after all event members are added to the db and pay button to complete the registrations. in this situations, once the payment is done, shall we allow other event registrations if their 15 limit is not obtained, so they can expand their team to the other events too. discuss with me and plan the right architecture without confusions and problems. review the codebase first

---

## Assistant (Plan · MiMo V2.5 Free · 94.7s)

_Thinking:_

The user is asking me to review the current payment and registration architecture for a student leader system in their AION backend project. They want to understand:

1. Current flow: Student leader pays for their team, other event registrations are blocked until admin verification
2. Concerns about this approach - is it correct practice?
3. They want to handle cases where registrations might be less than 15 members
4. They prefer one bulk payment from the student leader
5. After payment, should they allow expanding to other events if 15 limit isn't reached?

Let me first explore the codebase to understand the current architecture, then provide recommendations.

I need to:
1. Look at the registration flow
2. Look at the payment flow
3. Understand the blocking mechanism
4. Review the admin verification process
5. Check the team size limitsLet me start by exploring the relevant files.

I'll review the codebase to understand the current payment and registration architecture. Let me explore the key files.

**Tool: task**

**Input:**
```json
{
  "description": "Explore registration architecture",
  "prompt": "I need to understand the current registration and payment architecture for the AION backend project. Please explore these specific areas and return a comprehensive summary:\n\n1. **Registration Flow**: Read `app/services/registration_sqla.py` - understand how teams are registered, how events are assigned to students, what happens with the 15-member limit, and what the blocking mechanism is for other events.\n\n2. **Payment Flow**: Read `app/services/payment_sqla.py` - understand how payments work, the status transitions, and how it ties to registration.\n\n3. **Fees Calculation**: Read `app/services/fees.py` - understand how fees are calculated (bulk vs per-student).\n\n4. **API Routes**: Read `app/api/admin.py` and `app/api/auth.py` - find the registration and payment endpoints.\n\n5. **Models**: Check `app/models_sqla/` for the event_registrations and payments table schemas.\n\n6. **Constants**: Read `app/utils/constants.py` for event slot definitions and limits.\n\nReturn a detailed summary of:\n- How the current registration flow works (step by step)\n- How the current payment flow works\n- What the 15-member limit enforcement looks like\n- What \"blocking other event registrations\" means in the current code\n- How admin verification works for payments\n- Any assumptions about team size and payment calculation",
  "subagent_type": "explore"
}
```

**Output:**
```
<task id="ses_f46017d3fffee9WtAudsXRFn0R" state="completed">
<task_result>
It looks like the summary was cut off at section 6. Let me complete it and add the remaining sections.

---

## 6. ADMIN VERIFICATION WORKFLOW (Detailed)

All three admin payment endpoints are restricted to **Super Admin only** (`adminRole: 1`, enforced by `get_current_super_admin` dependency). Moderators (`adminRole: 2`) receive 403 at these routes.

### Verification Guard Pattern
Every status transition follows the same pattern:
1. Load the payment row.
2. Check the current status matches the expected source status. If not, return 409 with a message showing the current status.
3. Execute a **guarded UPDATE** with a `WHERE payment_status = <expected>` clause.
4. Check `rowcount`. If 0, it means a concurrent request changed the status first -- return 409 ("status changed concurrently").
5. Flip all of the leader's registration rows in `event_registrations` via `update_status_by_leader()`, also guarded with `from_statuses`.
6. Append an audit record to `payment_audit`.

This means every transition is **optimistically locked** and **atomic** within a single async session transaction.

### Verify (`POST /admin/payments/{payment_id}/verify`)
- Source: `VERIFICATION_PENDING`
- Target: `SUCCESS` (payment) / `CONFIRMED` (registrations)
- Sets `verified_by` and `verified_at` on the payment row.
- Returns the updated payment with `confirmedRegistrations` count.

### Reject (`POST /admin/payments/{payment_id}/reject`)
- Source: `VERIFICATION_PENDING`
- Target: `REJECTED` (payment) / `PAYMENT_PENDING` (registrations)
- Requires a `reason` string in the request body.
- Returns the updated payment with `revertedRegistrations` count.
- The leader can then resubmit new proof via `POST /payments/proof`.

### Reopen (`POST /admin/payments/{payment_id}/reopen`)
- Source: `REJECTED`
- Target: `VERIFICATION_PENDING` (payment) / `VERIFICATION_PENDING` (registrations)
- Only available to Super Admin (not moderators).
- Clears `rejection_reason`.
- Returns the updated payment with `promotedRegistrations` count.

### View Proof (`GET /admin/payments/{payment_id}/proof`)
- Returns a signed URL (B2, 300s TTL) or a local proxy URL.
- The `/proof/content` sub-route streams the raw bytes directly. Proofs are never publicly reachable.

### List All Payments (`GET /admin/payments`)
- Optional `?status=` query param to filter by status.
- Joins with `users` (leader name, college, department) and `admins` (verifier name).
- Ordered by `submitted_at DESC NULLS LAST`, then `id DESC`.

### Payment Detail (`GET /admin/payments/{payment_id}`)
- Returns the full payment object plus the complete append-only `payment_audit` trail.

---

## 7. DATABASE SCHEMAS (Key Tables)

### `event_registrations` (one row per student per leader)
| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | Auto-increment |
| `leader_id` | Text FK -> users | CASCADE on delete |
| `name` | Text | Student name |
| `register_number` | Text | Uppercased, unique per (leader, register_number) |
| `mobile` | Text | 10-digit, starts with 6-9 |
| `college_name_text` | Text | College name (free text) |
| `college_id` | BigInteger FK -> colleges | Nullable, SET NULL on delete |
| `department` | Text | CHECK: cs/it/ai/ds/ca |
| `degree` | Text | CHECK: ug/pg |
| `food_preference` | Text | CHECK: vegetarian/non-vegetarian |
| `event1_id` | BigInteger FK -> events | Always set |
| `slot1_id` | BigInteger FK -> event_slots | Always set |
| `event2_id` | BigInteger FK -> events | Nullable (second event) |
| `slot2_id` | BigInteger FK -> event_slots | Nullable (paired with event2) |
| `status` | Text | CHECK: PAYMENT_PENDING/VERIFICATION_PENDING/CONFIRMED/REJECTED |

**Key constraints**:
- `(event2_id IS NULL AND slot2_id IS NULL) OR (event2_id IS NOT NULL AND slot2_id IS NOT NULL)` -- event2/slot2 are paired.
- `event2_id IS NULL OR event1_id <> event2_id` -- distinct events.
- `slot2_id IS NULL OR slot1_id <> slot2_id` -- no same-slot clash.
- Unique index on `(leader_id, register_number)`.
- DB trigger `trg_bid_mayhem` rejects Bid Mayhem combined with any other event.

### `payments` (one row per leader, UNIQUE)
| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | Also serves as `paymentId` |
| `leader_id` | Text FK -> users | UNIQUE index |
| `expected_amount_paises` | BigInteger | CHECK >= 0 |
| `submitted_amount_paises` | BigInteger | Nullable, CHECK >= 0 |
| `currency` | Text | CHECK = 'INR' |
| `utr` | Text | Nullable, UNIQUE partial index (where not null) |
| `payment_status` | Text | CHECK: PENDING/VERIFICATION_PENDING/SUCCESS/REJECTED |
| `proof_object_key` | Text | Storage key (B2 or local) |
| `proof_original_filename` | Text | Original upload name |
| `proof_mime_type` | Text | image/jpeg, image/png, image/webp |
| `proof_file_size` | BigInteger | Bytes |
| `submitted_at` | DateTime(tz) | Set on proof submission |
| `verified_at` | DateTime(tz) | Set on admin verify |
| `verified_by` | Text FK -> admins | Admin who verified |
| `rejection_reason` | Text | Set on reject, cleared on reopen |

### `payment_audit` (append-only audit trail)
| Column | Type | Notes |
|---|---|---|
| `id` | BigInteger PK | |
| `payment_id` | BigInteger FK -> payments | CASCADE on delete |
| `admin_id` | Text | Nullable (null for leader-initiated actions) |
| `action` | Text | CHECK: CREATED/PROOF_SUBMITTED/VERIFIED/REJECTED/REOPENED |
| `old_status` | Text | |
| `new_status` | Text | |
| `reason` | Text | For REJECTED |
| `details` | JSONB | Additional metadata |
| `created_at` | DateTime(tz) | |

### `events` and `event_slots` (reference tables, seeded)
- `event_slots`: 3 rows -- id 1 (label "1"), id 2 (label "2"), id 3 (label "BOTH").
- `events`: 8 rows seeded from `EVENT_SLOT_MAP` in constants.

---

## 8. KEY ASSUMPTIONS AND INVARIANTS

### Team Size and Payment Calculation
- **Fee is per unique student, not per team or per event.** Rs.200 per student.
- A student in 2 events still pays Rs.200 once (same register number = same student).
- A leader with 15 students pays Rs.3000 maximum (15 * 200).
- Adding a student to a second event does NOT increase the fee (the student already exists).
- The fee is recalculated on every `/registerteam` and `/payments/mine` call.

### Registration Model
- One leader has at most 15 students (across all events).
- Each student can be in at most 2 events (event1 + event2).
- Each student can only be in events from different time slots (slot 1 and slot 2).
- Bid Mayhem occupies BOTH slots and is mutually exclusive with all other events.
- One team per event per leader (no duplicate registrations for the same event).
- `foodPreference` is captured once at student creation and never overwritten.

### Payment Model
- One payment row per leader (UNIQUE on `leader_id`).
- Payment row is created on first `/registerteam` call and updated on subsequent calls.
- Amount mismatch between expected and submitted is NOT rejected -- it is flagged for admin manual review.
- UTR is trimmed, uppercased, and globally unique across all payments.
- Proof files are content-sniffed (not trusted by extension alone), size-capped, and stored privately.

### Transactional Safety
- All registration + payment changes happen within a single async session transaction.
- The `get_db` dependency commits on success and rolls back on any exception.
- Payment upsert uses `begin_nested()` (SAVEPOINT) to handle concurrent first-registrations without aborting the outer transaction.
- All status transitions use guarded UPDATEs with `WHERE status = <expected>` -- rowcount 0 means concurrent modification, not a silent overwrite.

### Authentication Boundaries
- Leaders authenticate with JWT (`role: "user"`), access their own data only (enforced by `leaderId` match).
- Admins authenticate with JWT (`role: "admin"`), with `adminRole: 1` (Super Admin) or `adminRole: 2` (Moderator).
- Payment admin endpoints are Super Admin only. View/delete team endpoints allow moderators.
- Health check is rate-limit exempt.
</task_result>
</task>
```

---

## Assistant (Plan · MiMo V2.5 Free · 7.5s)

_Thinking:_

Now I have a good understanding of the codebase. Let me also look at the specific registration service to understand the blocking mechanism the user is referring to.

Let me check the specific blocking mechanism for event registrations and the payment flow more closely.

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\services\\registration_sqla.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\services\registration_sqla.py</path>
<type>file</type>
<content>
1: import re
2: 
3: from sqlalchemy import select
4: from sqlalchemy.ext.asyncio import AsyncSession
5: 
6: from app.exceptions.api_error import APIError
7: from app.models_sqla.event import Event, EventSlot
8: from app.models_sqla.event_registration import EventRegistration
9: from app.utils.constants import FOOD_PREFERENCES, MAX_STUDENTS_PER_LEADER
10: from app.utils.validators import clean_participant_mobile
11: 
12: _PARTICIPANT_MOBILE = re.compile(r"^[6-9]\d{9}$")
13: 
14: 
15: async def _resolve_event(session: AsyncSession, event_name: str) -> tuple[Event, EventSlot]:
16:     stmt = (
17:         select(Event, EventSlot)
18:         .join(EventSlot, Event.slot_id == EventSlot.id)
19:         .where(Event.name == event_name)
20:     )
21:     result = await session.execute(stmt)
22:     row = result.first()
23:     if row is None:
24:         raise APIError(400, "Invalid event selected")
25:     return row[0], row[1]
26: 
27: 
28: async def register_team(
29:     session: AsyncSession,
30:     event_regs,  # EventRegistrationRepositorySqla, shares the same session
31:     *,
32:     leader_id: str,
33:     event: str,
34:     participants: list,
35:     college: str,
36:     department: str,
37: ) -> dict:
38:     """Register/update a team in one transaction (Postgres).
39: 
40:     The Mongo version used manual compensation on failure; with a real
41:     transactional backend we let the surrounding AsyncSession rollback on
42:     any exception. Returns ``{"created": n, "updated": n}``.
43:     """
44:     srv_event, srv_slot = await _resolve_event(session, event)
45:     slot_label = srv_slot.slot_label
46: 
47:     # One team per event per leader.
48:     if await event_regs.find_leader_event(leader_id, event):
49:         raise APIError(
50:             409,
51:             f"Your team is already registered for {event}. Only one team per event is allowed.",
52:         )
53: 
54:     reg_numbers = [(p.registerNumber or "").upper() for p in participants]
55: 
56:     seen: set[str] = set()
57:     for reg_number in reg_numbers:
58:         if reg_number in seen:
59:             raise APIError(400, f"Duplicate register numbers in team: {reg_number}")
60:         seen.add(reg_number)
61: 
62:     existing_docs = await event_regs.find_team_by_register_numbers(leader_id, reg_numbers)
63:     existing_reg_set = {doc["registerNumber"] for doc in existing_docs}
64: 
65:     for participant in participants:
66:         is_existing = (participant.registerNumber or "").upper() in existing_reg_set
67: 
68:         if not participant.name or not participant.registerNumber or not participant.mobile or not participant.degree:
69:             raise APIError(
70:                 400,
71:                 "Incomplete data for a participant. name, registerNumber, mobile and degree are all required.",
72:             )
73: 
74:         if not _PARTICIPANT_MOBILE.match(clean_participant_mobile(participant.mobile)):
75:             raise APIError(
76:                 400,
77:                 f"Invalid mobile number for {participant.name}. Must be 10 digits starting with 6-9.",
78:             )
79: 
80:         if participant.foodPreference and participant.foodPreference not in FOOD_PREFERENCES:
81:             raise APIError(
82:                 400,
83:                 f"Invalid food preference for {participant.name}. Must be vegetarian or non-vegetarian.",
84:             )
85: 
86:         if not is_existing:
87:             if not participant.foodPreference:
88:                 raise APIError(400, f"Food preference is required for new participant {participant.name}.")
89: 
90:     current_student_count = await event_regs.count_by_leader(leader_id)
91:     new_student_count = sum(1 for r in reg_numbers if r not in existing_reg_set)
92:     if current_student_count + new_student_count > MAX_STUDENTS_PER_LEADER:
93:         raise APIError(
94:             409,
95:             f"This would exceed the 15-student limit. Current: {current_student_count}, new in this team: {new_student_count}.",
96:         )
97: 
98:     for doc in existing_docs:
99:         if doc.get("event2") == "Bid Mayhem" or doc.get("event1") == "Bid Mayhem":
100:             raise APIError(
101:                 409,
102:                 f"{doc['name']} ({doc['registerNumber']}) is in Bid Mayhem and cannot register for other events.",
103:             )
104:         if slot_label == "BOTH" and doc.get("event1"):
105:             raise APIError(
106:                 409,
107:                 f"{doc['name']} ({doc['registerNumber']}) already has events. Bid Mayhem cannot be combined.",
108:             )
109:         if doc.get("event2") is not None:
110:             raise APIError(
111:                 409,
112:                 f"{doc['name']} ({doc['registerNumber']}) is already in 2 events: {doc['event1']} & {doc['event2']}.",
113:             )
114:         if doc.get("slot1") == slot_label:
115:             raise APIError(
116:                 409,
117:                 f"{doc['name']} ({doc['registerNumber']}) already has {doc['event1']} in the same time slot.",
118:             )
119: 
120:     created = 0
121:     updated = 0
122: 
123:     for participant in participants:
124:         reg_upper = participant.registerNumber.upper()
125:         clean_mobile = clean_participant_mobile(participant.mobile)
126:         existing = next((d for d in existing_docs if d["registerNumber"] == reg_upper), None)
127: 
128:         if existing:
129:             stmt = (
130:                 select(EventRegistration)
131:                 .where(EventRegistration.id == existing["_id"])
132:             )
133:             obj = (await session.execute(stmt)).scalars().first()
134:             obj.event2_id = srv_event.id
135:             obj.slot2_id = srv_slot.id
136:             await session.flush()
137:             updated += 1
138:         else:
139:             new_obj = EventRegistration(
140:                 leader_id=leader_id,
141:                 name=participant.name,
142:                 register_number=reg_upper,
143:                 mobile=clean_mobile,
144:                 college_name_text=college,
145:                 department=department,
146:                 degree=participant.degree,
147:                 food_preference=participant.foodPreference,
148:                 event1_id=srv_event.id,
149:                 slot1_id=srv_slot.id,
150:                 status="PAYMENT_PENDING",
151:             )
152:             session.add(new_obj)
153:             await session.flush()
154:             created += 1
155: 
156:     return {"created": created, "updated": updated}

(End of file - total 156 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\services\\payment_sqla.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\services\payment_sqla.py</path>
<type>file</type>
<content>
1: """Payment workflow business logic.
2: 
3: All state transitions are guarded single-session operations -- the FastAPI
4: get_db dependency commits on success and rolls back on any exception, so
5: payment + registration status changes are atomic.
6: 
7: Status machines:
8:   payments.payment_status:
9:     PENDING -> VERIFICATION_PENDING -> SUCCESS
10:     VERIFICATION_PENDING -> REJECTED -> (resubmit) -> VERIFICATION_PENDING
11:     REJECTED -> (reopen, Super Admin) -> VERIFICATION_PENDING
12:   event_registrations.status mirrors the payment for the leader's rows.
13: """
14: import io
15: import re
16: import uuid
17: 
18: from fastapi import UploadFile
19: from PIL import Image, UnidentifiedImageError
20: from sqlalchemy.exc import IntegrityError
21: from sqlalchemy.ext.asyncio import AsyncSession
22: 
23: from app.config.settings import settings
24: from app.exceptions.api_error import APIError
25: from app.repositories_sqla import (
26:     EventRegistrationRepositorySqla,
27:     PaymentRepositorySqla,
28: )
29: from app.services.fees import calculate_registration_fee, normalize_utr
30: from app.storage.proof_storage import ProofStorageError, get_proof_storage
31: from app.utils.constants import ALLOWED_PROOF_FORMATS, PAYMENT_LOCKED_STATUSES
32: 
33: _UTR_RE = re.compile(r"^[A-Za-z0-9]{8,22}$")
34: 
35: 
36: async def ensure_payment_for_registration(
37:     session: AsyncSession,
38:     payments: PaymentRepositorySqla,
39:     leader_id: str,
40:     expected_paises: int,
41:     unique_count: int,
42: ) -> dict:
43:     """Create-or-refresh the leader's single payment row after /registerteam.
44: 
45:     Race-safe via SAVEPOINT: two concurrent first-registrations for the same
46:     leader cannot both INSERT (UNIQUE leader_id); the loser updates instead.
47:     """
48:     existing = await payments.find_by_leader(leader_id)
49:     if existing is None:
50:         try:
51:             async with session.begin_nested():
52:                 await payments.insert_pending(leader_id, expected_paises)
53:         except IntegrityError:
54:             pass
55:         existing = await payments.find_by_leader(leader_id)
56:         if existing is not None and existing["paymentStatus"] == "PENDING" and existing["submittedAmountPaises"] is None:
57:             await payments.insert_audit(
58:                 existing["_id"],
59:                 admin_id=None,
60:                 action="CREATED",
61:                 old_status=None,
62:                 new_status="PENDING",
63:                 details={
64:                     "expectedAmountPaises": expected_paises,
65:                     "uniqueStudents": unique_count,
66:                 },
67:             )
68:             return existing
69:     await payments.update_expected_amount(leader_id, expected_paises)
70:     return await payments.find_by_leader(leader_id)
71: 
72: 
73: def assert_team_edits_allowed(payment: dict | None) -> None:
74:     """409 when team edits are locked (proof submitted or verified)."""
75:     if payment and payment["paymentStatus"] in PAYMENT_LOCKED_STATUSES:
76:         raise APIError(
77:             409,
78:             "Team changes are locked while your payment is under review or "
79:             "confirmed. Contact an organizer for modifications.",
80:         )
81: 
82: 
83: def _validate_proof_file(data: bytes, filename: str) -> tuple[str, str]:
84:     """Sniff actual image content via Pillow. Returns (ext, mime). Raises 400."""
85:     max_bytes = settings.PROOF_MAX_MB * 1024 * 1024
86:     if len(data) == 0:
87:         raise APIError(400, "Payment screenshot is empty")
88:     if len(data) > max_bytes:
89:         raise APIError(
90:             400, f"Screenshot must be {settings.PROOF_MAX_MB} MB or smaller"
91:         )
92: 
93:     fmt = None
94:     try:
95:         with Image.open(io.BytesIO(data)) as img:
96:             fmt = img.format
97:     except UnidentifiedImageError:
98:         pass
99:     except Exception:
100:         pass
101: 
102:     ext = ALLOWED_PROOF_FORMATS.get(fmt or "")
103:     if ext is None:
104:         raise APIError(
105:             400,
106:             "Unsupported file type. Upload a JPG, PNG or WebP screenshot "
107:             f"({settings.PROOF_MAX_MB} MB max).",
108:         )
109: 
110:     mime = {
111:         ".jpg": "image/jpeg",
112:         ".png": "image/png",
113:         ".webp": "image/webp",
114:     }[ext]
115:     return ext, mime
116: 
117: 
118: async def submit_payment_proof(
119:     session: AsyncSession,
120:     payments: PaymentRepositorySqla,
121:     event_regs: EventRegistrationRepositorySqla,
122:     *,
123:     leader_id: str,
124:     utr_raw: str | None,
125:     amount_paises: int | None,
126:     screenshot: UploadFile | None,
127: ) -> dict:
128:     """Validate + store proof, transition payment/registrations atomically."""
129:     payment = await payments.find_by_leader(leader_id)
130:     if payment is None:
131:         raise APIError(404, "No registration found. Register your team first.")
132: 
133:     status = payment["paymentStatus"]
134:     normalized_utr = normalize_utr(utr_raw)
135: 
136:     if status == "VERIFICATION_PENDING" and normalized_utr == payment["utr"]:
137:         # Idempotent retry of the same submission (double click / network retry).
138:         return payment
139:     if status == "SUCCESS":
140:         raise APIError(409, "Payment is already verified.")
141:     if status not in ("PENDING", "REJECTED"):
142:         raise APIError(409, "A different payment proof is already under review.")
143: 
144:     if not utr_raw or not utr_raw.strip():
145:         raise APIError(400, "UTR / transaction reference is required")
146:     if not _UTR_RE.match(normalized_utr):
147:         raise APIError(400, "UTR must be 8-22 letters or digits with no spaces")
148: 
149:     if amount_paises is None or amount_paises <= 0:
150:         raise APIError(400, "Submitted amount is required")
151:     # Amount mismatch is NOT rejected here — it is stored as-is and flagged
152:     # for manual review. Admins see Expected vs Submitted vs Difference.
153:     # A screenshot/UTR alone can never mark a payment successful.
154: 
155:     if screenshot is None or screenshot.filename is None:
156:         raise APIError(400, "Payment screenshot is required")
157:     data = await screenshot.read()
158:     original_name = screenshot.filename
159:     try:
160:         ext, mime = _validate_proof_file(data, original_name)
161:     except APIError:
162:         await screenshot.close()
163:         raise
164: 
165:     storage = get_proof_storage()
166:     key = f"payment-proofs/{leader_id}/{payment['_id']}/{uuid.uuid4().hex}{ext}"
167: 
168:     try:
169:         storage.save(key, data, mime)
170:     except ProofStorageError as exc:
171:         raise APIError(500, f"Failed to store payment proof: {exc}")
172: 
173:     try:
174:         try:
175:             async with session.begin_nested():
176:                 rowcount = await payments.submit_proof_update(
177:                     payment["_id"],
178:                     from_statuses=("PENDING", "REJECTED"),
179:                     utr=normalized_utr,
180:                     submitted_amount_paises=amount_paises,
181:                     proof_object_key=key,
182:                     proof_original_filename=original_name,
183:                     proof_mime_type=mime,
184:                     proof_file_size=len(data),
185:                 )
186:         except IntegrityError:
187:             storage.delete(key)
188:             raise APIError(
189:                 409, "This UTR / transaction reference has already been used."
190:             )
191:         if rowcount == 0:
192:             raise APIError(409, "A different payment proof is already under review.")
193: 
194:         await event_regs.update_status_by_leader(
195:             leader_id,
196:             "VERIFICATION_PENDING",
197:             from_statuses=("PAYMENT_PENDING",),
198:         )
199:         await payments.insert_audit(
200:             payment["_id"],
201:             admin_id=None,
202:             action="PROOF_SUBMITTED",
203:             old_status=status,
204:             new_status="VERIFICATION_PENDING",
205:             details={
206:                 "utr": normalized_utr,
207:                 "submittedAmountPaises": amount_paises,
208:                 "expectedAmountPaises": payment["expectedAmountPaises"],
209:             },
210:         )
211:     except APIError:
212:         storage.delete(key)
213:         raise
214:     except Exception:
215:         storage.delete(key)
216:         raise
217: 
218:     return await payments.find_by_leader(leader_id)
219: 
220: 
221: async def verify_payment(
222:     session: AsyncSession,
223:     payments: PaymentRepositorySqla,
224:     event_regs: EventRegistrationRepositorySqla,
225:     *,
226:     payment_id: int,
227:     admin_id: str,
228: ) -> dict:
229:     payment = await payments.find_by_id(payment_id)
230:     if payment is None:
231:         raise APIError(404, "Payment not found")
232:     if payment["paymentStatus"] != "VERIFICATION_PENDING":
233:         raise APIError(
234:             409,
235:             f"Only payments in VERIFICATION_PENDING can be verified "
236:             f"(current: {payment['paymentStatus']}).",
237:         )
238: 
239:     rowcount = await payments.mark_verified(payment_id, admin_id)
240:     if rowcount == 0:
241:         raise APIError(409, "Payment status changed concurrently. Retry.")
242: 
243:     updated_regs = await event_regs.update_status_by_leader(
244:         payment["leaderId"], "CONFIRMED", from_statuses=("VERIFICATION_PENDING",)
245:     )
246:     await payments.insert_audit(
247:         payment_id,
248:         admin_id=admin_id,
249:         action="VERIFIED",
250:         old_status="VERIFICATION_PENDING",
251:         new_status="SUCCESS",
252:     )
253:     result = await payments.find_by_id(payment_id)
254:     if result is not None:
255:         result["confirmedRegistrations"] = updated_regs
256:     return result
257: 
258: 
259: async def reject_payment(
260:     session: AsyncSession,
261:     payments: PaymentRepositorySqla,
262:     event_regs: EventRegistrationRepositorySqla,
263:     *,
264:     payment_id: int,
265:     admin_id: str,
266:     reason: str,
267: ) -> dict:
268:     payment = await payments.find_by_id(payment_id)
269:     if payment is None:
270:         raise APIError(404, "Payment not found")
271:     if payment["paymentStatus"] != "VERIFICATION_PENDING":
272:         raise APIError(
273:             409,
274:             f"Only payments in VERIFICATION_PENDING can be rejected "
275:             f"(current: {payment['paymentStatus']}).",
276:         )
277: 
278:     rowcount = await payments.mark_rejected(payment_id, reason.strip())
279:     if rowcount == 0:
280:         raise APIError(409, "Payment status changed concurrently. Retry.")
281: 
282:     reverted = await event_regs.update_status_by_leader(
283:         payment["leaderId"], "PAYMENT_PENDING", from_statuses=("VERIFICATION_PENDING",)
284:     )
285:     await payments.insert_audit(
286:         payment_id,
287:         admin_id=admin_id,
288:         action="REJECTED",
289:         old_status="VERIFICATION_PENDING",
290:         new_status="REJECTED",
291:         reason=reason.strip(),
292:     )
293:     result = await payments.find_by_id(payment_id)
294:     if result is not None:
295:         result["revertedRegistrations"] = reverted
296:     return result
297: 
298: 
299: async def reopen_payment(
300:     session: AsyncSession,
301:     payments: PaymentRepositorySqla,
302:     event_regs: EventRegistrationRepositorySqla,
303:     *,
304:     payment_id: int,
305:     admin_id: str,
306: ) -> dict:
307:     payment = await payments.find_by_id(payment_id)
308:     if payment is None:
309:         raise APIError(404, "Payment not found")
310:     if payment["paymentStatus"] != "REJECTED":
311:         raise APIError(
312:             409,
313:             f"Only REJECTED payments can be reopened (current: {payment['paymentStatus']}).",
314:         )
315: 
316:     rowcount = await payments.reopen(payment_id)
317:     if rowcount == 0:
318:         raise APIError(409, "Payment status changed concurrently. Retry.")
319: 
320:     promoted = await event_regs.update_status_by_leader(
321:         payment["leaderId"], "VERIFICATION_PENDING", from_statuses=("PAYMENT_PENDING",)
322:     )
323:     await payments.insert_audit(
324:         payment_id,
325:         admin_id=admin_id,
326:         action="REOPENED",
327:         old_status="REJECTED",
328:         new_status="VERIFICATION_PENDING",
329:     )
330:     result = await payments.find_by_id(payment_id)
331:     if result is not None:
332:         result["promotedRegistrations"] = promoted
333:     return result
334: 
335: 
336: def build_payment_summary(payment: dict | None, upi_uri: str | None) -> dict:
337:     """Leader-facing summary shape used by /payments/mine."""
338:     if payment is None:
339:         return {"payment": None, "upiUri": upi_uri}
340:     allowed = {
341:         "paymentId",
342:         "leaderId",
343:         "expectedAmountPaises",
344:         "submittedAmountPaises",
345:         "currency",
346:         "utr",
347:         "paymentStatus",
348:         "submittedAt",
349:         "verifiedAt",
350:         "rejectionReason",
351:     }
352:     return {
353:         "payment": {k: v for k, v in payment.items() if k in allowed},
354:         "upiUri": upi_uri,
355:     }

(End of file - total 355 lines)
</content>
```

---

## Assistant (Plan · MiMo V2.5 Free · 12.3s)

_Thinking:_

Now let me also check the fees calculation and the constants for more context on the payment and team size logic.

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\services\\fees.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\services\fees.py</path>
<type>file</type>
<content>
1: """Registration fee calculation — single source of truth.
2: 
3: Money is handled exclusively as integer paise. The backend is the only
4: authority for the unique student count and the payable amount; frontend
5: values are informational only and never trusted.
6: """
7: import re
8: from urllib.parse import urlencode
9: 
10: from app.config.settings import settings
11: from app.utils.constants import CURRENCY
12: 
13: UTR_REGEX = re.compile(r"^[A-Za-z0-9]{8,22}$")
14: 
15: 
16: def calculate_registration_fee(unique_student_count: int) -> int:
17:     """Flat per-unique-student fee, integer paise (Rs.200 default)."""
18:     if unique_student_count < 0:
19:         raise ValueError("unique_student_count must be >= 0")
20:     return unique_student_count * settings.REGISTRATION_FEE_PER_STUDENT_PAISE
21: 
22: 
23: def paise_to_rupee_string(amount_paises: int) -> str:
24:     sign = "-" if amount_paises < 0 else ""
25:     amount_paises = abs(int(amount_paises))
26:     return f"{sign}{amount_paises // 100}.{amount_paises % 100:02d}"
27: 
28: 
29: def normalize_utr(utr: str | None) -> str | None:
30:     if utr is None:
31:         return None
32:     return utr.strip().upper() or None
33: 
34: 
35: def validate_utr(utr: str | None) -> str | None:
36:     """Return an error message for invalid UTRs, or None when valid."""
37:     normalized = normalize_utr(utr)
38:     if not normalized:
39:         return "UTR / transaction reference is required"
40:     if not UTR_REGEX.match(normalized):
41:         return "UTR must be 8-22 letters or digits with no spaces"
42:     return None
43: 
44: 
45: def build_upi_uri(leader_id: str, amount_paises: int) -> str | None:
46:     """Compose the UPI intent URI for the payment dialog's QR code.
47: 
48:     Returns None when UPI_VPA is not configured; the UI falls back to
49:     copyable text instructions in that case.
50:     """
51:     if not settings.UPI_VPA:
52:         return None
53:     params = {
54:         "pa": settings.UPI_VPA,
55:         "pn": settings.UPI_PAYEE_NAME or "AION 2K26",
56:         "am": paise_to_rupee_string(amount_paises),
57:         "tn": f"AION2K26-{leader_id}",
58:         "cu": CURRENCY,
59:     }
60:     return "upi://pay?" + urlencode(params)

(End of file - total 60 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\utils\\constants.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\utils\constants.py</path>
<type>file</type>
<content>
1: DEPARTMENTS = ["cs", "it", "ai", "ds", "ca"]
2: DEGREES = ["ug", "pg"]
3: SLOTS = ["1", "2", "BOTH"]
4: SHIFTS = ["1", "2"]
5: FOOD_PREFERENCES = ["vegetarian", "non-vegetarian"]
6: 
7: EVENT_SLOT_MAP = {
8:     "Fixathon": "1",
9:     "Mute Masters": "1",
10:     "Treasure Titans": "1",
11:     "Bid Mayhem": "BOTH",
12:     "QRush": "2",
13:     "VisionX": "2",
14:     "ThinkSync": "2",
15:     "Crazy Sell": "2",
16: }
17: 
18: EVENTS = [
19:     "Fixathon",
20:     "Mute Masters",
21:     "Treasure Titans",
22:     "VisionX",
23:     "QRush",
24:     "ThinkSync",
25:     "Bid Mayhem",
26:     "Crazy Sell",
27: ]
28: 
29: MAX_STUDENTS_PER_LEADER = 15
30: 
31: REGISTRATION_STATUSES = [
32:     "PAYMENT_PENDING",
33:     "VERIFICATION_PENDING",
34:     "CONFIRMED",
35:     "REJECTED",
36: ]
37: 
38: PAYMENT_STATUSES = ["PENDING", "VERIFICATION_PENDING", "SUCCESS", "REJECTED"]
39: 
40: PAYMENT_AUDIT_ACTIONS = [
41:     "CREATED",
42:     "PROOF_SUBMITTED",
43:     "VERIFIED",
44:     "REJECTED",
45:     "REOPENED",
46: ]
47: 
48: CURRENCY = "INR"
49: 
50: PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")
51: 
52: ALLOWED_PROOF_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

(End of file - total 52 lines)
</content>
```

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\api\\auth.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\api\auth.py</path>
<type>file</type>
<content>
1: import secrets
2: import time
3: 
4: from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
5: from sqlalchemy.exc import IntegrityError
6: 
7: from app.auth.dependencies import get_current_super_admin, get_current_user
8: from app.auth.security import create_access_token, hash_password, verify_password
9: from app.config.settings import settings
10: from app.dependencies.db import AsyncSessionDep
11: from app.dependencies.repositories import (
12:     get_college_repo,
13:     get_event_regs_repo,
14:     get_payment_repo,
15:     get_user_repo,
16: )
17: from app.exceptions.api_error import APIError
18: from app.middleware.rate_limit import limiter
19: from app.repositories_sqla import (
20:     CollegeRepositorySqla,
21:     EventRegistrationRepositorySqla,
22:     PaymentRepositorySqla,
23:     UserRepositorySqla,
24: )
25: from app.schemas.auth import (
26:     AddCollegeResponse,
27:     GetCandidatesRequest,
28:     GetCandidatesResponse,
29:     GetCollegeResponse,
30:     LeaderLoginRequest,
31:     LeaderLoginResponse,
32:     LeaderRegisterRequest,
33:     LeaderRegisterResponse,
34:     RegisterTeamRequest,
35:     RegisterTeamResponse,
36:     StatsResponse,
37: )
38: from app.schemas.common import success
39: from app.schemas.payment import MyPaymentsResponse, SubmitProofResponse
40: from app.services.fees import build_upi_uri, calculate_registration_fee
41: from app.services.payment_sqla import (
42:     assert_team_edits_allowed,
43:     build_payment_summary,
44:     ensure_payment_for_registration,
45:     submit_payment_proof,
46: )
47: from app.services.registration_sqla import register_team
48: from app.utils.constants import CURRENCY
49: from app.utils.serializers import sanitize
50: from app.utils.validators import clean_mobile_number
51: 
52: router = APIRouter()
53: 
54: 
55: async def _generate_leader_id(users: UserRepositorySqla) -> str:
56:     while True:
57:         candidate = f"LD{int(time.time() * 1000)}{secrets.randbelow(1000)}"
58:         if not await users.find_by_userid(candidate):
59:             return candidate
60: 
61: 
62: @router.post("/regleader", status_code=201, response_model=LeaderRegisterResponse)
63: async def register_leader(
64:     payload: LeaderRegisterRequest,
65:     session: AsyncSessionDep,
66:     users: UserRepositorySqla = Depends(get_user_repo),
67:     colleges: CollegeRepositorySqla = Depends(get_college_repo),
68: ):
69:     normalized_email = payload.email.strip().lower()
70:     if await users.find_by_email(normalized_email):
71:         raise APIError(400, "Email already registered")
72: 
73:     clean_mobile = clean_mobile_number(payload.mobilenumber)
74:     if await users.find_by_mobile(clean_mobile):
75:         raise APIError(400, "Mobile number already registered")
76: 
77:     if await users.find_leader_slot_conflict(
78:         payload.college.strip(), payload.department.strip(), payload.shift.strip()
79:     ):
80:         raise APIError(400, "Leader already exists for this College, Department and Shift")
81: 
82:     leader_id = await _generate_leader_id(users)
83: 
84:     try:
85:         await users.insert(
86:             {
87:                 "userid": leader_id,
88:                 "name": payload.name.strip(),
89:                 "email": normalized_email,
90:                 "mobilenumber": clean_mobile,
91:                 "department": payload.department.strip(),
92:                 "college": payload.college.strip(),
93:                 "shift": payload.shift.strip(),
94:                 "password": hash_password(payload.password),
95:             }
96:         )
97:         await session.flush()
98:     except IntegrityError:
99:         raise APIError(400, "Registration failed. Email or mobile number is already registered.")
100: 
101:     await colleges.mark_registered(payload.college.strip())
102: 
103:     return success("Leader registered successfully", userid=leader_id)
104: 
105: 
106: @router.post("/loginleader", response_model=LeaderLoginResponse)
107: @limiter.limit(settings.RATE_LIMIT_LOGIN)
108: async def login_leader(
109:     request: Request,
110:     payload: LeaderLoginRequest,
111:     users: UserRepositorySqla = Depends(get_user_repo),
112: ):
113:     normalized_email = payload.email.strip().lower()
114:     user = await users.find_by_email(normalized_email)
115:     if not user or not verify_password(payload.password, user["password"]):
116:         raise APIError(401, "Invalid Email or Password")
117: 
118:     token = create_access_token(
119:         {"userid": user["userid"], "email": user["email"], "name": user["name"], "role": "user"}
120:     )
121:     return success("Login successful", userid=user["userid"], name=user["name"], token=token)
122: 
123: 
124: @router.post("/registerteam", response_model=RegisterTeamResponse)
125: async def register_team_route(
126:     payload: RegisterTeamRequest,
127:     session: AsyncSessionDep,
128:     current_user: dict = Depends(get_current_user),
129:     users: UserRepositorySqla = Depends(get_user_repo),
130:     event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
131:     payments: PaymentRepositorySqla = Depends(get_payment_repo),
132: ):
133:     if payload.leaderId != current_user["userid"]:
134:         raise APIError(403, "Access denied. Leader ID mismatch.")
135: 
136:     leader = await users.find_by_userid(payload.leaderId)
137:     if not leader:
138:         raise APIError(404, "Leader not found")
139: 
140:     college = leader.get("college")
141:     department = leader.get("department")
142:     if not college or not department:
143:         raise APIError(400, "Leader profile incomplete. Missing college or department.")
144: 
145:     assert_team_edits_allowed(await payments.find_by_leader(payload.leaderId))
146: 
147:     result = await register_team(
148:         session,
149:         event_regs,
150:         leader_id=payload.leaderId,
151:         event=payload.event,
152:         participants=payload.participants,
153:         college=college,
154:         department=department,
155:     )
156: 
157:     unique_count = await event_regs.count_distinct_students(payload.leaderId)
158:     amount_due = calculate_registration_fee(unique_count)
159:     await ensure_payment_for_registration(
160:         session, payments, payload.leaderId, amount_due, unique_count
161:     )
162:     payment = await payments.find_by_leader(payload.leaderId)
163: 
164:     return success(
165:         f"Team of {len(payload.participants)} registered for {payload.event}.",
166:         created=result["created"],
167:         updated=result["updated"],
168:         uniqueStudents=unique_count,
169:         amountDuePaises=amount_due,
170:         currency=CURRENCY,
171:         upiUri=build_upi_uri(payload.leaderId, amount_due),
172:         paymentStatus=payment["paymentStatus"] if payment else "PENDING",
173:     )
174: 
175: 
176: @router.get("/payments/mine", response_model=MyPaymentsResponse)
177: async def my_payments(
178:     current_user: dict = Depends(get_current_user),
179:     event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
180:     payments: PaymentRepositorySqla = Depends(get_payment_repo),
181: ):
182:     leader_id = current_user["userid"]
183:     unique_count = await event_regs.count_distinct_students(leader_id)
184:     amount_due = calculate_registration_fee(unique_count)
185:     payment = await payments.find_by_leader(leader_id)
186:     summary = build_payment_summary(payment, build_upi_uri(leader_id, amount_due))
187:     return success(
188:         "Payment details fetched successfully",
189:         uniqueStudents=unique_count,
190:         amountDuePaises=payment["expectedAmountPaises"] if payment else amount_due,
191:         upiUri=summary["upiUri"],
192:         data=sanitize(summary["payment"]),
193:     )
194: 
195: 
196: @router.post("/payments/proof", response_model=SubmitProofResponse)
197: async def submit_proof_route(
198:     session: AsyncSessionDep,
199:     screenshot: UploadFile | None = File(None),
200:     utr: str | None = Form(None),
201:     amountPaises: int | None = Form(None),
202:     current_user: dict = Depends(get_current_user),
203:     event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
204:     payments: PaymentRepositorySqla = Depends(get_payment_repo),
205: ):
206:     payment = await submit_payment_proof(
207:         session,
208:         payments,
209:         event_regs,
210:         leader_id=current_user["userid"],
211:         utr_raw=utr,
212:         amount_paises=amountPaises,
213:         screenshot=screenshot,
214:     )
215:     return success("Payment proof submitted for verification",
216:                    paymentId=payment["paymentId"],
217:                    paymentStatus=payment["paymentStatus"])
218: 
219: 
220: @router.post("/getcandidates", response_model=GetCandidatesResponse)
221: async def get_candidates(
222:     payload: GetCandidatesRequest,
223:     current_user: dict = Depends(get_current_user),
224:     event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
225: ):
226:     if not payload.user_id:
227:         raise APIError(400, "User ID required")
228:     if payload.user_id != current_user["userid"]:
229:         raise APIError(403, "Access denied. User ID mismatch.")
230: 
231:     students = await event_regs.find_by_leader(payload.user_id)
232: 
233:     registered_events: set[str] = set()
234:     for student in students:
235:         if student.get("event1"):
236:             registered_events.add(student["event1"])
237:         if student.get("event2"):
238:             registered_events.add(student["event2"])
239: 
240:     return success(
241:         "Candidates fetched successfully",
242:         totalStudents=len(students),
243:         registeredEvents=list(registered_events),
244:         data=sanitize(students),
245:     )
246: 
247: 
248: @router.get("/stats/{leader_id}", response_model=StatsResponse)
249: async def get_stats(
250:     leader_id: str,
251:     current_user: dict = Depends(get_current_user),
252:     event_regs: EventRegistrationRepositorySqla = Depends(get_event_regs_repo),
253: ):
254:     if leader_id != current_user["userid"]:
255:         raise APIError(403, "Access denied. Leader ID mismatch.")
256: 
257:     students = await event_regs.find_by_leader(leader_id)
258: 
259:     registered_events: set[str] = set()
260:     for student in students:
261:         if student.get("event1"):
262:             registered_events.add(student["event1"])
263:         if student.get("event2"):
264:             registered_events.add(student["event2"])
265: 
266:     return success(
267:         "Stats fetched successfully",
268:         stats={
269:             "totalStudents": len(students),
270:             "studentsRemaining": 15 - len(students),
271:             "eventsRegistered": len(registered_events),
272:             "registeredEvents": list(registered_events),
273:         },
274:     )
275: 
276: 
277: @router.post("/addcollege", status_code=201, response_model=AddCollegeResponse)
278: async def add_college(
279:     colleges: list[dict],
280:     current_admin: dict = Depends(get_current_super_admin),
281:     colleges_repo: CollegeRepositorySqla = Depends(get_college_repo),
282: ):
283:     if not colleges:
284:         raise APIError(400, "Send array of colleges")
285: 
286:     for college in colleges:
287:         if not college.get("collegeId") or not college.get("name"):
288:             raise APIError(400, "Each college must have collegeId and name")
289: 
290:     inserted = await colleges_repo.insert_many(colleges)
291:     if inserted == 0:
292:         raise APIError(400, "No colleges were added. Duplicate collegeId values detected.")
293: 
294:     return success("Colleges added successfully", count=inserted)
295: 
296: 
297: @router.get("/getcollege", response_model=GetCollegeResponse)
298: async def get_college(colleges_repo: CollegeRepositorySqla = Depends(get_college_repo)):
299:     colleges = await colleges_repo.find_all()
300:     return success("Colleges fetched successfully", data=sanitize(colleges))

(End of file - total 300 lines)
</content>
```

---

## Assistant (Plan · MiMo V2.5 Free · 26.1s)

_Thinking:_

Now I have a thorough understanding of the codebase. Let me analyze the user's question and the current architecture to provide a comprehensive plan.

Let me summarize the current flow:

### Current Architecture:
1. **Registration Flow**: Leader registers team for an event → students get `PAYMENT_PENDING` status
2. **Payment**: One payment row per leader. Fee = Rs.200 × unique students. Leader submits proof (UTR + screenshot)
3. **Team Edits Lock**: Once payment is in `VERIFICATION_PENDING` or `SUCCESS`, team edits are **blocked** (line 73-80 in payment_sqla.py)
4. **Admin Verification**: Super Admin verifies/rejects the single payment. All leader's registrations flip at once.

### What the user is saying:
- Currently, the `assert_team_edits_allowed` blocks ALL team modifications once payment is submitted (VERIFICATION_PENDING or SUCCESS)
- This means if a leader submits payment after registering 10 students, they CANNOT add the remaining 5 students until admin verifies
- The user wants:
  - One bulk payment per team (already the case)
  - After payment verification, if the team hasn't reached 15 members, allow them to expand to other events
  - But the blocking currently prevents this

### The user's dilemma:
**Option 1 (Current)**: Block all event registrations after payment → Admin verifies once → But team can't grow after verification

**Option 2**: Allow team registrations even after payment → But admin has to verify UPI proofs for each event individually → Tedious

**User's preferred approach**: 
1. Leader builds team (all events)
2. One bulk payment
3. Admin verifies once
4. After verification, if team < 15, allow adding more students to events### Key Questions to Resolve:
1. After payment is SUCCESS, should we allow adding new students to the SAME events the team is already in? Or only to NEW events?
2. If new students are added after payment is SUCCESS, should the fee automatically increase? Should a supplementary payment be needed?
3. How to handle the case where a leader registers 10 students, pays Rs.2000, gets verified, then wants to add 5 more students to different events?
4. Should there be a "rounds" concept? Like Round 1: Register all you want → Pay → Admin verifies → Round 2: Add more if slots available?

Let me think about the architecture more carefully...

### The Real Problem:
The current system assumes registration + payment is a **one-shot** process. But in reality:
- Leaders might not have all 15 students ready at registration time
- They might want to register for 2 events first, pay, then add more students to other events later
- The 15-student cap is a hard limit, but teams might want to grow incrementally

### Proposed Architecture:

**Option A: Post-Verification Expansion**
1. Leader registers students → Payment → Admin verifies → Team is CONFIRMED
2. After CONFIRMED, leader can add more students (up to 15) to NEW events (not already registered)
3. New students added this way are automatically CONFIRMED (payment already done)
4. Fee difference is calculated and a supplementary payment may be needed

**Option B: Multi-Phase Registration**
1. Phase 1: Leader registers students for events → Submits payment → Admin verifies
2. Phase 2: Leader can add more students until the 15-cap or event deadline
3. Each phase has its own payment cycle

**Option C: Always-Open Registration with Pending Payments**
1. Leader can always add students (up to 15)
2. Payment is recalculated dynamically
3. Only after ALL events are locked (by admin or deadline), final payment is verifiedI think the user wants something like **Option A** - the simplest approach that solves the problem.

Let me now create a comprehensive plan for the user.

Now I have a complete picture of the architecture. Let me summarize my findings and present a clear analysis.

**Tool: read**

**Input:**
```json
{
  "filePath": "E:\\AION WINTER\\Backend AION2K26\\app\\repositories_sqla\\event_registration_repository.py"
}
```

**Output:**
```
<path>E:\AION WINTER\Backend AION2K26\app\repositories_sqla\event_registration_repository.py</path>
<type>file</type>
<content>
1: from sqlalchemy import delete, func, select, update
2: from sqlalchemy.ext.asyncio import AsyncSession
3: 
4: from app.models_sqla.event import Event, EventSlot
5: from app.models_sqla.event_registration import EventRegistration
6: 
7: 
8: class EventRegistrationRepositorySqla:
9:     def __init__(self, session: AsyncSession):
10:         self._session = session
11:         self._model = EventRegistration
12:         self._event_model = Event
13:         self._slot_model = EventSlot
14: 
15:     def _to_dict(self, obj: EventRegistration | None) -> dict | None:
16:         if obj is None:
17:             return None
18:         return {
19:             "_id": obj.id,
20:             "leaderId": obj.leader_id,
21:             "name": obj.name,
22:             "registerNumber": obj.register_number,
23:             "mobile": obj.mobile,
24:             "college": obj.college_name_text,
25:             "department": obj.department,
26:             "degree": obj.degree,
27:             "foodPreference": obj.food_preference,
28:             "status": obj.status,
29:             "event1_id": obj.event1_id,
30:             "slot1_id": obj.slot1_id,
31:             "event2_id": obj.event2_id,
32:             "slot2_id": obj.slot2_id,
33:             "event1": None,  # populated by callers via _resolve_event_names
34:             "slot1": None,
35:             "event2": None,
36:             "slot2": None,
37:         }
38: 
39:     async def _resolve_events_map(self) -> dict[int, str]:
40:         stmt = select(Event.id, Event.name)
41:         result = await self._session.execute(stmt)
42:         return {row.id: row.name for row in result.all()}
43: 
44:     async def _resolve_slots_map(self) -> dict[int, str]:
45:         stmt = select(EventSlot.id, EventSlot.slot_label)
46:         result = await self._session.execute(stmt)
47:         return {row.id: row.slot_label for row in result.all()}
48: 
49:     def _to_hydrated_dict(
50:         self,
51:         obj: EventRegistration,
52:         events: dict[int, str],
53:         slots: dict[int, str],
54:     ) -> dict:
55:         d = self._to_dict(obj)
56:         d["event1"] = events.get(obj.event1_id)
57:         d["slot1"] = slots.get(obj.slot1_id)
58:         d["event2"] = events.get(obj.event2_id) if obj.event2_id else None
59:         d["slot2"] = slots.get(obj.slot2_id) if obj.slot2_id else None
60:         return d
61: 
62:     async def _hydrate_many(self, objs: list[EventRegistration]) -> list[dict]:
63:         """Resolve the events/slots maps ONCE per batch.
64: 
65:         Never reintroduce a per-row map lookup — that was an N+1 (two extra
66:         SELECTs for every document returned).
67:         """
68:         events = await self._resolve_events_map()
69:         slots = await self._resolve_slots_map()
70:         return [self._to_hydrated_dict(o, events, slots) for o in objs]
71: 
72:     async def _hydrate(self, obj: EventRegistration) -> dict:
73:         return (await self._hydrate_many([obj]))[0]
74: 
75:     async def find_by_leader(self, leader_id: str) -> list[dict]:
76:         stmt = select(EventRegistration).where(EventRegistration.leader_id == leader_id)
77:         result = await self._session.execute(stmt)
78:         return await self._hydrate_many(result.scalars().all())
79: 
80:     async def find_leader_event(self, leader_id: str, event_name: str) -> dict | None:
81:         stmt_events = select(Event.id).where(Event.name == event_name)
82:         result_ev = await self._session.execute(stmt_events)
83:         event_id = result_ev.scalars().first()
84:         if event_id is None:
85:             return None
86:         stmt = select(EventRegistration).where(
87:             EventRegistration.leader_id == leader_id,
88:             (EventRegistration.event1_id == event_id)
89:             | (EventRegistration.event2_id == event_id),
90:         )
91:         result = await self._session.execute(stmt)
92:         obj = result.scalars().first()
93:         return await self._hydrate(obj) if obj else None
94: 
95:     async def find_team_by_register_numbers(
96:         self, leader_id: str, register_numbers: list[str]
97:     ) -> list[dict]:
98:         stmt = select(EventRegistration).where(
99:             EventRegistration.leader_id == leader_id,
100:             EventRegistration.register_number.in_(register_numbers),
101:         )
102:         result = await self._session.execute(stmt)
103:         return await self._hydrate_many(result.scalars().all())
104: 
105:     async def count_by_leader(self, leader_id: str) -> int:
106:         stmt = (
107:             select(func.count())
108:             .select_from(EventRegistration)
109:             .where(EventRegistration.leader_id == leader_id)
110:         )
111:         result = await self._session.execute(stmt)
112:         return int(result.scalar_one())
113: 
114:     async def count_distinct_students(self, leader_id: str) -> int:
115:         """Unique students for a leader — the fee basis.
116: 
117:         register_number is stored uppercased and UNIQUE per (leader_id,
118:         register_number), so COUNT(*) equals DISTINCT count; the explicit
119:         DISTINCT keeps this correct-by-construction.
120:         """
121:         stmt = (
122:             select(
123:                 func.count(
124:                     func.distinct(func.upper(EventRegistration.register_number))
125:                 )
126:             )
127:             .select_from(EventRegistration)
128:             .where(EventRegistration.leader_id == leader_id)
129:         )
130:         result = await self._session.execute(stmt)
131:         return int(result.scalar_one())
132: 
133:     async def update_status_by_leader(
134:         self,
135:         leader_id: str,
136:         new_status: str,
137:         from_statuses: tuple[str, ...],
138:     ) -> int:
139:         """Guarded bulk status transition for a leader's registrations."""
140:         stmt = (
141:             update(EventRegistration)
142:             .where(
143:                 EventRegistration.leader_id == leader_id,
144:                 EventRegistration.status.in_(from_statuses),
145:             )
146:             .values(status=new_status)
147:             .execution_options(synchronize_session=False)
148:         )
149:         result = await self._session.execute(stmt)
150:         return result.rowcount or 0
151: 
152:     async def find_team(self, college: str, department: str) -> list[dict]:
153:         stmt = select(EventRegistration).where(
154:             EventRegistration.college_name_text == college,
155:             EventRegistration.department == department,
156:         )
157:         result = await self._session.execute(stmt)
158:         return await self._hydrate_many(result.scalars().all())
159: 
160:     async def find_by_leader_and_event(
161:         self, leader_id: str, event_name: str
162:     ) -> list[dict]:
163:         stmt_events = select(Event.id).where(Event.name == event_name)
164:         event_id = (await self._session.execute(stmt_events)).scalars().first()
165:         if event_id is None:
166:             return []
167:         stmt = select(EventRegistration).where(
168:             EventRegistration.leader_id == leader_id,
169:             (EventRegistration.event1_id == event_id)
170:             | (EventRegistration.event2_id == event_id),
171:         )
172:         result = await self._session.execute(stmt)
173:         return await self._hydrate_many(result.scalars().all())
174: 
175:     async def promote_event2_to_event1(
176:         self, doc_id: int, event2_id: int, slot2_id: int | None
177:     ) -> None:
178:         stmt = (
179:             update(EventRegistration)
180:             .where(EventRegistration.id == doc_id)
181:             .values(
182:                 event1_id=event2_id,
183:                 slot1_id=slot2_id,
184:                 event2_id=None,
185:                 slot2_id=None,
186:             )
187:         )
188:         await self._session.execute(stmt)
189: 
190:     async def clear_event2(self, doc_id: int) -> None:
191:         stmt = (
192:             update(EventRegistration)
193:             .where(EventRegistration.id == doc_id)
194:             .values(event2_id=None, slot2_id=None)
195:         )
196:         await self._session.execute(stmt)
197: 
198:     async def delete_many_by_leader(self, leader_id: str) -> int:
199:         stmt = (
200:             delete(EventRegistration)
201:             .where(EventRegistration.leader_id == leader_id)
202:             .execution_options(synchronize_session=False)
203:         )
204:         result = await self._session.execute(stmt)
205:         return result.rowcount or 0
206: 
207:     async def delete_one(self, doc_id: int) -> None:
208:         stmt = (
209:             delete(EventRegistration)
210:             .where(EventRegistration.id == doc_id)
211:             .execution_options(synchronize_session=False)
212:         )
213:         await self._session.execute(stmt)
214: 
215:     async def count_leader_event(self, leader_id: str, event_name: str) -> int:
216:         stmt_events = select(Event.id).where(Event.name == event_name)
217:         event_id = (await self._session.execute(stmt_events)).scalars().first()
218:         if event_id is None:
219:             return 0
220:         stmt = (
221:             select(func.count())
222:             .select_from(EventRegistration)
223:             .where(
224:                 EventRegistration.leader_id == leader_id,
225:                 (EventRegistration.event1_id == event_id)
226:                 | (EventRegistration.event2_id == event_id),
227:             )
228:         )
229:         return int((await self._session.execute(stmt)).scalar_one())

(End of file - total 229 lines)
</content>
```

---

## Assistant (Plan · MiMo V2.5 Free · 42.5s)

_Thinking:_

Now I have a thorough understanding of the codebase. Let me analyze the current flow and the user's concerns, then present a clear architectural plan.

## Current Flow Analysis

### Current Registration + Payment Flow:
1. Leader registers team for Event1 → students get `PAYMENT_PENDING` status
2. Fee is calculated: `unique_students × Rs.200` (per unique register number, not per event)
3. Leader can register for Event2 (adding same students to second event, or new students)
4. At any point, leader can submit payment proof (UTR + screenshot)
5. Once proof is submitted → `payment_status = VERIFICATION_PENDING`, `registration_status = VERIFICATION_PENDING`
6. **TEAM EDITS ARE LOCKED** (`assert_team_edits_allowed` blocks when status is `VERIFICATION_PENDING` or `SUCCESS`)
7. Admin verifies → all registrations become `CONFIRMED`

### The Problem:
The user is saying:
- In their "demo test", the student leader's other event registrations are **blocked** after payment
- They want the payment to be ONE bulk payment by the student leader for the whole team
- After admin verifies the payment, if the 15-student limit isn't reached, the leader should be able to add MORE students to OTHER events

### Current Code Issues:

1. **`assert_team_edits_allowed`** (payment_sqla.py:73-80): This blocks ALL team edits when `paymentStatus` is in `PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")`. This means:
   - Once payment is submitted → can't add/remove students
   - Once payment is verified → can't add/remove students
   
2. **The15-student limit** is enforced at registration time (`MAX_STUDENTS_PER_LEADER = 15`), but it's a total across ALL events.

3. **Fee calculation**: `unique_students × Rs.200` - this means if a student is in 2 events, they still pay only Rs.200 once.

### What the user wants (my understanding):

**Option A (Current - what they're NOT happy with):**
- Leader registers students for events → payment → blocked → admin verifies → DONE (can't expand)

**Option B (What they're asking about but find tedious):**
- Remove blocking → leader can always add students → but admin has to verify each event's payment separately**Option C (What they prefer - the RIGHT architecture):**
1. Leader builds team (adds students to events) - can add up to 15 students
2. Leader submits ONE payment for the whole team
3. Admin verifies ONCE
4. After verification (CONFIRMED), leader CAN still add more students to other events (up to 15 limit)
5. If new students are added after initial payment, a supplementary payment may be needed
6. OR: After first payment verification, new students added are automatically confirmed (free addition within the already-paid amount?)

Wait, let me re-read the user's message more carefully:

> "so i am prefering to have one bulk payment to the student leader after all event members are added to the db and pay button to complete the registrations. in this situations, once the payment is done, shall we allow other event registrations if their 15 limit is not obtained, so they can expand their team to the other events too"

So the flow they want:
1. Leader adds ALL students to events first (no payment needed yet, or payment in PENDING state)
2. Leader clicks "Pay" → one bulk payment
3. Admin verifies
4. AFTER verification, if 15-student limit not reached, leader CAN add MORE students to OTHER events
5. These new students might need additional payment

Actually, re-reading again, I think there might be a simpler interpretation:

The user's concern is about the **timing** of when events are "locked":
- Current: Once payment is submitted, ALL event registrations are frozen
- Desired: After payment is verified (CONFIRMED), the leader should still be able to EXPAND their team to other events if they haven't hit the 15-student cap

This is a reasonable requirement. The admin has already verified the initial payment. If the leader adds more students later:
- Option 1: The additional students are automatically confirmed (fee was already covered if the initial payment ≥ expected amount)
- Option 2: The additional students go through a separate payment cycle

Let me think about this more carefully...

Actually, the fee is per unique student (Rs.200). So:
- If leader registers 10 students → pays Rs.2000 → admin verifies
- Then leader adds 5 more students to different events → additional Rs.1000 needed
- These5 new students would be in PAYMENT_PENDING state
- Leader would need to make another payment of Rs.1000

OR:
- The initial payment covers all students up to 15
- Leader pays Rs.3000 upfront for 15 students
- Admin verifies Rs.3000
- Leader can then add students incrementally, already covered by the initial payment

The second approach is simpler from a UX perspective but risky (what if leader doesn't fill all 15?).

Let me plan the architecture now. I think the user wants:

### Recommended Architecture:

**Phase-based Registration with Post-Verification Expansion:**

1. **Registration Phase** (Payment PENDING):
   - Leader can add/remove/edit students freely
   - No payment required yet
   - Can register for multiple events
   - 15-student cap enforced

2. **Payment Phase** (Payment SUBMITTED → VERIFICATION_PENDING):
   - Team edits LOCKED (current behavior, reasonable for preventing fraud during verification)
   - One bulk payment for all registered students
   - Admin reviews and verifies/rejects

3. **Post-Verification Phase** (Payment SUCCESS → registrations CONFIRMED):
   - **NEW**: Leader CAN add more students if under 15-student cap
   - New students are automatically CONFIRMED (payment already done)
   - BUT: Fee calculation changes → additional fee may be needed
   - If additional fee > 0: leader must submit supplementary payment

Wait, this gets complicated. Let me think about whether to allow expansion at all after verification...

Actually, I think the simplest and cleanest approach is:

### Simplest Correct Architecture:

**Option: Allow Adding Students Only When Payment is PENDING**

1. Leader registers students → status = PAYMENT_PENDING
2. Leader can keep adding students (up to 15) while status is PAYMENT_PENDING
3. When ready, leader submits payment → status = VERIFICATION_PENDING → team locked
4. Admin verifies → status = SUCCESS → registrations = CONFIRMED
5. **After verification, NO more additions** (team is finalized)

**Problem**: What if leader wants to add students AFTER admin verification? They can't.

**Better Option: Allow Post-Verification Addition with Supplementary Payment**

1. Registration Phase: Leader adds students → PAYMENT_PENDING → fee recalculated each time
2. Payment Phase: Leader submits payment → VERIFICATION_PENDING → team locked temporarily
3. Admin verifies → SUCCESS → team UNLOCKED
4. **Expansion Phase**: Leader can add more students (up to 15) → new students = PAYMENT_PENDING
5. Leader submits supplementary payment for new students → cycle repeats

This is the most flexible but more complex.

**Even Better: The user's preferred approach**

Actually, re-reading the user's message one more time:

> "shall we get the payment as one bulk. but there maybe chances of registrations less than 15 members too. how to handle this situations."

> "once the payment is done, shall we allow other event registrations if their 15 limit is not obtained, so they can expand their team to the other events too"

I think the user is asking:
1. Should we take one bulk payment for the whole team? YES
2. What if team has less than 15 members? That's fine, charge for actual count
3. After payment is done and verified, should we allow expanding to other events if under 15? The user wants to discuss this

Let me present both options clearly:

**Option A: Lock After Verification (Simple)**
- After admin verifies payment, team is FINALIZED
- No more additions
- Pro: Simple, clean- Con: Inflexible

**Option B: Allow Expansion After Verification (Flexible)**
- After admin verifies, leader can add more students
- New students need supplementary payment
- Pro: Flexible
- Con: More complex admin work for supplementary payments

**Option C: Pre-Payment Registration Window (Recommended)**
- Leader has a registration window to add all students
- During this window, no payment needed
- When window closes (or leader is ready), they submit payment
- Payment locks the team temporarily for admin verification
- After verification, team is FINALIZED
- Pro: Clear phases, simple
- Con: Need to define the "window"

Actually, I think the current architecture is almost right. The issue is that `assert_team_edits_allowed` blocks at `VERIFICATION_PENDING` AND `SUCCESS`. The user wants it to unblock after `SUCCESS`.

Let me present a clear architectural recommendation.

Now I have a complete understanding of the codebase. Let me present my analysis and architectural recommendations.

---

## Current Flow Analysis

Here's what the code does today:

### Current Registration → Payment → Verification Flow

```
Leader adds students → PAYMENT_PENDING
Leader submits proof → VERIFICATION_PENDING → TEAM EDITS LOCKED
Admin verifies → SUCCESS/CONFIRMED → TEAM EDITS STILL LOCKED (permanent)
```

**The blocking mechanism** (`payment_sqla.py:73-80`):
```python
PAYMENT_LOCKED_STATUSES = ("VERIFICATION_PENDING", "SUCCESS")

def assert_team_edits_allowed(payment):
    if payment and payment["paymentStatus"] in PAYMENT_LOCKED_STATUSES:
        raise APIError(409, "Team changes are locked...")
```

This is called in `auth.py:145` **before** every `/registerteam` call. Once you submit proof, you can **never** add more students — even after verification.

### Key Invariants Already in Place
- **One payment per leader** (UNIQUE on `leader_id`) — already bulk
- **Fee = Rs.200 × unique students** (not per event) — already correct
- **15-student cap** across all events — already enforced
- **Single transaction** for all registration + payment changes — already atomic

---

## The Problem You Identified

| Scenario | What Happens Today | What Should Happen |
|---|---|---|
| Leader registers 10 students, pays, admin verifies | **Permanent lock** — can never add 5 more | Should allow expansion to 15 if slots remain |
| Leader registers for Event1 + Event2, pays | Can't add Event3 participants after verification | Should allow adding students to new events post-verification |
| Leader has 15 students, all confirmed | Lock is fine — team is full | Correct behavior |

**The core issue**: `PAYMENT_LOCKED_STATUSES` includes `SUCCESS` — this means even after admin approves payment, the team is permanently frozen. This is too aggressive.

---

## Architecture Options

### Option A: Unlock After Verification (Recommended)

```
Phase 1: REGISTRATION (payment_status = PENDING)
  → Leader adds/removes students freely
  → Fee recalculates dynamically (Rs.200 × unique students)
  → Can register for any events (slot rules apply)

Phase 2: PAYMENT SUBMITTED (payment_status = VERIFICATION_PENDING)
  → Team EDITS LOCKED (prevents fraud during admin review)
  → Admin reviews UTR + screenshot

Phase 3: VERIFIED (payment_status = SUCCESS, registrations = CONFIRMED)
  → Team EDITS UNLOCKED ← THIS IS THE CHANGE
  → Leader CAN add more students (up to 15 cap)
  → New students auto-CONFIRMED (payment already covered IF amount >= expected)
  → OR new students = PAYMENT_PENDING if fee increased

Phase 4: FINALIZED (optional — admin or deadline locks permanently)
```

**Changes needed**:
1. `constants.py`: Add a new locked status tuple that excludes `SUCCESS`
2. `payment_sqla.py`: `assert_team_edits_allowed` only blocks during `VERIFICATION_PENDING`
3. `registration_sqla.py`: After adding students post-verification, check if supplementary payment is needed
4. `fees.py`: Add logic for supplementary fee calculation

**Pros**: Simple change, preserves existing flow, allows expansion
**Cons**: Need to handle supplementary payments if fee increases

---

### Option B: Separate Registration Window from Payment

```
Phase 1: OPEN REGISTRATION
  → Leader adds students, no payment yet
  → Fee shown dynamically but not collected
  → Registration deadline (set by admin) ends this phase

Phase 2: PAYMENT
  → Leader pays for all registered students
  → Team LOCKED during verification

Phase 3: CONFIRMED
  → Team UNLOCKED for expansion
  → Same supplementary payment logic as Option A
```

**Changes needed**: Add a `registration_deadline` config, freeze registrations after deadline

**Pros**: Clear separation of concerns
**Cons**: More complex, needs deadline management

---

### Option C: Always Allow Registration, Payment is Separate Track

```
Any time: Leader can add students (up to 15)
Payment track: Independent of registration
  → Leader pays whenever they want
  → Admin verifies whenever they want
  → Registration never blocks payment, payment never blocks registration
```

**Pros**: Maximum flexibility
**Cons**: Admin nightmare — students could be in events without payment, hard to track who paid for what

---

## My Recommendation: Option A

**Why Option A**:
1. **Minimal code change** — only `assert_team_edits_allowed` needs to change
2. **Preserves fraud prevention** — team is still locked during admin review
3. **Allows natural expansion** — if a leader has 10 students confirmed, they can add 5 more
4. **Fee handling is clean** — existing `calculate_registration_fee()` already recalculates based on unique students

### Detailed Flow for Option A

```
1. Leader registers 8 students for Event1 + Event2
   → payment_status = PENDING
   → registration_status = PAYMENT_PENDING
   → Fee = 8 × Rs.200 = Rs.1600

2. Leader submits payment proof
   → payment_status = VERIFICATION_PENDING
   → registration_status = VERIFICATION_PENDING
   → TEAM EDITS LOCKED (during admin review)

3. Admin verifies payment
   → payment_status = SUCCESS
   → registration_status = CONFIRMED
   → TEAM EDITS UNLOCKED

4. Leader adds 4 more students for Event3 (different slot)
   → 4 new registrations = PAYMENT_PENDING
   → Fee recalculates: 12 × Rs.200 = Rs.2400
   → Supplementary amount = Rs.2400 - Rs.1600 = Rs.800

5. Leader submits supplementary payment proof
   → New registrations = VERIFICATION_PENDING
   → Existing CONFIRMED registrations stay CONFIRMED
   → Admin verifies supplementary payment
   → All CONFIRMED

6. Leader adds 3 more students for Event4
   → Same cycle
   → Total: 15 students, fee = Rs.3000
```

### Code Changes Required

| File | Change | Lines |
|---|---|---|
| `constants.py` | Add `PAYMENT_EDIT_LOCKED_STATUSES = ("VERIFICATION_PENDING",)` | ~1 line |
| `payment_sqla.py` | `assert_team_edits_allowed` uses new constant | ~2 lines |
| `registration_sqla.py` | Handle post-verification additions (new students = PAYMENT_PENDING, existing unchanged) | ~10 lines |
| `payment_sqla.py` | `submit_payment_proof` handles partial transitions (only flip PAYMENT_PENDING rows) | ~5 lines |
| `fees.py` | Add `calculate_supplementary_fee()` | ~5 lines |

### Edge Cases to Handle

| Edge Case | Handling |
|---|---|
| Leader at 15 students, tries to add more | Reject with "15-student limit reached" (already works) |
| Leader adds student, fee increases, hasn't paid difference | New student stays PAYMENT_PENDING, leader can submit supplementary proof |
| Leader at 15, all confirmed, wants to swap a student | Need separate "edit student" flow (not covered in this change) |
| Admin rejects payment after some students already added post-verification | Only revert the PAYMENT_PENDING rows; CONFIRMED stay confirmed |
| Race condition: leader adds student while admin is verifying | VERIFICATION_PENDING lock prevents this |

---

### What I Need From You

Before I create the implementation plan, I need to clarify a few things:

1. **After verification, should new students be auto-CONFIRMED or need supplementary payment?**
   - Auto-CONFIRMED: Simpler, but leader might not pay for all students
   - Supplementary payment: More accurate, but more admin work

2. **Should there be a registration deadline?**
   - If yes: After deadline, team is permanently locked
   - If no: Leader can add students anytime before event

3. **Do you want to support student swaps (remove one, add another) post-verification?**
   - This is more complex — needs admin approval for removal

4. **Should the admin see a "pending balance" if supplementary payment is needed?**

Let me know your preferences and I'll create a detailed implementation plan.

---

