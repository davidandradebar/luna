from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.rules import RuleNotFoundError, load_rules, resolve_rule

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def rules():
    return load_rules(FIXTURES / "labor_rules.json")


def test_all_fixture_rules_are_marked_unverified(rules):
    assert all(r.verification_status == "por_verificar" for r in rules)


def test_resolves_rule_by_effective_date(rules):
    before = resolve_rule(rules, "monthly_ordinary_hours_divisor", "private", date(2026, 1, 1))
    after = resolve_rule(rules, "monthly_ordinary_hours_divisor", "private", date(2026, 8, 1))
    assert before.value == 220
    assert after.value == 210


def test_surcharge_changes_over_time(rules):
    key = "sunday_holiday_surcharge"
    assert resolve_rule(rules, key, "private", date(2026, 12, 1)).value == Decimal("0.9")
    assert resolve_rule(rules, key, "private", date(2027, 7, 1)).value == 1


def test_regime_is_respected(rules):
    rule = resolve_rule(rules, "max_weekly_hours", "public_dual", date(2026, 12, 1))
    assert rule.value == 66


def test_tenant_rule_only_applies_to_its_tenant(rules):
    rule = resolve_rule(
        rules, "max_consecutive_nights", "private", date(2026, 12, 1), tenant_id="tenant_demo"
    )
    assert rule.value == 3
    with pytest.raises(RuleNotFoundError):
        resolve_rule(rules, "max_consecutive_nights", "private", date(2026, 12, 1))


def test_missing_rule_raises(rules):
    with pytest.raises(RuleNotFoundError):
        resolve_rule(rules, "max_weekly_hours", "private", date(2020, 1, 1))
