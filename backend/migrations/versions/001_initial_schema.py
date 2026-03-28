"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector must run outside a transaction block
    with op.get_context().autocommit_block():
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # athletes
    op.create_table(
        "athletes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("strava_athlete_id", sa.BigInteger(), unique=True),
        sa.Column("garmin_user_id", sa.String(), unique=True),
        sa.Column("timezone", sa.String(), server_default="Asia/Kuala_Lumpur"),
        sa.Column("goal_race_type", sa.String()),
        sa.Column("goal_race_date", sa.Date()),
        sa.Column("goal_finish_time_seconds", sa.Integer()),
        sa.Column("gemini_api_key_encrypted", sa.String()),
        sa.Column("gemini_model", sa.String(), server_default="gemini-2.5-flash"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # oauth_tokens
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("scope", sa.String()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # activities
    op.create_table(
        "activities",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("external_id", sa.String()),
        sa.Column("activity_type", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("distance_meters", sa.Float()),
        sa.Column("elevation_gain_meters", sa.Float()),
        sa.Column("avg_hr", sa.Integer()),
        sa.Column("max_hr", sa.Integer()),
        sa.Column("avg_pace_seconds_per_km", sa.Float()),
        sa.Column("avg_cadence", sa.Integer()),
        sa.Column("avg_power", sa.Integer()),
        sa.Column("hr_zone_distribution", JSONB()),
        sa.Column("splits", JSONB()),
        sa.Column("workout_type", sa.String()),
        sa.Column("perceived_effort", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("gear_id", sa.String()),
        sa.Column("raw_metadata", JSONB()),
        sa.UniqueConstraint("source", "external_id"),
    )

    # health_metrics
    op.create_table(
        "health_metrics",
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("recorded_date", sa.Date(), primary_key=True),
        sa.Column("hrv_rmssd", sa.Float()),
        sa.Column("hrv_sdrr", sa.Float()),
        sa.Column("resting_hr", sa.Integer()),
        sa.Column("sleep_score", sa.Integer()),
        sa.Column("sleep_duration_minutes", sa.Integer()),
        sa.Column("deep_sleep_minutes", sa.Integer()),
        sa.Column("rem_sleep_minutes", sa.Integer()),
        sa.Column("sleep_start", sa.DateTime(timezone=True)),
        sa.Column("sleep_end", sa.DateTime(timezone=True)),
        sa.Column("body_battery_max", sa.Integer()),
        sa.Column("body_battery_min", sa.Integer()),
        sa.Column("stress_avg", sa.Integer()),
        sa.Column("steps", sa.Integer()),
        sa.Column("spo2_avg", sa.Float()),
        sa.Column("respiratory_rate", sa.Float()),
        sa.Column("training_readiness_score", sa.Integer()),
    )

    # readiness_scores
    op.create_table(
        "readiness_scores",
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score_date", sa.Date(), primary_key=True),
        sa.Column("readiness_score", sa.Float()),
        sa.Column("hrv_delta_pct", sa.Float()),
        sa.Column("sleep_delta_pct", sa.Float()),
        sa.Column("load_delta_pct", sa.Float()),
        sa.Column("ai_summary", sa.Text()),
        sa.Column("ai_recommendation", sa.Text()),
    )

    # training_plans
    op.create_table(
        "training_plans",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("goal_race_type", sa.String()),
        sa.Column("goal_race_date", sa.Date()),
        sa.Column("goal_time_seconds", sa.Integer()),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("plan_summary", sa.Text()),
        sa.Column("revision_reason", sa.Text()),
        sa.Column("weekly_structure", JSONB()),
    )

    # planned_workouts
    op.create_table(
        "planned_workouts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("training_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("workout_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("target_distance_meters", sa.Float()),
        sa.Column("target_duration_minutes", sa.Integer()),
        sa.Column("target_pace_min_seconds_per_km", sa.Float()),
        sa.Column("target_pace_max_seconds_per_km", sa.Float()),
        sa.Column("target_hr_zone", sa.Integer()),
        sa.Column("target_rpe", sa.Integer()),
        sa.Column("intensity_points", sa.Float()),
        sa.Column("completed", sa.Boolean(), server_default="false"),
        sa.Column("completed_activity_id", sa.String(), sa.ForeignKey("activities.id")),
        sa.Column("calendar_event_id", sa.String()),
        sa.Column("garmin_workout_id", sa.String()),
    )

    # gear
    op.create_table(
        "gear",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strava_gear_id", sa.String(), unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("brand", sa.String()),
        sa.Column("model", sa.String()),
        sa.Column("distance_meters", sa.Float(), server_default="0"),
        sa.Column("max_distance_meters", sa.Float(), server_default="800000"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("purchased_at", sa.Date()),
        sa.Column("retired_at", sa.Date()),
    )

    # activity_embeddings (with pgvector)
    op.create_table(
        "activity_embeddings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("activity_id", sa.String(), sa.ForeignKey("activities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.String(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE activity_embeddings ADD COLUMN embedding VECTOR(384)")
    op.execute("CREATE INDEX ON activity_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)")

    # knowledge_embeddings (with pgvector)
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source", sa.String()),
        sa.Column("chunk_index", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE knowledge_embeddings ADD COLUMN embedding VECTOR(384)")
    op.execute("CREATE INDEX ON knowledge_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50)")

    # Indexes
    op.create_index("idx_activities_athlete_date", "activities", ["athlete_id", sa.text("started_at DESC")])
    op.create_index("idx_health_athlete_date", "health_metrics", ["athlete_id", sa.text("recorded_date DESC")])
    op.create_index("idx_planned_athlete_date", "planned_workouts", ["athlete_id", "scheduled_date"])

    # Materialized view for weekly mileage (standard PostgreSQL — no TimescaleDB needed)
    op.execute("""
        CREATE MATERIALIZED VIEW weekly_mileage AS
        SELECT
            athlete_id,
            date_trunc('week', started_at) AS week,
            SUM(distance_meters) / 1000 AS km,
            SUM(duration_seconds) / 3600.0 AS hours,
            AVG(avg_hr) AS avg_hr,
            COUNT(*) AS activity_count
        FROM activities
        WHERE activity_type = 'run'
        GROUP BY athlete_id, week
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS weekly_mileage")
    op.drop_table("knowledge_embeddings")
    op.drop_table("activity_embeddings")
    op.drop_table("gear")
    op.drop_table("planned_workouts")
    op.drop_table("training_plans")
    op.drop_table("readiness_scores")
    op.drop_table("health_metrics")
    op.drop_table("activities")
    op.drop_table("oauth_tokens")
    op.drop_table("athletes")
