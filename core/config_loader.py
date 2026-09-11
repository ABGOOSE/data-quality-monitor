"""Load quality rules from YAML config files."""

from pathlib import Path

import yaml


def load_rules(path: str | Path) -> dict:
    # :后是类型注解
    """Load quality rules from a YAML file.

    Args:
        path: Path to the YAML rules file.

    Returns:
        A dict with rule definitions, e.g.
        {"tables": {"sample_orders": {"columns": {...}, "checks": [...]}}}
    """
    # 上面的是文档字符串，用三引号 """...""" 括起来
    # 它紧跟在函数定义之后，用于说明函数的功能、参数和返回值。
    # docstring 是函数对象的一个属性（__doc__），可以被程序读取、用于自动生成文档或交互式帮助
    # 从 YAML 文件加载质量规则
    # Args:：描述参数 path 的含义。
    # Returns:：描述返回值，并给出示例结
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
    # 调用 yaml.safe_load 解析文件内容（安全的 YAML 加载，避免执行任意代码），并将解析后的 Python 对象（这里是字典）作为函数返回值返回
