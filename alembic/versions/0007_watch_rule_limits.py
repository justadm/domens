"""watch rule alert limits

Revision ID: 0007_watch_rule_limits
Revises: 0006_launch_quality
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op

revision = "0007_watch_rule_limits"
down_revision = "0006_launch_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_watch_rules ADD COLUMN IF NOT EXISTS max_length INTEGER")
    op.execute("ALTER TABLE user_watch_rules ADD COLUMN IF NOT EXISTS daily_alert_limit INTEGER NOT NULL DEFAULT 3")


def downgrade() -> None:
    op.execute("ALTER TABLE user_watch_rules DROP COLUMN IF EXISTS daily_alert_limit")
    op.execute("ALTER TABLE user_watch_rules DROP COLUMN IF EXISTS max_length")
