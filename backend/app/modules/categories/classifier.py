"""Rule-based transaction classification.

Deterministic rules (description/counterparty keywords) classify a
transaction; the first matching rule by priority wins, otherwise the
transaction falls into ``OTHER``. Rules are meant to be stored per user
later (ClassificationRule) — this module holds the pure engine.
"""

from dataclasses import dataclass
from enum import StrEnum


class CategoryCode(StrEnum):
    SALARY = "SALARY"
    RENT = "RENT"
    FOOD = "FOOD"
    TRANSPORT = "TRANSPORT"
    SHOPPING = "SHOPPING"
    EDUCATION = "EDUCATION"
    SUBSCRIPTION = "SUBSCRIPTION"
    MEDICAL = "MEDICAL"
    INVESTMENT = "INVESTMENT"
    TRANSFER = "TRANSFER"
    REFUND = "REFUND"
    CREDIT_CARD_REPAYMENT = "CREDIT_CARD_REPAYMENT"
    OTHER = "OTHER"


class RuleField(StrEnum):
    DESCRIPTION = "description"
    COUNTERPARTY = "counterparty"


class RuleOperator(StrEnum):
    CONTAINS = "contains"
    EQUALS = "equals"


@dataclass(frozen=True)
class Rule:
    priority: int
    field: RuleField
    operator: RuleOperator
    value: str
    category: CategoryCode


# Lower priority value = applied earlier = wins on conflict.
DEFAULT_RULES: list[Rule] = [
    Rule(100, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "NETFLIX", CategoryCode.SUBSCRIPTION),
    Rule(100, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "SPOTIFY", CategoryCode.SUBSCRIPTION),
    Rule(100, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "ICLOUD", CategoryCode.SUBSCRIPTION),
    Rule(100, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "订阅", CategoryCode.SUBSCRIPTION),
    Rule(200, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "工资", CategoryCode.SALARY),
    Rule(200, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "salary", CategoryCode.SALARY),
    Rule(200, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "代发工资", CategoryCode.SALARY),
    Rule(300, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "房租", CategoryCode.RENT),
    Rule(300, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "租金", CategoryCode.RENT),
    Rule(
        400,
        RuleField.DESCRIPTION,
        RuleOperator.CONTAINS,
        "还款",
        CategoryCode.CREDIT_CARD_REPAYMENT,
    ),
    Rule(
        400,
        RuleField.DESCRIPTION,
        RuleOperator.CONTAINS,
        "信用卡还款",
        CategoryCode.CREDIT_CARD_REPAYMENT,
    ),
    Rule(500, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "退款", CategoryCode.REFUND),
    Rule(500, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "refund", CategoryCode.REFUND),
    Rule(600, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "转入", CategoryCode.TRANSFER),
    Rule(600, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "转出", CategoryCode.TRANSFER),
    Rule(600, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "转账", CategoryCode.TRANSFER),
    Rule(700, RuleField.COUNTERPARTY, RuleOperator.CONTAINS, "美团", CategoryCode.FOOD),
    Rule(700, RuleField.COUNTERPARTY, RuleOperator.CONTAINS, "盒马", CategoryCode.FOOD),
    Rule(700, RuleField.COUNTERPARTY, RuleOperator.CONTAINS, "滴滴", CategoryCode.TRANSPORT),
    Rule(700, RuleField.COUNTERPARTY, RuleOperator.CONTAINS, "地铁", CategoryCode.TRANSPORT),
    Rule(700, RuleField.COUNTERPARTY, RuleOperator.CONTAINS, "星巴克", CategoryCode.FOOD),
]


def classify(
    *,
    description: str,
    counterparty: str | None = None,
    rules: list[Rule] | None = None,
) -> CategoryCode:
    """Classify a transaction, returning the winning category code.

    Rules are applied in priority order; the first match wins. With no
    match the transaction is ``OTHER``.
    """
    active_rules = DEFAULT_RULES if rules is None else rules
    for rule in sorted(active_rules, key=lambda r: r.priority):
        if rule.field == RuleField.DESCRIPTION:
            haystack = (description or "").lower()
        else:
            haystack = (counterparty or "").lower()

        if rule.operator == RuleOperator.CONTAINS:
            if rule.value.lower() in haystack:
                return rule.category
        elif haystack.strip() == rule.value.lower():
            return rule.category
    return CategoryCode.OTHER
