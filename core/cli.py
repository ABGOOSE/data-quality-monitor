"""Command-line entry point: dqm --table <name> --data <csv>.

把「读配置 -> 读数据 -> 跑检查 -> 打印结果」串成一条完整链路，
将来接 Airflow 定时调度、面试现场 demo 用的都是这个入口。
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from core.checker import run_checks
from core.config_loader import load_rules

# 默认配置文件路径：用 __file__ 动态定位，而不是写死相对路径。
# __file__ 是当前文件的路径；.resolve() 转成绝对路径；
# .parents[1] 是"上一级的上一级"——parents[0] 是 core/，parents[1] 就是项目根。
# 这样无论从哪个目录运行 dqm，都能找到 config/rules.yaml。
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "rules.yaml"

# 结果字典里的"元信息"键：它们描述这条结果本身（什么规则、过没过、哪一列），
# 不是检查出来的指标（如 null_count）。格式化输出时跳过，只展示真正的指标。
_META_KEYS = {"rule", "passed", "column"}


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for the dqm command.

    argparse 三件套：创建解析器 -> add_argument 声明参数 -> parse_args 解析。
    声明参数后，--help 说明、缺参报错、拼错参数名提示都是白送的，不用自己写 if。
    """
    # prog 和 description 会出现在 --help 输出里
    parser = argparse.ArgumentParser(
        prog="dqm",
        description="Run data quality checks defined in rules.yaml against a CSV file.",
    )
    # 每个 add_argument 声明一个命令行参数；required=True 表示不传就直接报错退出
    parser.add_argument("--table", required=True, help="Table name defined in rules.yaml")
    parser.add_argument("--data", required=True, help="Path to the CSV data file")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        # type=Path：argparse 自动把字符串转成 Path 对象；
        # default：用户不传 --config 时就用项目自带的 rules.yaml
        help=f"Path to rules.yaml (default: {DEFAULT_CONFIG})",
    )
    return parser


def render_results(table: str, results: list[dict]) -> str:
    """Format check results as terminal-friendly text.

    Example:
        [PASS] order_id :: not_null  (null_count=0, total_count=3)
        [FAIL] amount :: range  (out_of_range_count=1, ...)
        [FAIL] table :: row_count  (row_count=0, min_rows=1)
    """
    lines = [f"Table: {table}", "-" * 60]
    for result in results:
        # 三元表达式：一行版的 if-else，条件为真取前面，为假取后面
        status = "PASS" if result["passed"] else "FAIL"
        target = result["column"] if result["column"] is not None else "table"
        # 生成器表达式 + join：遍历结果字典，跳过 rule/passed/column 三个元信息键，
        # 把剩下的指标键值对拼成 "null_count=0, total_count=3" 这样的明细串
        detail = ", ".join(
            f"{key}={value}" for key, value in result.items() if key not in _META_KEYS
        )
        # f-string：{result['rule']} 会把变量值嵌进字符串（注意外层用了双引号，里面就得用单引号）
        line = f"[{status}] {target} :: {result['rule']}"
        if detail:
            line += f"  ({detail})"
        lines.append(line)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code.

    Exit codes:
        0 = all checks passed
        1 = at least one check failed (CI / 调度系统靠它判断)
        2 = usage error (表不存在、文件找不到等)
    """
    # argv 参数平时是 None，parse_args 自己去读真正的命令行；
    # 测试时可以传 ["--table", "x", "--data", "y"] 模拟命令行，不用真的起子进程
    args = build_parser().parse_args(argv)

    rules = load_rules(args.config)
    if args.table not in rules.get("tables", {}):
        # 错误信息走 stderr（错误输出通道），检查报告走 stdout（标准输出通道）。
        # 两个通道分开，脚本和 CI 才能把"正常输出"和"报错"分别捕获。
        print(f"Error: table '{args.table}' not found in {args.config}", file=sys.stderr)
        return 2

    try:
        df = pd.read_csv(args.data)
    except FileNotFoundError:
        # 捕获文件不存在的异常，打印一行人能看懂的错误，
        # 而不是让用户面对一整屏 traceback
        print(f"Error: data file not found: {args.data}", file=sys.stderr)
        return 2

    results = run_checks(df, rules["tables"][args.table])
    print(render_results(args.table, results))
    # all() + 生成器表达式：所有结果都 passed 才返回 True。
    # main 返回的数字会被 sys.exit 转成进程退出码——退出码就是 CLI 和 CI 之间的"协议"
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    # 这个 if 的作用：python -m core.cli 时执行 main；被 import 时只拿函数不执行。
    # sys.exit(数字) 把数字变成进程退出码，CI / 调度系统靠它判断这次检查成败。
    sys.exit(main())
