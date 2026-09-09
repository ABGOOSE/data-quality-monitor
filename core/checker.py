"""Data quality check engine."""

import pandas as pd


def check_not_null(series: pd.Series) -> dict:
    #返回注解：-> dict 表示这个函数返回字典，注释作用
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
    #`series.isna()`：把每个元素变成布尔掩码
    return {
        "rule": "not_null",
        "passed": null_count == 0,
        "null_count": null_count,
        "total_count": total_count,
        "null_ratio": round(null_count / total_count, 4) if total_count > 0 else 0,
    }


def check_unique(series: pd.Series) -> dict:
    """Check if a series contains duplicate non-null values.

    Args:
        series: A pandas Series to check.

    Returns:
        A dict with check result:
        - passed: True if no duplicates among non-null values
        - duplicate_count: number of duplicated occurrences (2nd and later)
        - total_count: total number of rows
        - duplicate_ratio: ratio of duplicated occurrences
    """
    total_count = len(series)
    non_null = series.dropna()
    duplicate_count = int(non_null.duplicated().sum())
    return {
        "rule": "unique",
        "passed": duplicate_count == 0,
        "duplicate_count": duplicate_count,
        "total_count": total_count,
        "duplicate_ratio": round(duplicate_count / total_count, 4) if total_count > 0 else 0,
    }


def check_range(series: pd.Series, min_value: float, max_value: float) -> dict:
    """Check if non-null values fall within [min_value, max_value].

    Args:
        series: A pandas Series to check.
        min_value: Lower bound (inclusive).
        max_value: Upper bound (inclusive).

    Returns:
        A dict with check result:
        - passed: True if no value is out of range
        - out_of_range_count: number of values outside the range
        - total_count: total number of rows
        - out_of_range_ratio: ratio of out-of-range values
        - min_value / max_value: the bounds used for the check
    """
    total_count = len(series)
    non_null = series.dropna()
    out_of_range_count = int(((non_null < min_value) | (non_null > max_value)).sum())
    return {
        "rule": "range",
        "passed": out_of_range_count == 0,
        "out_of_range_count": out_of_range_count,
        "total_count": total_count,
        "out_of_range_ratio": round(out_of_range_count / total_count, 4) if total_count > 0 else 0,
        "min_value": min_value,
        "max_value": max_value,
    }


RULE_FUNCTIONS = {
    "not_null": check_not_null,
    "unique": check_unique,
    "range": check_range,
}


def run_checks(df: pd.DataFrame, table_rules: dict) -> list[dict]:
    """Run all column rules from a table config against a DataFrame.

    Args:
        df: DataFrame to check.
        table_rules: Table rule config from rules.yaml, e.g.
            {"columns": {"order_id": [{"rule": "not_null"}, ...]}}

    Returns:
        A list of check result dicts (one per rule).
    """
    results = []
    for column, rules in table_rules.get("columns", {}).items():
        if column not in df.columns:
            continue
        series = df[column]
        for rule_config in rules:
            rule_name = rule_config["rule"]
            if rule_name not in RULE_FUNCTIONS:
                continue
            params = {key: value for key, value in rule_config.items() if key != "rule"}
            func = RULE_FUNCTIONS[rule_name]
            results.append(func(series, **params))
    return results