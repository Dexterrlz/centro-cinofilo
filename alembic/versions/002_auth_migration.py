"""Migrazione sistema auth: customers -> users, rimozione otp_codes

Revision ID: 002
Revises: 001
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Crea tabella users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("dog_name", sa.String(length=100), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("google_id", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("verification_token", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("google_id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    # Migra i clienti esistenti nella tabella users
    op.execute("""
        INSERT INTO users (first_name, last_name, email, email_verified, is_active, created_at)
        SELECT first_name, last_name, email, true, true, created_at
        FROM customers
        ON CONFLICT (email) DO NOTHING
    """)

    # Aggiungi colonna user_id a appointments
    op.add_column("appointments", sa.Column("user_id", sa.Integer(), nullable=True))

    # Popola user_id basandosi sull'email del customer
    op.execute("""
        UPDATE appointments a
        SET user_id = u.id
        FROM customers c
        JOIN users u ON u.email = c.email
        WHERE a.customer_id = c.id
    """)

    # Rendi user_id non nullable dopo la migrazione dei dati
    op.alter_column("appointments", "user_id", nullable=False)

    # Aggiungi FK constraint
    op.create_foreign_key(
        "fk_appointments_user_id",
        "appointments", "users",
        ["user_id"], ["id"]
    )

    # Rimuovi la vecchia FK e colonna customer_id
    op.drop_constraint("appointments_customer_id_fkey", "appointments", type_="foreignkey")
    op.drop_column("appointments", "customer_id")

    # Elimina tabella otp_codes
    op.drop_index("ix_otp_codes_email", "otp_codes")
    op.drop_index("ix_otp_codes_id", "otp_codes")
    op.drop_table("otp_codes")

    # Elimina tabella customers
    op.drop_index("ix_customers_email", "customers")
    op.drop_index("ix_customers_id", "customers")
    op.drop_table("customers")


def downgrade() -> None:
    # Ricrea customers
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

    # Ricrea otp_codes
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

    # Ripristina customer_id in appointments
    op.add_column("appointments", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.drop_constraint("fk_appointments_user_id", "appointments", type_="foreignkey")
    op.drop_column("appointments", "user_id")
    op.drop_index("ix_users_email", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")
