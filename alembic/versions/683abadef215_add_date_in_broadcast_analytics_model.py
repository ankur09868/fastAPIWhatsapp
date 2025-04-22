"""add date in broadcast analytics model

Revision ID: 683abadef215
Revises: 49cffdd3bb1c
Create Date: 2025-04-21 18:10:57.306281

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '683abadef215'
down_revision: Union[str, None] = '49cffdd3bb1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('broadcast_analytics', sa.Column('date', sa.Date))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('broadcast_analytics', 'date')
