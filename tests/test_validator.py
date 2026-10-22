"""Tests for core/validator.py config schema validation."""

# 配置校验器的测试：每个测试把"合法配置"改坏某一处，
# 看校验器能不能准确识别并给出能定位的错误信息。
from core.validator import validate_rules

# 一份合法的最小配置：很多测试在它的基础上改坏某一处。
VALID_CONFIG = {
    "tables": {
        "TableA": {
            "columns": {
                "id": [{"rule": "not_null"}, {"rule": "unique"}],
                "amount": [{"rule": "range", "min_value": 0, "max_value": 1000000}],
            },
            "checks": [{"rule": "row_count", "min_rows": 1}],
        }
    }
}


def test_valid_config_has_no_errors():
    """完整合法配置：错误列表为空。"""
    assert validate_rules(VALID_CONFIG) == []


# ---------- 第 1 层：顶层结构 ----------


def test_config_not_a_dict():
    """顶层不是字典（比如是个列表）：报错。"""
    errors = validate_rules(["not", "a", "dict"])
    assert len(errors) == 1
    assert "must be a mapping" in errors[0]


def test_missing_tables_key():
    """没有 tables 键：报错。"""
    errors = validate_rules({"other": 1})
    assert len(errors) == 1
    assert "Missing required top-level key 'tables'" in errors[0]


def test_tables_not_a_dict():
    """tables 不是字典（比如是列表）：报错。"""
    errors = validate_rules({"tables": []})
    assert len(errors) == 1
    assert "'tables' must be a mapping" in errors[0]


def test_tables_empty():
    """tables 为空：报错。"""
    errors = validate_rules({"tables": {}})
    assert len(errors) == 1
    assert "is empty" in errors[0]


# ---------- 第 2 层：表级结构 ----------


def test_table_config_not_a_dict():
    """某个表下面不是字典：报错且定位到该表。"""
    config = {"tables": {"Bad": ["not", "a", "dict"]}}
    errors = validate_rules(config)
    assert any("tables.Bad must be a mapping" in e for e in errors)


def test_columns_not_a_dict():
    """columns 不是字典（比如是列表）：报错。"""
    config = {"tables": {"T": {"columns": []}}}
    errors = validate_rules(config)
    assert any("tables.T.columns must be a mapping" in e for e in errors)


def test_column_rule_list_not_a_list():
    """某一列下面不是规则列表（比如直接给了字典）：报错。"""
    config = {"tables": {"T": {"columns": {"col": {"rule": "not_null"}}}}}
    errors = validate_rules(config)
    assert any("columns.col must be a list" in e for e in errors)


def test_checks_not_a_list():
    """checks 不是列表：报错。"""
    config = {"tables": {"T": {"checks": {"rule": "row_count"}}}}
    errors = validate_rules(config)
    assert any("tables.T.checks must be a list" in e for e in errors)


# ---------- 第 3 层：规则本身 ----------


def test_rule_not_a_dict():
    """规则列表里的元素不是字典：报错。"""
    config = {"tables": {"T": {"columns": {"col": ["not_null"]}}}}
    errors = validate_rules(config)
    assert any("must be a mapping" in e for e in errors)


def test_rule_missing_rule_key():
    """规则字典缺 rule 键：报错。"""
    config = {"tables": {"T": {"columns": {"col": [{"min_value": 1}]}}}}
    errors = validate_rules(config)
    assert any("missing required key 'rule'" in e for e in errors)


def test_rule_name_not_string():
    """rule 的值不是字符串：报错。"""
    config = {"tables": {"T": {"columns": {"col": [{"rule": 123}]}}}}
    errors = validate_rules(config)
    assert any("'rule' must be a string" in e for e in errors)


def test_unknown_column_rule():
    """列级规则名未注册：报错并列出可用规则。"""
    config = {"tables": {"T": {"columns": {"col": [{"rule": "nope"}]}}}}
    errors = validate_rules(config)
    assert any("unknown rule 'nope'" in e for e in errors)


def test_unknown_table_rule():
    """表级规则名未注册：报错。"""
    config = {"tables": {"T": {"checks": [{"rule": "nope"}]}}}
    errors = validate_rules(config)
    assert any("unknown rule 'nope'" in e for e in errors)


# ---------- 第 4 层：参数对齐 ----------


def test_unexpected_parameter():
    """yaml 写了函数不认识的参数（拼写错误，如 min_val）：报错。"""
    config = {
        "tables": {"T": {"columns": {"col": [{"rule": "range", "min_val": 0, "max_value": 1}]}}}
    }
    errors = validate_rules(config)
    assert any("unexpected parameter 'min_val'" in e for e in errors)


def test_missing_required_parameter():
    """函数必填参数（range 要 min_value/max_value）没给全：报错。"""
    config = {"tables": {"T": {"columns": {"col": [{"rule": "range", "min_value": 0}]}}}}
    errors = validate_rules(config)
    assert any("missing required parameter 'max_value'" in e for e in errors)


def test_optional_parameter_can_be_omitted():
    """有默认值的参数（zscore 的 threshold、row_count 的 min_rows）省略：不报错。"""
    config = {
        "tables": {
            "T": {
                "columns": {"col": [{"rule": "zscore"}]},
                "checks": [{"rule": "row_count"}],
            }
        }
    }
    assert validate_rules(config) == []
