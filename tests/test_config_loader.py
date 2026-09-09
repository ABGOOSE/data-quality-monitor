"""Unit tests for config loader."""

import inspect
from pathlib import Path

from core.checker import RULE_FUNCTIONS
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


def test_all_rules_have_implementations():
    """Every rule declared in rules.yaml must exist in RULE_FUNCTIONS."""
    rules = load_rules(RULES_PATH)
    for table in rules["tables"].values():
        for col_rules in table["columns"].values():
            for rule_config in col_rules:
                assert rule_config["rule"] in RULE_FUNCTIONS


def test_rule_params_match_function_signature():
    """Rule params in YAML must match the check function's parameter names."""
    rules = load_rules(RULES_PATH)
    for table in rules["tables"].values():
        for col_rules in table["columns"].values():
            for rule_config in col_rules:
                func = RULE_FUNCTIONS[rule_config["rule"]]
                param_names = set(inspect.signature(func).parameters)
                param_names.discard("series")
                declared = set(rule_config.keys()) - {"rule"}
                assert declared <= param_names, (
                    f"Params {declared - param_names} not accepted by {func.__name__}"
                )
