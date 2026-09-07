"""Data quality check engine."""

import pandas as pd


def check_not_null(series: pd.Series) -> dict:
    """Check if a series contains null values.

    Args:
        series: A pandas Series to check.

    Returns:
        A dict with check result:
        - passed: True if no null values
        - null_count: number of null values
        - total_count: total number of rows
        - null_ratio: ratio of null values
    """
    total_count = len(series)
    null_count = int(series.isna().sum())
    return {
        "rule": "not_null",
        "passed": null_count == 0,
        "null_count": null_count,
        "total_count": total_count,
        "null_ratio": round(null_count / total_count, 4) if total_count > 0 else 0,
    }