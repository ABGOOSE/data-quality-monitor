"""Unit tests for checker module."""

import pandas as pd

from core.checker import check_not_null, check_range, check_unique, run_checks


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


def test_run_checks_all_pass():
    """Clean data should pass all rules."""
    df = pd.DataFrame({
        "order_id": [1, 2, 3],
        "amount": [10.0, 50.0, 999.0],
    })
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
    df = pd.DataFrame({
        "order_id": [1, None, 2],
        "amount": [-5.0, 50.0, 2000000.0],
    })
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