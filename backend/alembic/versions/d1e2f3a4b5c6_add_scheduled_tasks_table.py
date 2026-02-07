"""add scheduled_tasks table

Revision ID: d1e2f3a4b5c6
Revises: bc4f440c9498
Create Date: 2026-02-07 08:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'bc4f440c9498'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create scheduled_tasks table."""
    op.create_table(
        'scheduled_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_type', sa.String(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(), server_default='pending', nullable=True),
        sa.Column('payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_tasks_status'), 'scheduled_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_scheduled_tasks_scheduled_time'), 'scheduled_tasks', ['scheduled_time'], unique=False)


def downgrade() -> None:
    """Drop scheduled_tasks table."""
    op.drop_index(op.f('ix_scheduled_tasks_scheduled_time'), table_name='scheduled_tasks')
    op.drop_index(op.f('ix_scheduled_tasks_status'), table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')
