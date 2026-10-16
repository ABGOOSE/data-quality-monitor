"""Unit tests for checker module."""

import pandas as pd
import pytest

from core.checker import (
    check_allowed_values,
    check_not_null,
    check_null_ratio,
    check_range,
    check_row_count,
    check_unique,
    check_zscore,
    run_checks,
)


def test_not_null_all_valid():
    """When no null values, check should pass."""
    series = pd.Series([1, 2, 3, 4, 5])
    result = check_not_null(series)
    assert result["passed"] is True
    assert result["null_count"] == 0
    assert result["total_count"] == 5
    assert result["null_ratio"] == 0.0


def test_not_null_with_nulls():
    """When null values exist, check should fail and count correctly."""
    series = pd.Series([1, None, 3, None, 5])
    result = check_not_null(series)
    assert result["passed"] is False
    assert result["null_count"] == 2
    assert result["total_count"] == 5
    assert result["null_ratio"] == 0.4


def test_not_null_empty_series():
    """Empty series should pass with zero counts."""
    series = pd.Series([], dtype=float)
    result = check_not_null(series)
    assert result["passed"] is True
    assert result["null_count"] == 0
    assert result["total_count"] == 0
    assert result["null_ratio"] == 0.0


def test_unique_all_distinct():
    """When all non-null values are distinct, check should pass."""
    series = pd.Series([1, 2, 3, 4, 5])
    result = check_unique(series)
    assert result["passed"] is True
    assert result["duplicate_count"] == 0
    assert result["total_count"] == 5
    assert result["duplicate_ratio"] == 0.0


def test_unique_with_duplicates():
    """Duplicates should be counted (second and later occurrences)."""
    series = pd.Series([1, 2, 2, 3, 3, 3])
    result = check_unique(series)
    assert result["passed"] is False
    assert result["duplicate_count"] == 3
    assert result["total_count"] == 6
    assert result["duplicate_ratio"] == 0.5


def test_unique_ignores_nulls():
    """Null values are not considered duplicates."""
    series = pd.Series([None, None, 1])
    result = check_unique(series)
    assert result["passed"] is True
    assert result["duplicate_count"] == 0


def test_unique_empty_series():
    """Empty series should pass with zero counts."""
    series = pd.Series([], dtype=float)
    result = check_unique(series)
    assert result["passed"] is True
    assert result["duplicate_count"] == 0
    assert result["total_count"] == 0


def test_range_all_within():
    """All values within [min, max] should pass."""
    series = pd.Series([1, 5, 100, 1000000])
    result = check_range(series, min_value=0, max_value=1000000)
    assert result["passed"] is True
    assert result["out_of_range_count"] == 0


def test_range_with_outliers():
    """Values below min or above max are violations."""
    series = pd.Series([-1, 5, 2000000])
    result = check_range(series, min_value=0, max_value=1000000)
    assert result["passed"] is False
    assert result["out_of_range_count"] == 2
    assert result["total_count"] == 3


def test_range_boundary_values_pass():
    """Values exactly at min or max are not violations."""
    series = pd.Series([0, 1000000])
    result = check_range(series, min_value=0, max_value=1000000)
    assert result["passed"] is True
    assert result["out_of_range_count"] == 0


def test_range_ignores_nulls():
    """Null values are not range violations."""
    series = pd.Series([None, 5, 100])
    result = check_range(series, min_value=0, max_value=1000000)
    assert result["passed"] is True
    assert result["out_of_range_count"] == 0


def test_range_empty_series():
    """Empty series should pass with zero counts."""
    series = pd.Series([], dtype=float)
    result = check_range(series, min_value=0, max_value=1000000)
    assert result["passed"] is True
    assert result["out_of_range_count"] == 0


# ---------- 表级规则 check_row_count ----------
# 表级规则收的是整个 DataFrame。测法思路和列级一样：通过 / 失败 / 边界 / 空表四件套。
def test_row_count_pass():
    """A table with enough rows should pass."""
    df = pd.DataFrame({"a": [1, 2, 3]})
    result = check_row_count(df, min_rows=1)
    assert result["passed"] is True
    assert result["row_count"] == 3


def test_row_count_fail():
    """A table with too few rows should fail."""
    df = pd.DataFrame({"a": [1]})
    result = check_row_count(df, min_rows=3)
    assert result["passed"] is False
    assert result["row_count"] == 1


def test_row_count_boundary_passes():
    """Exactly min_rows rows is not a violation."""
    # 边界值测试：min_rows 本身是合法的。这类测试专门抓 >= 误写成 > 的 bug
    df = pd.DataFrame({"a": [1, 2]})
    result = check_row_count(df, min_rows=2)
    assert result["passed"] is True


def test_row_count_empty_table():
    """An empty table fails when min_rows > 0."""
    df = pd.DataFrame()
    result = check_row_count(df, min_rows=1)
    assert result["passed"] is False
    assert result["row_count"] == 0


def test_run_checks_all_pass():
    """Clean data should pass all rules."""
    df = pd.DataFrame(
        {
            "order_id": [1, 2, 3],
            "amount": [10.0, 50.0, 999.0],
        }
    )
    table_rules = {
        "columns": {
            "order_id": [{"rule": "not_null"}, {"rule": "unique"}],
            "amount": [{"rule": "range", "min_value": 0, "max_value": 1000000}],
        }
    }
    results = run_checks(df, table_rules)
    assert len(results) == 3
    assert all(r["passed"] for r in results)


def test_run_checks_detects_violations():
    """Violations should be reported per rule."""
    df = pd.DataFrame(
        {
            "order_id": [1, None, 2],
            "amount": [-5.0, 50.0, 2000000.0],
        }
    )
    table_rules = {
        "columns": {
            "order_id": [{"rule": "not_null"}, {"rule": "unique"}],
            "amount": [{"rule": "range", "min_value": 0, "max_value": 1000000}],
        }
    }
    results = run_checks(df, table_rules)
    assert results[0]["rule"] == "not_null" and results[0]["passed"] is False
    assert results[1]["rule"] == "unique" and results[1]["passed"] is True
    assert results[2]["rule"] == "range" and results[2]["passed"] is False


def test_run_checks_skips_missing_columns():
    """Columns not in the DataFrame should be skipped, not crash."""
    df = pd.DataFrame({"order_id": [1, 2]})
    table_rules = {
        "columns": {
            "order_id": [{"rule": "not_null"}],
            "missing_col": [{"rule": "not_null"}],
        }
    }
    results = run_checks(df, table_rules)
    assert len(results) == 1


def test_run_checks_runs_table_rules():
    """Table-level rules in `checks` should also be executed."""
    # columns 故意留空，只放 checks：证明 run_checks 的第二轮（表级）真的在跑
    df = pd.DataFrame({"order_id": [1, 2]})
    table_rules = {
        "columns": {},
        "checks": [{"rule": "row_count", "min_rows": 2}],
    }
    results = run_checks(df, table_rules)
    assert len(results) == 1
    assert results[0]["rule"] == "row_count"
    assert results[0]["passed"] is True
    assert results[0]["column"] is None  # 表级结果没有具体列，column 统一为 None


def test_run_checks_table_rule_fails_on_empty_table():
    """row_count on an empty DataFrame should fail."""
    df = pd.DataFrame({"order_id": pd.Series([], dtype=float)})
    table_rules = {
        "columns": {},
        "checks": [{"rule": "row_count", "min_rows": 1}],
    }
    results = run_checks(df, table_rules)
    assert results[0]["passed"] is False


def test_run_checks_result_carries_column_name():
    """Each column result should carry its column name for reporting."""
    df = pd.DataFrame({"order_id": [1, 2]})
    results = run_checks(df, {"columns": {"order_id": [{"rule": "not_null"}]}})
    assert results[0]["column"] == "order_id"  # 报告输出靠这个键知道结果属于哪一列


def test_run_checks_unknown_column_rule_raises():
    """A declared column rule with no implementation must fail loudly."""
    df = pd.DataFrame({"order_id": [1]})
    table_rules = {"columns": {"order_id": [{"rule": "no_such_rule"}]}}
    # pytest.raises 是上下文管理器：断言 with 块里的代码必须抛出指定异常。
    # match 参数用正则匹配报错信息，防止"抛了 ValueError 但原因完全不对"的假通过
    with pytest.raises(ValueError, match="no_such_rule"):
        run_checks(df, table_rules)


def test_run_checks_unknown_table_rule_raises():
    """A declared table rule with no implementation must fail loudly."""
    # 表级规则遇到未知名字同样要大声报错——两个分派表都必须守住
    df = pd.DataFrame({"order_id": [1]})
    table_rules = {"checks": [{"rule": "no_such_rule"}]}
    with pytest.raises(ValueError, match="no_such_rule"):
        run_checks(df, table_rules)


# ---------- 统计异常检测 check_zscore ----------
# z-score：z = (x - mean) / std，|z| > threshold 的值判为离群。
# 和 range 的区别：边界不是人写的，是数据自己算的（均值±Nσ）。
# 测试六件套：检测 / 正常 / 边界严格> / 数据不足 / 零方差 / 空值
def test_zscore_detects_outliers():
    """An extreme value (|z| > 3) should be flagged as an outlier."""
    # 10 个 10 + 1 个 100：mean≈18.2, std≈27.1 → z(100)≈3.02 > 3
    # 注意：离群值必须真的超出 3σ——值不够极端时 z 会被均值和标准差"稀释"
    series = pd.Series([10.0] * 10 + [100.0])
    result = check_zscore(series)
    assert result["passed"] is False
    assert result["outlier_count"] == 1
    assert result["total_count"] == 11


def test_zscore_normal_data_passes():
    """Small fluctuations around the mean should pass."""
    series = pd.Series([1, 2, 1, 2, 1, 2])
    result = check_zscore(series)
    assert result["passed"] is True
    assert result["outlier_count"] == 0


def test_zscore_boundary_strict():
    """|z| exactly at threshold is NOT an outlier (strict >, not >=)."""
    # mean=2, std=1 → 1 和 3 的 |z| 恰好 = 1.0；threshold=1.0 时不算异常。
    # 这个测试专门抓实现里把 > 误写成 >= 的 bug
    series = pd.Series([1, 2, 3])
    result = check_zscore(series, threshold=1.0)
    assert result["passed"] is True
    assert result["outlier_count"] == 0


def test_zscore_insufficient_data_passes():
    """Fewer than 2 non-null values: std undefined, no evidence, pass."""
    series = pd.Series([5])
    result = check_zscore(series)
    assert result["passed"] is True


def test_zscore_constant_series_passes():
    """All values identical (std=0): no variance, no outliers."""
    series = pd.Series([5, 5, 5, 5])
    result = check_zscore(series)
    assert result["passed"] is True


def test_zscore_ignores_nulls():
    """Null values are not z-score violations (consistent with other rules)."""
    series = pd.Series([None] + [10.0] * 10 + [100.0])
    result = check_zscore(series)
    assert result["passed"] is False
    assert result["outlier_count"] == 1


def test_allowed_values_passes_when_all_in_set():
    """全部值都在允许集合内 → 通过。"""
    series = pd.Series(["pending", "shipped", "delivered"])
    result = check_allowed_values(
        series, allowed_values=["pending", "shipped", "delivered", "cancelled"]
    )
    assert result["passed"] is True
    assert result["disallowed_count"] == 0
    assert result["total_count"] == 3
    assert result["disallowed_ratio"] == 0.0


def test_allowed_values_fails_on_out_of_set():
    """混入集合外的值（拼错的 shippedd）→ 失败，精确数出违规个数。"""
    series = pd.Series(["pending", "shippedd", "delivered"])
    result = check_allowed_values(series, allowed_values=["pending", "shipped", "delivered"])
    assert result["passed"] is False
    assert result["disallowed_count"] == 1
    assert result["disallowed_ratio"] == round(1 / 3, 4)


def test_allowed_values_ignores_null():
    """空值不算违规（空值是"没填"不是"填错"，和 unique/zscore 口径一致）。"""
    series = pd.Series(["pending", None, "cancelled"])
    result = check_allowed_values(series, allowed_values=["pending", "shipped", "cancelled"])
    assert result["passed"] is True
    assert result["disallowed_count"] == 0


# ---------- 缺失率阈值 check_null_ratio ----------
# 和 not_null 的区别：not_null 是"零容忍"（一个空就失败），
# null_ratio 是"有容忍度"（缺失率超过 max_ratio 才失败）。
# 判定口径：null_ratio > max_ratio 才 FAIL；恰好等于 → PASS。
# （max_ratio 是容忍上限，没超就不误报，与 zscore"严格大于"口径一致）
def test_null_ratio_below_threshold_passes():
    """缺失率低于阈值 → 通过。"""
    series = pd.Series([1, None, 3, 4, 5])  # 1 个空 / 5 行 = 0.2
    result = check_null_ratio(series, max_ratio=0.3)
    assert result["passed"] is True
    assert result["null_count"] == 1
    assert result["total_count"] == 5
    assert result["null_ratio"] == 0.2


def test_null_ratio_above_threshold_fails():
    """缺失率超过阈值 → 失败，精确断言比率。"""
    series = pd.Series([None, None, None, 4, 5])  # 3 个空 / 5 行 = 0.6
    result = check_null_ratio(series, max_ratio=0.3)
    assert result["passed"] is False
    assert result["null_count"] == 3
    assert result["total_count"] == 5
    assert result["null_ratio"] == 0.6
    assert result["max_ratio"] == 0.3


def test_null_ratio_boundary_equal_passes():
    """恰好等于 max_ratio → 通过（容忍上限没超，和 zscore 严格> 口径一致）。"""
    series = pd.Series([None, None, 3, 4, 5])  # 2 个空 / 5 行 = 0.4
    result = check_null_ratio(series, max_ratio=0.4)
    assert result["passed"] is True
    assert result["null_ratio"] == 0.4


def test_null_ratio_all_null_does_not_crash():
    """全缺失 → 不崩，比率 1.0，超过任何正常阈值 → 失败。"""
    series = pd.Series([None, None, None])
    result = check_null_ratio(series, max_ratio=0.9)
    assert result["passed"] is False
    assert result["null_count"] == 3
    assert result["null_ratio"] == 1.0


def test_null_ratio_empty_series_passes():
    """空表（0 行）→ 比率 0.0，通过，不除零崩溃。"""
    series = pd.Series([], dtype=float)
    result = check_null_ratio(series, max_ratio=0.5)
    assert result["passed"] is True
    assert result["null_ratio"] == 0.0
