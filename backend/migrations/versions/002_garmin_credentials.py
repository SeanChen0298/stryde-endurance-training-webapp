"""Add garmin_email and garmin_tokens_encrypted to athletes

Revision ID: 002
Revises: 001
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("athletes", sa.Column("garmin_email", sa.String(), nullable=True))
    op.add_column("athletes", sa.Column("garmin_tokens_encrypted", sa.String(), nullable=True))


def downgrade():
    op.drop_column("athletes", "garmin_tokens_encrypted")
    op.drop_column("athletes", "garmin_email")
