"""add messages external_id

Revision ID: b7d9a2f1c4a1
Revises: 3e08d1327385
Create Date: 2026-02-04 12:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7d9a2f1c4a1"
down_revision: Union[str, Sequence[str], None] = "3e08d1327385"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("messages", sa.Column("external_id", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_messages_external_id"),
        "messages",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_messages_external_id"), table_name="messages")
    op.drop_column("messages", "external_id")
