"""add currency to cash flow plans

Revision ID: c42e81b79f10
Revises: a91c6f3d8e20
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c42e81b79f10"
down_revision: str | None = "a91c6f3d8e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cash_flow_plans",
        sa.Column("currency", sa.String(length=3), server_default="CNY", nullable=False),
    )
    op.alter_column("cash_flow_plans", "currency", server_default=None)


def downgrade() -> None:
    op.drop_column("cash_flow_plans", "currency")
