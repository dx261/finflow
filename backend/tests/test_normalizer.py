"""normalize_text tests."""

from app.modules.statements.parsers.normalizer import normalize_text


def test_none_becomes_empty() -> None:
    assert normalize_text(None) == ""


def test_plan_example_chinese_colon() -> None:
    # " Posting Date： " -> "postingdate"
    assert normalize_text(" Posting Date： ") == "postingdate"


def test_chinese_header_with_colon() -> None:
    assert normalize_text("交易日期：") == "交易日期"


def test_english_colon_and_case() -> None:
    assert normalize_text("Amount: ") == "amount"
    assert normalize_text("AmOuNt") == "amount"


def test_newlines_collapsed() -> None:
    assert normalize_text("摘要\n第二行") == "摘要第二行"


def test_zero_width_space_removed() -> None:
    assert normalize_text("​账户余额") == "账户余额"


def test_ideographic_space_removed() -> None:
    assert normalize_text(" 余额　") == "余额"


def test_punctuation_removed() -> None:
    assert normalize_text("贷方金额 / 借方金额") == "贷方金额借方金额"
