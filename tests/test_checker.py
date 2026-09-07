"""Unit tests for checker module."""

import pandas as pd

from core.checker import check_not_null


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