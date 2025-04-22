"""Add BroadcastAnalytics model

Revision ID: 49cffdd3bb1c
Revises: 8931dfa3f14f
Create Date: 2025-04-18 19:07:42.418250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49cffdd3bb1c'
down_revision: Union[str, None] = '8931dfa3f14f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create broadcast_analytics table
    op.create_table('broadcast_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('total_sent', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_delivered', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_read', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_cost', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant_tenant.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_broadcast_analytics_id'), 'broadcast_analytics', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop broadcast_analytics table
    op.drop_index(op.f('ix_broadcast_analytics_id'), table_name='broadcast_analytics')
    op.drop_table('broadcast_analytics')