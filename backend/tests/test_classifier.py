"""Category classifier tests."""

from app.modules.categories.classifier import (
    CategoryCode,
    Rule,
    RuleField,
    RuleOperator,
    classify,
)


def test_subscription_keyword() -> None:
    assert classify(description="NETFLIX 会员") == CategoryCode.SUBSCRIPTION
    assert classify(description="Spotify premium") == CategoryCode.SUBSCRIPTION


def test_salary_keyword() -> None:
    assert classify(description="代发工资") == CategoryCode.SALARY
    assert classify(description="salary") == CategoryCode.SALARY


def test_rent_keyword() -> None:
    assert classify(description="房租转账") == CategoryCode.RENT


def test_counterparty_field() -> None:
    assert classify(description="消费", counterparty="美团") == CategoryCode.FOOD
    assert classify(description="打车", counterparty="滴滴出行") == CategoryCode.TRANSPORT


def test_counterparty_ignored_for_description_rules() -> None:
    # "工资" appears only in counterparty; description rules ignore it.
    assert classify(description="付款", counterparty="工资卡") == CategoryCode.OTHER


def test_unknown_falls_to_other() -> None:
    assert classify(description="某未知消费") == CategoryCode.OTHER


def test_priority_ordering() -> None:
    rules = [
        Rule(
            10,
            RuleField.DESCRIPTION,
            RuleOperator.CONTAINS,
            "还款",
            CategoryCode.CREDIT_CARD_REPAYMENT,
        ),
        Rule(100, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "转账", CategoryCode.TRANSFER),
    ]
    # "还款转账" matches both; lower priority value (10) must win.
    assert classify(description="还款转账", rules=rules) == CategoryCode.CREDIT_CARD_REPAYMENT


def test_custom_rules_override_defaults() -> None:
    rules = [Rule(1, RuleField.DESCRIPTION, RuleOperator.CONTAINS, "工资", CategoryCode.SHOPPING)]
    assert classify(description="工资", rules=rules) == CategoryCode.SHOPPING


def test_equals_operator() -> None:
    rules = [Rule(1, RuleField.DESCRIPTION, RuleOperator.EQUALS, "salary", CategoryCode.SALARY)]
    assert classify(description="SALARY", rules=rules) == CategoryCode.SALARY
    assert classify(description="salary bonus", rules=rules) == CategoryCode.OTHER
