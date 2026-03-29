"""Add light_sleep, awake_count, sleep_stress, body_battery_at_wake, sleep_score_insight to health_metrics

Revision ID: 003
Revises: 002
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("health_metrics", sa.Column("light_sleep_minutes", sa.Integer(), nullable=True))
    op.add_column("health_metrics", sa.Column("awake_count", sa.Integer(), nullable=True))
    op.add_column("health_metrics", sa.Column("sleep_stress_avg", sa.Float(), nullable=True))
    op.add_column("health_metrics", sa.Column("body_battery_at_wake", sa.Integer(), nullable=True))
    op.add_column("health_metrics", sa.Column("sleep_score_insight", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("health_metrics", "sleep_score_insight")
    op.drop_column("health_metrics", "body_battery_at_wake")
    op.drop_column("health_metrics", "sleep_stress_avg")
    op.drop_column("health_metrics", "awake_count")
    op.drop_column("health_metrics", "light_sleep_minutes")
