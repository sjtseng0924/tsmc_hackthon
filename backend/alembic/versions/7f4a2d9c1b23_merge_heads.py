"""merge heads

Revision ID: 7f4a2d9c1b23
Revises: c0be9d4e74ab, d1e2f3a4b5c6
Create Date: 2026-02-06 23:45:00.000000

"""
from typing import Sequence, Union

# no-op merge migration

revision: str = "7f4a2d9c1b23"
down_revision: Union[str, Sequence[str], None] = ("c0be9d4e74ab", "d1e2f3a4b5c6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge heads."""
    pass


def downgrade() -> None:
    """Downgrade merge."""
    pass
