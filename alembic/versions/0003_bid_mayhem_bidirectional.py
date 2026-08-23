"""make trg_bid_mayhem bidirectional

Revision ID: 0003_bid_mayhem_bidirectional
Revises: 0002_seed_super_admin
Create Date: 2025-01-01 00:00:02.000000

The original trigger only rejected adding a second event when event1
occupied slot 'BOTH'. A row like event1=Fixathon('1') with
event2=Bid Mayhem('BOTH') passed both the trigger and the same-slot CHECK
(since '1' <> 'BOTH'). This revision replaces the function so that Bid
Mayhem in EITHER column is rejected whenever the other column is populated.
The trigger definition itself is unchanged (already fires BEFORE INSERT OR
UPDATE OF event1_id, event2_id).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_bid_mayhem_bidirectional"
down_revision: Union[str, None] = "0002_seed_super_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_FUNCTION = """
CREATE OR REPLACE FUNCTION enforce_bid_mayhem_exclusivity()
RETURNS trigger AS $$
DECLARE
    slot1_label TEXT;
    slot2_label TEXT;
BEGIN
    IF NEW.event2_id IS NOT NULL THEN
        SELECT s.slot_label INTO slot1_label
        FROM events e
        JOIN event_slots s ON s.id = e.slot_id
        WHERE e.id = NEW.event1_id;

        SELECT s.slot_label INTO slot2_label
        FROM events e
        JOIN event_slots s ON s.id = e.slot_id
        WHERE e.id = NEW.event2_id;

        IF slot1_label = 'BOTH' OR slot2_label = 'BOTH' THEN
            RAISE EXCEPTION 'Bid Mayhem occupies both slots and cannot be combined with another event';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# Pre-0003 behavior, restored verbatim on downgrade.
_OLD_FUNCTION = """
CREATE OR REPLACE FUNCTION enforce_bid_mayhem_exclusivity()
RETURNS trigger AS $$
DECLARE slot_label TEXT;
BEGIN
    SELECT s.slot_label INTO slot_label
    FROM events e
    JOIN event_slots s ON s.id = e.slot_id
    WHERE e.id = NEW.event1_id;
    IF slot_label = 'BOTH' AND NEW.event2_id IS NOT NULL THEN
        RAISE EXCEPTION 'Bid Mayhem occupies both slots; cannot add a second event';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # CREATE OR REPLACE keeps the existing trigger (trg_bid_mayhem) bound to
    # the updated function body — no DROP TRIGGER needed.
    op.execute(_NEW_FUNCTION)


def downgrade() -> None:
    op.execute(_OLD_FUNCTION)
