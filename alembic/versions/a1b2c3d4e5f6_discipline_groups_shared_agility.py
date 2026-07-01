"""discipline_groups_shared_agility

Revision ID: a1b2c3d4e5f6
Revises: f3a8c1d2e4b5
Create Date: 2026-07-01 00:00:00.000000

Crea tabella discipline_groups.
Aggiunge group_id a disciplines e packages.
Rende discipline_id e instructor_id nullable in packages.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3a8c1d2e4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'discipline_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index(op.f('ix_discipline_groups_id'), 'discipline_groups', ['id'], unique=False)

    op.add_column('disciplines', sa.Column('group_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_disciplines_group_id', 'disciplines',
        'discipline_groups', ['group_id'], ['id']
    )

    op.add_column('packages', sa.Column('group_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_packages_group_id', 'packages',
        'discipline_groups', ['group_id'], ['id']
    )

    # Rendi discipline_id e instructor_id nullable nei pacchetti (per pacchetti di gruppo)
    op.alter_column('packages', 'discipline_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('packages', 'instructor_id', existing_type=sa.Integer(), nullable=True)

    # Aggiunge vincolo UNIQUE per pacchetti di gruppo (user_id, group_id)
    op.create_unique_constraint('uq_group_package', 'packages', ['user_id', 'group_id'])


def downgrade() -> None:
    op.drop_constraint('uq_group_package', 'packages', type_='unique')
    op.alter_column('packages', 'instructor_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('packages', 'discipline_id', existing_type=sa.Integer(), nullable=False)
    op.drop_constraint('fk_packages_group_id', 'packages', type_='foreignkey')
    op.drop_column('packages', 'group_id')
    op.drop_constraint('fk_disciplines_group_id', 'disciplines', type_='foreignkey')
    op.drop_column('disciplines', 'group_id')
    op.drop_index(op.f('ix_discipline_groups_id'), table_name='discipline_groups')
    op.drop_table('discipline_groups')
