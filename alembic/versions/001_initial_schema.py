"""Schema iniziale

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "disciplines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=7), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_disciplines_id", "disciplines", ["id"])

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("privacy_accepted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_id", "customers", ["id"])
    op.create_index("ix_customers_email", "customers", ["email"])

    appointment_status = sa.Enum(
        "pending", "confirmed", "cancelled", "completed", "no_show",
        name="appointmentstatus"
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", appointment_status, nullable=False, server_default="pending"),
        sa.Column("cancellation_token", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["discipline_id"], ["disciplines.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "discipline_id", "appointment_date", "start_time",
            name="uq_discipline_date_time"
        ),
        sa.UniqueConstraint("cancellation_token"),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"])
    op.create_index("ix_appointments_appointment_date", "appointments", ["appointment_date"])
    op.create_index("ix_appointments_status", "appointments", ["status"])
    op.create_index("ix_appointments_cancellation_token", "appointments", ["cancellation_token"])

    op.create_table(
        "availability_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["discipline_id"], ["disciplines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_availability_rules_id", "availability_rules", ["id"])

    op.create_table(
        "blocked_dates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("discipline_id", sa.Integer(), nullable=True),
        sa.Column("blocked_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=200), nullable=True),
        sa.Column("all_disciplines", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["discipline_id"], ["disciplines.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_blocked_dates_id", "blocked_dates", ["id"])
    op.create_index("ix_blocked_dates_blocked_date", "blocked_dates", ["blocked_date"])

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("booking_data", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_otp_codes_id", "otp_codes", ["id"])
    op.create_index("ix_otp_codes_email", "otp_codes", ["email"])

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_users_id", "admin_users", ["id"])


def downgrade() -> None:
    op.drop_table("admin_users")
    op.drop_table("otp_codes")
    op.drop_table("blocked_dates")
    op.drop_table("availability_rules")
    op.drop_table("appointments")
    op.execute("DROP TYPE IF EXISTS appointmentstatus")
    op.drop_table("customers")
    op.drop_table("disciplines")
