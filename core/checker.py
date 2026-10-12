"""Data quality check engine."""

import pandas as pd


def check_not_null(series: pd.Series) -> dict:
    # 返回注解：-> dict 表示这个函数返回字典，注释作用
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
    # `series.isna()`：把每个元素变成布尔掩码
    return {
        "rule": "not_null",
        "passed": null_count == 0,  # 这是一个布尔值判断
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
    # 返回的是一个字典。


def check_range(series: pd.Series, min_value: float, max_value: float) -> dict:
    # 等效于def check_range(series, min_value, max_value)
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


# 第一条表级规则：和列级规则不同，它收到的不是一列 Series，而是整个 DataFrame。
# 列级规则回答"这一列干净吗"，表级规则回答"这张表本身健康吗"（行数够不够、表是不是空的）。
def check_row_count(df: pd.DataFrame, min_rows: int = 1) -> dict:
    # min_rows: int = 1 是默认参数：调用方不传就用 1，YAML 里省略这个键也不会报错
    """Check if a DataFrame has at least min_rows rows.

    Args:
        df: DataFrame to check (table-level rule, receives the whole table).
        min_rows: Minimum number of rows required (inclusive).

    Returns:
        A dict with check result:
        - passed: True if the table has at least min_rows rows
        - row_count: actual number of rows
        - min_rows: the threshold used for the check
    """
    # len(df) 拿到行数。DataFrame 能被 len() 测量，是因为 pandas 实现了它的 __len__ 魔法方法
    row_count = len(df)
    return {
        "rule": "row_count",
        "passed": row_count >= min_rows,
        "row_count": row_count,
        "min_rows": min_rows,
    }


# 统计异常检测规则：z = (x - mean) / std，|z| > threshold 的值判为离群。
# 和 range 的区别：边界不是人写的，是数据自己算的（均值±Nσ），
# 适合"不知道正常范围是多少"的列（流量、延迟、成交量）。
# 注意 z-score 的弱点：离群值本身会拉高 mean 和 std，所以它适合
# 主体数据集中的场景；主体被污染时可能"稀释"掉离群信号。
def check_zscore(series: pd.Series, threshold: float = 3.0) -> dict:
    """Check if any non-null value deviates from the mean by more than threshold stds.

    Args:
        series: A pandas Series to check.
        threshold: |z| above this value is an outlier (default 3 = 3σ rule).

    Returns:
        A dict with check result:
        - passed: True if no outlier
        - outlier_count: number of values with |z| > threshold
        - total_count: total number of rows
        - outlier_ratio: ratio of outliers
        - threshold: the threshold used for the check
    """
    total_count = len(series)
    # 和其他规则一致：null 归 not_null 管，这里只看非空值
    non_null = series.dropna().astype(float)
    # 非空值不足 2 个：标准差算不出来，没有足够证据说异常 → 通过
    if len(non_null) < 2:
        return {
            "rule": "zscore",
            "passed": True,
            "outlier_count": 0,
            "total_count": total_count,
            "outlier_ratio": 0.0,
            "threshold": threshold,
        }
    mean = non_null.mean()
    std = non_null.std()
    # 标准差为 0（所有值相同）：没有波动就没有异常 → 通过
    if std == 0:
        return {
            "rule": "zscore",
            "passed": True,
            "outlier_count": 0,
            "total_count": total_count,
            "outlier_ratio": 0.0,
            "threshold": threshold,
        }
    # 向量化：整列一次性算 z 分数，不用 for 循环（pandas 广播）
    z_scores = ((non_null - mean) / std).abs()
    # 严格 > threshold：|z| 恰好等于阈值不算异常（边界测试守住这个行为）
    outlier_count = int((z_scores > threshold).sum())
    return {
        "rule": "zscore",
        "passed": outlier_count == 0,
        "outlier_count": outlier_count,
        "total_count": total_count,
        "outlier_ratio": round(outlier_count / total_count, 4) if total_count > 0 else 0,
        "threshold": threshold,
    }


# 枚举值检查规则：列的值必须属于给定集合（订单状态、渠道、性别这种"只能填固定几项"的列）。
# 和 range 的区别：range 管数值边界（大小），allowed_values 管枚举集合（是不是这几个选项之一）。
# 设计决策：空值不算违规——空值是"没填"，不是"填错了"，归 not_null 管。
def check_allowed_values(series: pd.Series, allowed_values: list) -> dict:
    """Check if non-null values belong to the allowed value set.

    Args:
        series: A pandas Series to check.
        allowed_values: List of allowed values, e.g. ["pending", "shipped"].

    Returns:
        A dict with check result:
        - passed: True if no non-null value is outside the allowed set
        - disallowed_count: number of values not in the allowed set
        - total_count: total number of rows
        - disallowed_ratio: ratio of disallowed values
        - allowed_values: the allowed set used for the check
    """
    total_count = len(series)
    # 和其他列级规则一致：空值归 not_null 管，这里只看非空值
    non_null = series.dropna()
    # ~ 是"取反"：isin(allowed_values) 得到"在集合里"的布尔掩码，
    # 取反后就是"不在集合里"的违规掩码，.sum() 数违规个数
    disallowed_count = int((~non_null.isin(allowed_values)).sum())
    return {
        "rule": "allowed_values",
        "passed": disallowed_count == 0,
        "disallowed_count": disallowed_count,
        "total_count": total_count,
        "disallowed_ratio": round(disallowed_count / total_count, 4) if total_count > 0 else 0,
        # 转成 list：YAML 里可能是元组/列表，统一成 list 保证 JSON 报告能序列化
        "allowed_values": list(allowed_values),
    }


# 分派表：列级规则名 -> 检查函数（函数接收一列 Series）
# YAML 里的 "rule: not_null" 是字符串，字符串不能直接调用，
# 必须靠这个字典把字符串翻译成对应的函数——这就是"分派"的含义。
# 以后加新规则 = 写一个函数 + 在这里登记一行，run_checks 一行都不用改。
RULE_FUNCTIONS = {
    "not_null": check_not_null,
    "unique": check_unique,
    "range": check_range,
    "zscore": check_zscore,
    "allowed_values": check_allowed_values,
}

# 表级分派表：单独一张表，因为函数签名不同——收 DataFrame，不是 Series。
# 两张表分开，run_checks 才知道该把整张表还是某一列传给函数。
TABLE_RULE_FUNCTIONS = {
    "row_count": check_row_count,
}


def run_checks(df: pd.DataFrame, table_rules: dict) -> list[dict]:
    """Run all column and table rules from a table config against a DataFrame.

    Args:
        df: DataFrame to check.
        table_rules: Table rule config from rules.yaml, e.g.
            {"columns": {"order_id": [{"rule": "not_null"}, ...]},
             "checks": [{"rule": "row_count", "min_rows": 1}]}

    Returns:
        A list of check result dicts (one per rule). Column rule results
        carry a "column" key; table rule results carry "column": None.

    Raises:
        ValueError: If the config declares a rule that has no implementation
            in RULE_FUNCTIONS / TABLE_RULE_FUNCTIONS. 配置里写了规则但代码
            没有实现，必须大声报错，而不是静默跳过。
    """
    results = []
    # ---- 第一轮：列级规则，每条规则作用在对应的一列上 ----
    for column, rules in table_rules.get("columns", {}).items():
        # 用 .get("columns", {}) 而不是 ["columns"]：
        # 配置里没写 columns 段时返回空字典，循环直接跳过，不会 KeyError
        # 配置声明了但数据里没有这列 → 跳过不报错（有专门的测试守住这个行为）
        if column not in df.columns:
            continue
        series = df[column]
        for rule_config in rules:
            rule_name = rule_config["rule"]
            if rule_name not in RULE_FUNCTIONS:
                # 配置写了规则、代码没实现 → 必须大声报错，而不是静默跳过。
                # 监控工具最危险的失败方式就是"你以为在查，其实没查"，
                # 数据质量问题会悄悄漏掉，所以这里宁可崩溃也不假装通过。
                raise ValueError(
                    f"Unknown rule '{rule_name}' for column '{column}'. "
                    f"Available: {sorted(RULE_FUNCTIONS)}"
                )
            # 字典推导式：{"rule": "range", "min_value": 0, "max_value": 1000000}
            # 去掉 "rule" 键后剩下 {"min_value": 0, "max_value": 1000000}，
            # 这正好就是检查函数要收的参数。所以 YAML 里的参数键名必须和函数签名对齐。
            params = {key: value for key, value in rule_config.items() if key != "rule"}
            func = RULE_FUNCTIONS[rule_name]
            # **params 是字典解包：func(series, **{"min_value": 0, "max_value": 1000000})
            # 等价于 func(series, min_value=0, max_value=1000000)
            result = func(series, **params)
            # 往结果字典里补一个元信息键：报告输出时才知道这条结果属于哪一列
            result["column"] = column
            results.append(result)
    # ---- 第二轮：表级规则，每条规则作用在整个表上 ----
    for rule_config in table_rules.get("checks", []):
        # .get("checks", []) 默认空列表：没配表级规则就什么都不做
        rule_name = rule_config["rule"]
        if rule_name not in TABLE_RULE_FUNCTIONS:
            raise ValueError(
                f"Unknown table rule '{rule_name}'. Available: {sorted(TABLE_RULE_FUNCTIONS)}"
            )
        params = {key: value for key, value in rule_config.items() if key != "rule"}
        func = TABLE_RULE_FUNCTIONS[rule_name]
        # 和列级规则唯一的区别：这里传的是整张 df
        result = func(df, **params)
        # 统一 schema：列级结果有 "column" 键，表级结果也有，只是值为 None。
        # CLI 输出时只用一套写法：column 是 None 就显示 "table"
        result["column"] = None
        results.append(result)
    return results
