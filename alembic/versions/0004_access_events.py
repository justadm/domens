"""access events audit table

Revision ID: 0004_access_events
Revises: 0003_roles_and_user_roles
Create Date: 2026-02-18

"""
from __future__ import annotations

from alembic import op

revision = "0004_access_events"
down_revision = "0003_roles_and_user_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS access_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          actor_user_id UUID REFERENCES telegram_users(id) ON DELETE SET NULL,
          target_user_id UUID REFERENCES telegram_users(id) ON DELETE SET NULL,
          action TEXT NOT NULL,
          role_code TEXT,
          payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_access_events_created_at ON access_events(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_access_events_action ON access_events(action)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_access_events_actor ON access_events(actor_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_access_events_target ON access_events(target_user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS access_events CASCADE")
