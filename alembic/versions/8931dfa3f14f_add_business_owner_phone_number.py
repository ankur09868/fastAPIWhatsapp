"""add_business_owner_phone_number

Revision ID: 8931dfa3f14f
Revises: fe2d0efa51d0
Create Date: 2025-04-14 16:24:19.335597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8931dfa3f14f'
down_revision: Union[str, None] = 'fe2d0efa51d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the business_owner_phone_number column to the catalogs table
    op.add_column('catalogs', 
                  sa.Column('business_owner_phone_number', sa.String(20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the column if downgrading
    op.drop_column('catalogs', 'business_owner_phone_number')