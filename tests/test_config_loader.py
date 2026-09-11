"""Unit tests for config loader."""

import inspect
from pathlib import Path

from core.checker import RULE_FUNCTIONS, TABLE_RULE_FUNCTIONS
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


# ---------- 契约测试（contract tests）----------
# 什么是契约：rules.yaml 和代码之间的一份"约定"——
# YAML 里声明的每条规则，代码里必须有同名实现；声明的每个参数，函数签名必须能接收。
# 普通单测查"函数行为对不对"，契约测试查"配置和代码有没有脱节"。
# 这类错误最容易拖到运行时才暴露（规则被静默跳过），所以放进 CI 每次自动查。
def test_all_rules_have_implementations():
    """Every rule declared in rules.yaml must exist in a RULE_FUNCTIONS dict.

    Covers both column rules (`columns`) and table rules (`checks`).
    """
    rules = load_rules(RULES_PATH)
    for table in rules["tables"].values():
        for col_rules in table["columns"].values():
            for rule_config in col_rules:
                assert rule_config["rule"] in RULE_FUNCTIONS
        for check_config in table.get("checks", []):
            assert check_config["rule"] in TABLE_RULE_FUNCTIONS


def test_rule_params_match_function_signature():
    """Rule params in YAML must match the check function's parameter names."""
    rules = load_rules(RULES_PATH)
    for table in rules["tables"].values():
        for col_rules in table["columns"].values():
            for rule_config in col_rules:
                _assert_params_match(rule_config, RULE_FUNCTIONS[rule_config["rule"]])
        for check_config in table.get("checks", []):
            _assert_params_match(check_config, TABLE_RULE_FUNCTIONS[check_config["rule"]])


def _assert_params_match(rule_config: dict, func) -> None:
    """Assert every param declared in YAML is accepted by the check function.

    The first positional parameter (series / df) is the data being checked,
    not a YAML-declared param, so it is excluded from the comparison.
    """
    # inspect.signature 是"反射"：运行时把函数签名读出来当数据用，
    # 拿到它声明了哪些参数名，再和 YAML 里声明的键名做差集比较
    signature = inspect.signature(func)
    # 第一个参数（series / df）是"被检查的数据"本身，不是 YAML 要声明的参数，
    # 所以从参数集合里去掉它，剩下的才参与比较
    data_param = next(iter(signature.parameters))
    param_names = set(signature.parameters) - {data_param}
    declared = set(rule_config.keys()) - {"rule"}
    assert declared <= param_names, (
        f"Params {declared - param_names} not accepted by {func.__name__}"
    )
