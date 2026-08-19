"""initial postgres schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Reference table: event_slots ('1', '2', 'BOTH')
    op.create_table(
        "event_slots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slot_label", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("slot_label IN ('1', '2', 'BOTH')", name="ck_event_slots_label"),
    )
    op.create_unique_constraint("uq_event_slots_slot_label", "event_slots", ["slot_label"])

    # Reference table: events (seeded from EVENT_SLOT_MAP)
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column(
            "slot_id",
            sa.BigInteger,
            sa.ForeignKey("event_slots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_events_name", "events", ["name"])
    op.create_index("ix_events_slot_id", "events", ["slot_id"])

    # admins
    op.create_table(
        "admins",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("admin_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.SmallInteger, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("role IN (1, 2)", name="ck_admins_role"),
    )
    op.create_unique_constraint("uq_admins_admin_id", "admins", ["admin_id"])
    op.create_index("ix_admins_role", "admins", ["role"])

    # colleges
    op.create_table(
        "colleges",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("college_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=False),
        sa.Column("district", sa.Text, nullable=False),
        sa.Column(
            "registered_status",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_colleges_college_id", "colleges", ["college_id"])
    op.create_index("ix_colleges_name", "colleges", ["name"])

    # users (leaders)
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("mobile_number", sa.Text, nullable=False),
        sa.Column("department", sa.Text, nullable=False),
        sa.Column("college_name_text", sa.Text, nullable=False),
        sa.Column(
            "college_id",
            sa.BigInteger,
            sa.ForeignKey("colleges.id", onupdate="CASCADE", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("shift", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "department IN ('cs', 'it', 'ai', 'ds', 'ca')", name="ck_users_department"
        ),
        sa.CheckConstraint("shift IN ('1', '2')", name="ck_users_shift"),
    )
    op.create_unique_constraint("uq_users_user_id", "users", ["user_id"])
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_unique_constraint("uq_users_mobile_number", "users", ["mobile_number"])
    op.create_index(
        "ix_users_college_text_dept_shift",
        "users",
        ["college_name_text", "department", "shift"],
    )

    # event_registrations (the core table)
    op.create_table(
        "event_registrations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "leader_id",
            sa.Text,
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("register_number", sa.Text, nullable=False),
        sa.Column("mobile", sa.Text, nullable=False),
        sa.Column("college_name_text", sa.Text, nullable=False),
        sa.Column(
            "college_id",
            sa.BigInteger,
            sa.ForeignKey("colleges.id", onupdate="CASCADE", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("department", sa.Text, nullable=False),
        sa.Column("degree", sa.Text, nullable=False),
        sa.Column("food_preference", sa.Text, nullable=False),
        sa.Column(
            "event1_id",
            sa.BigInteger,
            sa.ForeignKey("events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "slot1_id",
            sa.BigInteger,
            sa.ForeignKey("event_slots.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "event2_id",
            sa.BigInteger,
            sa.ForeignKey("events.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "slot2_id",
            sa.BigInteger,
            sa.ForeignKey("event_slots.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "department IN ('cs', 'it', 'ai', 'ds', 'ca')",
            name="ck_event_registrations_department",
        ),
        sa.CheckConstraint(
            "degree IN ('ug', 'pg')", name="ck_event_registrations_degree"
        ),
        sa.CheckConstraint(
            "food_preference IN ('vegetarian', 'non-vegetarian')",
            name="ck_event_registrations_food_preference",
        ),
        sa.CheckConstraint(
            "(event2_id IS NULL AND slot2_id IS NULL) "
            "OR (event2_id IS NOT NULL AND slot2_id IS NOT NULL)",
            name="ck_event_registrations_event2_slot2_paired",
        ),
        sa.CheckConstraint(
            "event2_id IS NULL OR event1_id <> event2_id",
            name="ck_event_registrations_distinct_events",
        ),
        sa.CheckConstraint(
            "slot2_id IS NULL OR slot1_id <> slot2_id",
            name="ck_event_registrations_no_same_slot_clash",
        ),
    )
    op.create_unique_constraint(
        "uq_event_registrations_leader_register",
        "event_registrations",
        ["leader_id", "register_number"],
    )
    op.create_index(
        "ix_event_registrations_leader_event1",
        "event_registrations",
        ["leader_id", "event1_id"],
    )
    op.create_index(
        "ix_event_registrations_leader_event2",
        "event_registrations",
        ["leader_id", "event2_id"],
    )
    op.create_index(
        "ix_event_registrations_college_dept",
        "event_registrations",
        ["college_name_text", "department"],
    )
    op.create_index(
        "ix_event_registrations_event1",
        "event_registrations",
        ["event1_id"],
    )
    op.create_index(
        "ix_event_registrations_event2",
        "event_registrations",
        ["event2_id"],
    )

    # Bid Mayhem 'BOTH' exclusivity trigger.
    op.execute(
        """
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
    )
    op.execute(
        """
        CREATE TRIGGER trg_bid_mayhem
        BEFORE INSERT OR UPDATE OF event1_id, event2_id
        ON event_registrations
        FOR EACH ROW
        EXECUTE FUNCTION enforce_bid_mayhem_exclusivity();
        """
    )

    # --- Seed reference data ---
    op.execute(
        """
        INSERT INTO event_slots (slot_label, description) VALUES
            ('1', 'Slot 1 events'),
            ('2', 'Slot 2 events'),
            ('BOTH', 'Bid Mayhem occupies both slots simultaneously')
        ON CONFLICT (slot_label) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO events (name, display_name, slot_id) VALUES
            ('Fixathon',       'Fixathon',       (SELECT id FROM event_slots WHERE slot_label = '1')),
            ('Mute Masters',   'Mute Masters',   (SELECT id FROM event_slots WHERE slot_label = '1')),
            ('Treasure Titans','Treasure Titans',(SELECT id FROM event_slots WHERE slot_label = '1')),
            ('Bid Mayhem',     'Bid Mayhem',     (SELECT id FROM event_slots WHERE slot_label = 'BOTH')),
            ('QRush',          'QRush',          (SELECT id FROM event_slots WHERE slot_label = '2')),
            ('VisionX',        'VisionX',        (SELECT id FROM event_slots WHERE slot_label = '2')),
            ('ThinkSync',      'ThinkSync',      (SELECT id FROM event_slots WHERE slot_label = '2')),
            ('Crazy Sell',     'Crazy Sell',     (SELECT id FROM event_slots WHERE slot_label = '2'))
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_bid_mayhem ON event_registrations")
    op.execute("DROP FUNCTION IF EXISTS enforce_bid_mayhem_exclusivity()")
    op.drop_table("event_registrations")
    op.drop_table("users")
    op.drop_table("colleges")
    op.drop_table("admins")
    op.drop_table("events")
    op.drop_table("event_slots")
