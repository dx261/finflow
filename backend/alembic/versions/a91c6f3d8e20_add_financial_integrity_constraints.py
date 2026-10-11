"""add financial integrity constraints

Revision ID: a91c6f3d8e20
Revises: 37a05fae7d04
Create Date: 2026-09-13
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a91c6f3d8e20"
down_revision: str | None = "37a05fae7d04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_accounts_minimum_balance_nonnegative", "accounts", "minimum_balance >= 0"
    )
    op.create_check_constraint("ck_payment_plans_amount_positive", "payment_plans", "amount > 0")
    op.create_unique_constraint(
        "uq_payment_plans_recurring_occurrence",
        "payment_plans",
        ["source_recurring_id", "occurrence_date"],
    )
    op.create_check_constraint(
        "ck_fund_allocations_amount_positive", "fund_allocations", "allocated_amount > 0"
    )
    op.create_check_constraint("ck_cash_flow_plans_amount_positive", "cash_flow_plans", "amount > 0")
    op.create_check_constraint(
        "ck_recurring_payments_amount_positive", "recurring_payments", "amount > 0"
    )
    op.create_check_constraint(
        "ck_recurring_payments_day_of_month",
        "recurring_payments",
        "day_of_month >= 1 AND day_of_month <= 31",
    )
    op.create_check_constraint(
        "ck_recurring_payments_date_range",
        "recurring_payments",
        "end_date IS NULL OR end_date >= start_date",
    )
    op.create_check_constraint(
        "ck_transactions_amount_nonnegative", "transactions", "amount >= 0"
    )
    op.create_unique_constraint(
        "uq_transactions_account_fingerprint",
        "transactions",
        ["account_id", "fingerprint"],
    )
    op.create_check_constraint(
        "ck_transaction_relations_distinct_transactions",
        "transaction_relations",
        "source_transaction_id <> target_transaction_id",
    )
    op.create_check_constraint(
        "ck_transaction_relations_confidence_range",
        "transaction_relations",
        "confidence >= 0 AND confidence <= 1",
    )
    op.create_unique_constraint(
        "uq_transaction_relations_pair_type",
        "transaction_relations",
        ["source_transaction_id", "target_transaction_id", "relation_type"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transaction_relations_pair_type", "transaction_relations", type_="unique"
    )
    op.drop_constraint(
        "ck_transaction_relations_confidence_range", "transaction_relations", type_="check"
    )
    op.drop_constraint(
        "ck_transaction_relations_distinct_transactions", "transaction_relations", type_="check"
    )
    op.drop_constraint("uq_transactions_account_fingerprint", "transactions", type_="unique")
    op.drop_constraint("ck_transactions_amount_nonnegative", "transactions", type_="check")
    op.drop_constraint("ck_recurring_payments_date_range", "recurring_payments", type_="check")
    op.drop_constraint("ck_recurring_payments_day_of_month", "recurring_payments", type_="check")
    op.drop_constraint("ck_recurring_payments_amount_positive", "recurring_payments", type_="check")
    op.drop_constraint("ck_cash_flow_plans_amount_positive", "cash_flow_plans", type_="check")
    op.drop_constraint("ck_fund_allocations_amount_positive", "fund_allocations", type_="check")
    op.drop_constraint("uq_payment_plans_recurring_occurrence", "payment_plans", type_="unique")
    op.drop_constraint("ck_payment_plans_amount_positive", "payment_plans", type_="check")
    op.drop_constraint("ck_accounts_minimum_balance_nonnegative", "accounts", type_="check")
