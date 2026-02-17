"""roles and user_roles

Revision ID: 0003_roles_and_user_roles
Revises: 0002_telegram_bot_tables
Create Date: 2026-02-17

"""
from __future__ import annotations

from alembic import op

revision = "0003_roles_and_user_roles"
down_revision = "0002_telegram_bot_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          code TEXT NOT NULL UNIQUE,
          title TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_roles (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id UUID NOT NULL REFERENCES telegram_users(id) ON DELETE CASCADE,
          role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
          granted_by TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE(user_id, role_id)
        )
        """
    )

    op.execute(
        """
        INSERT INTO roles(code, title)
        VALUES
          ('viewer', 'Viewer'),
          ('operator', 'Operator'),
          ('admin', 'Admin'),
          ('superadmin', 'Superadmin')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_roles CASCADE")
    op.execute("DROP TABLE IF EXISTS roles CASCADE")
