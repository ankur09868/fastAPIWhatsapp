"""create_catalog_table

Revision ID: fe2d0efa51d0
Revises: some_unique_id
Create Date: 2025-04-12 16:25:32.145332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe2d0efa51d0'
down_revision: Union[str, None] = 'some_unique_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create catalogs table
    op.create_table(
        'catalogs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('catalog_id', sa.BigInteger(), nullable=True),
        sa.Column('spreadsheet_link', sa.String(), nullable=False),
        sa.Column('razorpay_key', sa.JSON(), nullable=True),
        sa.Column('tenant_id', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_catalogs_id'), 'catalogs', ['id'], unique=False)
    op.create_index(op.f('ix_catalogs_catalog_id'), 'catalogs', ['catalog_id'], unique=True)
    
    # Check if tenant_tenant table exists before adding foreign key
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'tenant_tenant' in tables:
        # Add foreign key constraint
        op.create_foreign_key(
            'fk_catalogs_tenant', 
            'catalogs', 'tenant_tenant',
            ['tenant_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key first
    try:
        op.drop_constraint('fk_catalogs_tenant', 'catalogs', type_='foreignkey')
    except Exception:
        pass  # If constraint doesn't exist, continue
    
    # Drop indexes
    op.drop_index(op.f('ix_catalogs_catalog_id'), table_name='catalogs')
    op.drop_index(op.f('ix_catalogs_id'), table_name='catalogs')
    
    # Drop table
    op.drop_table('catalogs')
