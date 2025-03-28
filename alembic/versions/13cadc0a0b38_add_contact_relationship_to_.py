"""Add contact relationship to notifications

Revision ID: some_unique_id
Revises: previous_revision_id
Create Date: 2025-03-28 19:00:00.123456
"""

from alembic import op
import sqlalchemy as sa

# Revision identifiers
revision = "some_unique_id"
down_revision = None # Update this with the actual previous migration ID
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade schema: Add contact_id column to notifications"""
    op.add_column("notifications", sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts_contact.id"), nullable=True))


def downgrade():
    """Downgrade schema: Remove contact_id column from notifications"""
    op.drop_column("notifications", "contact_id")
