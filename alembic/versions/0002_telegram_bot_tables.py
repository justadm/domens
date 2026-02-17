"""telegram bot tables

Revision ID: 0002_telegram_bot_tables
Revises: 0001_init_schema
Create Date: 2026-02-17

"""
from __future__ import annotations

from alembic import op

revision = "0002_telegram_bot_tables"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_users (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          telegram_user_id TEXT NOT NULL UNIQUE,
          telegram_chat_id TEXT,
          username TEXT,
          first_name TEXT,
          locale TEXT,
          is_active BOOLEAN NOT NULL DEFAULT TRUE,
          disclaimer_accepted_at TIMESTAMPTZ,
          disclaimer_version TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_watch_rules (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID NOT NULL REFERENCES telegram_users(id) ON DELETE CASCADE,
          watch_query TEXT NOT NULL,
          tlds JSONB,
          min_score NUMERIC(5,2),
          max_price_usd NUMERIC(12,2),
          status TEXT NOT NULL DEFAULT 'active',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID NOT NULL REFERENCES telegram_users(id) ON DELETE CASCADE,
          channel_type TEXT NOT NULL,
          channel_target TEXT NOT NULL,
          alert_types JSONB,
          status TEXT NOT NULL DEFAULT 'active',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE(user_id, channel_type, channel_target)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID REFERENCES telegram_users(id) ON DELETE SET NULL,
          telegram_chat_id TEXT,
          event_type TEXT NOT NULL,
          payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_bot_events_created_at ON bot_events(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bot_events CASCADE")
    op.execute("DROP TABLE IF EXISTS user_subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS user_watch_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS telegram_users CASCADE")
