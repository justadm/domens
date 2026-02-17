"""init schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-02-17

"""
from __future__ import annotations

from pathlib import Path

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def _read_sql_schema() -> str:
    migration_file = Path(__file__).resolve()
    project_root = migration_file.parents[2]
    schema_path = project_root / "docs" / "db_schema.sql"
    return schema_path.read_text(encoding="utf-8")


def upgrade() -> None:
    sql = _read_sql_schema()
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS registration_orders CASCADE")
    op.execute("DROP TABLE IF EXISTS registrar_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS alerts CASCADE")
    op.execute("DROP TABLE IF EXISTS domain_status_history CASCADE")
    op.execute("DROP TABLE IF EXISTS watchlist_domains CASCADE")
    op.execute("DROP TABLE IF EXISTS domains CASCADE")
    op.execute("DROP TABLE IF EXISTS watchlists CASCADE")
    op.execute("DROP TYPE IF EXISTS registration_status")
    op.execute("DROP TYPE IF EXISTS domain_status")
