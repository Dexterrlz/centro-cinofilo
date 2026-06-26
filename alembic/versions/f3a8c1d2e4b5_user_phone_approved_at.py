"""user_phone_approved_at

Revision ID: f3a8c1d2e4b5
Revises: edfa62d1ad24
Create Date: 2026-06-26 00:00:00.000000

Aggiunge phone e approved_at agli utenti.
Cambia default is_active a False per nuovi utenti.
Imposta utenti esistenti come attivi con phone placeholder.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a8c1d2e4b5'
down_revision: Union[str, None] = 'edfa62d1ad24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Aggiunge phone con default temporaneo per righe esistenti
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('approved_at', sa.DateTime(), nullable=True))

    # Imposta placeholder per utenti esistenti
    op.execute("UPDATE users SET phone = 'N/A' WHERE phone IS NULL")
    op.execute("UPDATE users SET is_active = TRUE WHERE is_active = FALSE OR is_active IS NULL")
    op.execute("UPDATE users SET approved_at = NOW() WHERE approved_at IS NULL")

    # Rende phone NOT NULL dopo aver riempito le righe esistenti
    op.alter_column('users', 'phone', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'approved_at')
    op.drop_column('users', 'phone')
