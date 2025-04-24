"""add prompt in whatsapp_chat_whatsapptenantdata

Revision ID: 05e503ea3df1
Revises: 683abadef215
Create Date: 2025-04-23 17:23:50.258551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05e503ea3df1'
down_revision: Union[str, None] = '683abadef215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'whatsapp_chat_whatsapptenantdata',
        sa.Column('prompt', sa.String(length=250), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whatsapp_chat_whatsapptenantdata', 'prompt')
