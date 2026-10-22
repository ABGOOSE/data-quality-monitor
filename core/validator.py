"""Validate the structure of loaded rules config.

Schema 校验（配置校验）：在 yaml 加载成字典之后、规则真正运行之前，
把"配置乱写"的问题一次性查出来，挡在最前面（fail-fast）。

校验思路是自顶向下逐层检查：
    顶层 tables → 每个表的 columns/checks → 每条规则的 rule 键 → 规则名是否注册 → 参数是否对齐
"""

# inspect 是 Python 标准库，用来"查看函数长什么样"（比如它有哪些参数、有没有默认值）。
# 这里用它把 yaml 里写的参数键和检查函数的真实签名做对齐校验。
import inspect

# 相对导入：从同一个 core 包里的 checker 模块拿两张规则注册表。
# 列级规则收 Series，表级规则收 DataFrame，所以分成两张表。
from .checker import RULE_FUNCTIONS, TABLE_RULE_FUNCTIONS


def validate_rules(config: dict) -> list[str]:
    """Validate rules config and return a list of human-readable error messages.

    Args:
        config: The dict produced by yaml.safe_load (via load_rules).

    Returns:
        A list of error strings. An empty list means the config is valid.
        收集所有错误一次返回，方便用户一次修完，而不是改一个报一个。
    """
    errors: list[str] = []

    # ---- 第 1 层：顶层结构 ----
    # 整个配置必须是字典（yaml 里最外层是 "tables: ..."）。
    if not isinstance(config, dict):
        # 顶层都不是字典，后面没法继续查，直接返回。
        return [f"Config must be a mapping (dict), got {type(config).__name__}"]

    tables = config.get("tables")
    if tables is None:
        # 连 tables 键都没有，后面无从查起，直接返回。
        return ["Missing required top-level key 'tables'"]

    if not isinstance(tables, dict):
        return [f"'tables' must be a mapping (dict), got {type(tables).__name__}"]

    if not tables:
        # 有 tables 键但是空的（tables: 后面没内容）。
        errors.append("'tables' is empty; define at least one table")

    # ---- 第 2 层：逐个表检查 ----
    for table_name, table_config in tables.items():
        table_path = f"tables.{table_name}"

        if not isinstance(table_config, dict):
            # 表下面必须是一个字典（含 columns、checks）。
            errors.append(
                f"{table_path} must be a mapping (dict), got {type(table_config).__name__}"
            )
            # 这一层结构都不对，跳过它内部的检查。
            continue

        # ---- 列级规则段：columns 必须是字典（列名 -> 规则列表）----
        columns = table_config.get("columns", {})
        if not isinstance(columns, dict):
            errors.append(
                f"{table_path}.columns must be a mapping (dict), got {type(columns).__name__}"
            )
        else:
            for column_name, rule_list in columns.items():
                column_path = f"{table_path}.columns.{column_name}"

                # 每一列下面必须是一个规则列表（yaml 里的 "- rule: ..."）。
                if not isinstance(rule_list, list):
                    errors.append(
                        f"{column_path} must be a list of rules, got {type(rule_list).__name__}"
                    )
                    continue

                # 逐条规则校验（列级注册表）。
                for index, rule_config in enumerate(rule_list):
                    errors.extend(
                        _validate_rule(rule_config, RULE_FUNCTIONS, f"{column_path}[{index}]")
                    )

        # ---- 表级规则段：checks 必须是列表 ----
        checks = table_config.get("checks", [])
        if not isinstance(checks, list):
            errors.append(f"{table_path}.checks must be a list, got {type(checks).__name__}")
        else:
            for index, rule_config in enumerate(checks):
                # 逐条规则校验（表级注册表）。
                errors.extend(
                    _validate_rule(
                        rule_config, TABLE_RULE_FUNCTIONS, f"{table_path}.checks[{index}]"
                    )
                )

    return errors


def _validate_rule(rule_config: object, registry: dict, path: str) -> list[str]:
    """Validate a single rule config against a rule registry.

    Args:
        rule_config: One rule dict, e.g. {"rule": "range", "min_value": 0}.
        registry: The rule-name -> function mapping to check against.
        path: A dotted location string used in error messages to locate the rule.

    Returns:
        A list of error strings (empty if valid).
    """
    errors: list[str] = []

    # 一条规则必须是字典。
    if not isinstance(rule_config, dict):
        return [f"{path} must be a mapping (dict), got {type(rule_config).__name__}"]

    # 必须有 rule 键告诉引擎"这是哪条规则"。
    if "rule" not in rule_config:
        return [f"{path} missing required key 'rule'"]

    rule_name = rule_config["rule"]
    if not isinstance(rule_name, str):
        return [f"{path} 'rule' must be a string, got {type(rule_name).__name__}"]

    # 规则名必须在注册表里（代码里真的实现了这条规则）。
    if rule_name not in registry:
        errors.append(f"{path} unknown rule '{rule_name}'. Available: {sorted(registry)}")
        # 规则都不认识，就没法继续校验它的参数了。
        return errors

    # ---- 参数对齐校验：把 yaml 提供的参数键和函数签名做对比 ----
    function = registry[rule_name]
    signature = inspect.signature(function)
    # 函数的全部参数（含第一个 series/df，以及有默认值的参数）。
    valid_params = set(signature.parameters)

    # yaml 里除 rule 外的键，都是要传给函数的参数。
    provided = {key for key in rule_config if key != "rule"}

    # ① 多余参数：yaml 写了、函数却不认识（最常见的拼写错误，比如把 min_value 写成 min_val）。
    for key in sorted(provided - valid_params):
        errors.append(
            f"{path} rule '{rule_name}' got unexpected parameter '{key}'. "
            f"Valid parameters: {sorted(valid_params)}"
        )

    # ② 缺失参数：函数要求必填（没有默认值）、yaml 却没给。
    for name, parameter in signature.parameters.items():
        # 第一个参数是 series（列级）或 df（表级），由引擎传入，yaml 不提供，跳过。
        is_first = name == next(iter(signature.parameters))
        if is_first:
            continue
        # default 为空表示没有默认值 = 必填。
        is_required = parameter.default is inspect.Parameter.empty
        if is_required and name not in provided:
            errors.append(f"{path} rule '{rule_name}' missing required parameter '{name}'")

    return errors
