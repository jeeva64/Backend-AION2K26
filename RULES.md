# AION 2K26 — Rules & Regulations

**DEPARTMENT OF ARTIFICIAL INTELLIGENCE**
St. Joseph's College (Autonomous)
Accredited at A++ (Cycle IV) by NAAC · Special Heritage Status Awarded by UGC
College with Potential for Excellence by UGC · DBT – STAR & DST – FIST Sponsored College
25th Rank in NIRF 2025
Tiruchirappalli – 620 002, Tamil Nadu, India

**Event date: 07/10/2026 (Wednesday)**

> This document is the participant-facing rulebook for AION 2K26. It harmonizes
> the official symposium circular with the rules the website actually enforces.
> **Where the circular and the website disagree on registration or payment, the
> website rules govern** (see [Payment & Registration Rules](#payment--registration-rules)).
> Team sizes, slot allotments, and the fee below are kept in sync with
> `app/utils/constants.py` (`EVENT_MAX_TEAM_SIZE`, `EVENT_SLOT_MAP`,
> `MAX_STUDENTS_PER_LEADER`) and `app/services/fees.py`.

---

## General Instructions

- A maximum of **15 participants per department** are allowed to participate.
- Each participant may register for a **maximum of two events** (the two events
  must fall in different time slots).
- **Registration fee: ₹200 per participant.** The fee is paid **online through
  the website** by the team leader when registering — see
  [Payment & Registration Rules](#payment--registration-rules). Cash payment is
  not accepted for teams registered through the website.
- **Registration is online only.** Spot registration is not allowed.
- **Only one team member (the leader) should register for the entire team.**
  One leader represents one department team (one leader per college +
  department + shift).
- Participants must bring a **valid college ID card** and a **Bonafide
  certificate** duly signed by the Head or Coordinator of the Department.
- Participants are requested to report at the registration venue by
  **8:30 a.m. sharp** on the day of the event (07/10/2026).
- Refreshments and lunch will be provided **only to registered participants**.
- The **judges' decision shall be final**. No further clarifications or
  objections will be entertained.
- Any team violating the rules or misbehaving inside the campus will be
  **disqualified** from further proceedings.
- For any queries, participants are requested to contact the Chairman of the
  Symposium. The Chairman's contact details are available in the Symposium
  Brochure.

---

## Payment & Registration Rules

These rules are enforced by the website. They supersede any circular wording
about paying on the event day or by cash.

1. **Fee** - ₹200 per participant, charged once per **unique registered
   student** (not per event). A student registered in two events still pays
   ₹200 only. The backend calculates the total: `₹200 × unique students` in
   the department team.
2. **Who pays** - the team leader pays a **single bulk amount** for the whole
   department team through the website (one payment record per leader).
3. **How to pay** - **online UPI only.** The payment page shows a UPI QR code /
   UPI intent URI with the exact amount. After transferring, the leader submits
   proof on the website: **UTR (transaction reference) + amount + payment
   screenshot** (JPG/PNG/WebP).
4. **Confirmation** - registration is **not confirmed until the organizer
   verifies the payment**:

   ```
   Registered (PAYMENT_PENDING)
     → proof submitted (VERIFICATION_PENDING)
     → organizer verifies (CONFIRMED)
   ```

   Until status is `CONFIRMED`, the team's seat is not guaranteed. A screenshot
   alone never marks a payment successful.
5. **Rejection** - if the proof is rejected (wrong amount, duplicate UTR,
   unclear screenshot), the leader may **fix and resubmit**; the reason is shown
   on the payment page.
6. **Adding students after verification** - after the payment is verified
   (`SUCCESS`), the leader may add more students (within the 15-participant
   cap). The new students start as `PAYMENT_PENDING` and require a
   **supplementary UPI payment + proof** for the additional ₹200 per student.
7. **UTR rules** - the UTR must be 8–22 alphanumeric characters and is
   **unique across all teams**; reusing another team's UTR is rejected.
8. **Cash / on-day payment** - not accepted for website registered teams. The
   website's online UPI verification workflow is the only payment channel.

---

## Registration Rules (website-enforced)

| Rule | Limit | Enforced as |
|---|---|---|
| Participants per department | 15 unique students per leader | `409` when exceeded |
| Events per participant | 2 (different slots) | `409` on same-slot clash |
| Teams per event per department | 1 | `409` if already registered |
| One leader per department team | college + department + shift | `400` on duplicate leader |
| Spot registration | Not allowed | registration routes closed when the admin closes registration |

---

## Event → Slot Map

| Event | Slot | Max team size |
|---|---|---|
| Fixathon | 1 | 2 |
| Mute Masters | 1 | 2 |
| Treasure Titans | 1 | 2 |
| Bid Mayhem | BOTH | 2 |
| QRush | 2 | 2 |
| VisionX | 2 | 1 (individual) |
| ThinkSync | 2 | 2 |
| Crazy Sell | 2 | 4 |

---

## Technical Events

### 1. QRush (Technical Quiz)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- Teams are requested to bring a mobile device with proper internet connection.
- Topics: basic concepts of Computer Science (OOPs, SQL, Operating Systems,
  Computer Networks and AI).
- Prelims will be conducted.
- Mains: buzzer round.

### 2. Fixathon (Debugging)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- Prelims: written test on paper (SQL).
- Mains: system-based debugging using Python, Java, C++.

### 3. VisionX (Prompt Challenge)

- Only **one participant per department** is allowed.
- **Individual participant** (team size: 1).
- Prelims: image creation using any AI tools.
- Mains: video creation using any AI tools.
- Theme will be provided on the spot.

### 4. ThinkSync (Tech Connection)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- Teams are requested to bring a mobile device with proper internet connection.
- Questions will be based on technology-related words.
- Prelims will be conducted.
- Mains: buzzer round.

---

## Non-Technical Events

### 5. Bid Mayhem (IPL Auction)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- Prelims: MCQ round (knowledge of IPL from 2008–2026 is required).
- Mains: auction round will be conducted. Rules for the mains round will be
  announced on the day of the event.
- **Note: participants of this event cannot participate in any other event.**
  Bid Mayhem occupies both time slots and is exclusive — enforced by the
  website and the database.

### 6. Crazy Sell (Adzap)

- Only **one team per department** is allowed.
- **Team size: 4 members.**
- Duration: 5 minutes.
- Prelims round will be conducted depending on the number of teams that
  register.
- Theme will be provided 15 minutes prior to the event.

### 7. Mute Masters (Dumb Charades)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- The event will consist of three rounds: Movies, Famous Personalities, and
  Songs.

### 8. Treasure Titans (Treasure Hunt)

- Only **one team per department** is allowed.
- **Team size: 2 members.**
- Mobile phones are not allowed, unless explicitly permitted by coordinators.
- The team that finds the final treasure first will be declared the winner.
- Cheating, misbehaviour, copying or sharing clues, disobeying volunteers, or
  violating any rules will lead to **immediate disqualification**.
- Organizers have full authority to take the final decision.

---

## On-the-Day Instructions (07/10/2026)

These are venue rules, administered by the organizers (not by the website):

- Report at the registration venue by **8:30 a.m. sharp**.
- Produce a **valid college ID card** and a **Bonafide certificate** signed by
  the Head or Coordinator of the Department.
- Only participants with a **confirmed** online registration
  (`CONFIRMED` payment status) are admitted; **spot registration is not
  allowed**.
- Refreshments and lunch are provided only to registered participants.
- The judges' decision is final; no clarifications or objections will be
  entertained after the announcement of results.
- Misbehaviour or violation of rules inside the campus leads to disqualification
  of the team from further proceedings.
