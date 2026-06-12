"""launch quality tracking

Revision ID: 0006_launch_quality
Revises: 0005_copilot_logging
Create Date: 2026-06-12
"""
from __future__ import annotations

from alembic import op

revision = "0006_launch_quality"
down_revision = "0005_copilot_logging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE alerts
        ADD COLUMN IF NOT EXISTS explanation JSONB,
        ADD COLUMN IF NOT EXISTS delivery_payload JSONB
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_feedback (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
          telegram_user_id TEXT,
          feedback_type TEXT NOT NULL,
          payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_feedback_alert ON alert_feedback(alert_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_feedback_user ON alert_feedback(telegram_user_id, created_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_suppressions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          fqdn TEXT NOT NULL,
          destination TEXT NOT NULL,
          reason TEXT NOT NULL,
          status TEXT,
          score NUMERIC(5,2),
          expires_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(fqdn, destination, reason)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_alert_suppressions_lookup ON alert_suppressions(fqdn, destination, expires_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alert_suppressions CASCADE")
    op.execute("DROP TABLE IF EXISTS alert_feedback CASCADE")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS delivery_payload")
    op.execute("ALTER TABLE alerts DROP COLUMN IF EXISTS explanation")
