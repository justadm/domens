"""copilot conversations and detailed logs

Revision ID: 0005_copilot_logging
Revises: 0004_access_events
Create Date: 2026-02-18

"""
from __future__ import annotations

from alembic import op

revision = "0005_copilot_logging"
down_revision = "0004_access_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          telegram_user_id TEXT NOT NULL,
          channel TEXT NOT NULL DEFAULT 'web',
          status TEXT NOT NULL DEFAULT 'active',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(telegram_user_id, updated_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_messages (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          telegram_user_id TEXT NOT NULL,
          direction TEXT NOT NULL,
          message_text TEXT NOT NULL,
          intent TEXT,
          confidence NUMERIC(5,4),
          raw_payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_messages_conv ON conversation_messages(conversation_id, created_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS copilot_action_confirmations (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
          telegram_user_id TEXT NOT NULL,
          action_type TEXT NOT NULL,
          action_payload JSONB,
          status TEXT NOT NULL DEFAULT 'pending',
          confirmation_token TEXT NOT NULL UNIQUE,
          expires_at TIMESTAMPTZ NOT NULL,
          result_payload JSONB,
          error_message TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_copilot_confirm_user ON copilot_action_confirmations(telegram_user_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_copilot_confirm_status ON copilot_action_confirmations(status, expires_at)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS copilot_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          telegram_user_id TEXT NOT NULL,
          conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
          confirmation_id UUID REFERENCES copilot_action_confirmations(id) ON DELETE SET NULL,
          event_type TEXT NOT NULL,
          payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_events_user ON copilot_events(telegram_user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_copilot_events_type ON copilot_events(event_type, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS copilot_events CASCADE")
    op.execute("DROP TABLE IF EXISTS copilot_action_confirmations CASCADE")
    op.execute("DROP TABLE IF EXISTS conversation_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")
