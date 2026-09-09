"""Unit tests for config loader."""

from pathlib import Path

from core.config_loader import load_rules

# tests/ 的上一级就是项目根，用 __file__ 定位，不依赖运行目录
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "config" / "rules.yaml"


def test_load_rules_returns_dict():
    """Loading the real rules.yaml should return a dict."""
    rules = load_rules(RULES_PATH)
    assert isinstance(rules, dict)
    assert "tables" in rules


def test_load_rules_structure():
    """The loaded dict should match the YAML structure."""
    rules = load_rules(RULES_PATH)
    order_id_rules = rules["tables"]["sample_orders"]["columns"]["order_id"]
    assert order_id_rules[0]["rule"] == "not_null"
    assert order_id_rules[1]["rule"] == "unique"
    amount_rules = rules["tables"]["sample_orders"]["columns"]["amount"]
    assert amount_rules[0]["min_value"] == 0
    assert amount_rules[0]["max_value"] == 1000000
