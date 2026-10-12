"""Command-line entry point: dqm --table <name> --data <csv>.

把「读配置 -> 读数据 -> 跑检查 -> 打印结果」串成一条完整链路，
将来接 Airflow 定时调度、面试现场 demo 用的都是这个入口。
新增规则时 cli **一行都不用改**—— 因为它不拥有规则知识
"""

import argparse  # 命令行参数解析器，读懂用户敲了什么命令          进入命令
import sys  # 是「访问 Python 解释器本身」的接口，你和解释器的对讲机      退出码、错误通道
from datetime import datetime  # 生成报告文件名的时间戳
from pathlib import Path  # 路径处理

import pandas as pd  # 读 CSV

from core.checker import run_checks  # 从 core/checker.py 里导入 run_checks 函数，负责执行检查逻辑
from core.config_loader import (
    load_rules,  # 从 core/config_loader.py 里导入 load_rules 函数，负责加载规则配置
)
from core.reporter import (
    export_report,  # 从 core/reporter.py 里导入 export_report，负责把结果导出成报告文件（--report 用）
)

# 2 个常量：DEFAULT_CONFIG（配置文件在哪）、_META_KEYS（哪些键是元信息）
# 默认配置文件路径：用 __file__ 动态定位，而不是写死相对路径。
# __file__ 是当前文件的路径；.resolve() 转成绝对路径；
# .parents[1] 是"上一级的上一级"——parents[0] 是 core/，parents[1] 就是项目根。
# 这样无论从哪个目录运行 dqm，都能找到 config/rules.yaml。
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "rules.yaml"  # 配置yaml文件的路径

# 结果字典里的"元信息"键：它们描述这条结果本身（什么规则、过没过、哪一列），
# 不是检查出来的指标（如 null_count）。格式化输出时跳过，只展示真正的指标。
_META_KEYS = {"rule", "passed", "column"}


# ============ 业务区 1：声明命令收哪些参数 ============
# 函数① build_parser()：声明 dqm 收哪些参数（--table / --data / --config）
def build_parser() -> argparse.ArgumentParser:  # 为 dqm 命令构建 argparse 解析器。
    """Build the argparse parser for the dqm command.

    argparse 三件套：创建解析器 -> add_argument 声明参数 -> parse_args 解析。
    声明参数后，--help 说明、缺参报错、拼错参数名提示都是白送的，不用自己写 if。
    """
    # prog 和 description 会出现在 --help 输出里
    # 调用其他工具包的函数，然后用参数传参
    parser = (
        argparse.ArgumentParser(  # argparse.ArgumentParser(...) 是 Python 标准库里早就写好的一个类
            prog="dqm",
            description="Run data quality checks defined in rules.yaml against a CSV file.",
        )
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
    # --report：把检查结果导出成文件（json 给程序、markdown 给人），不传就只打印终端。
    # choices 限制取值范围：传别的值 argparse 直接报错退出（退出码 2）
    parser.add_argument(
        "--report",
        choices=["json", "markdown"],
        help="Export results to a report file: json (machine-readable) or markdown (human-readable)",
    )
    # --output：报告输出路径，配合 --report 使用；不传就自动命名
    parser.add_argument(
        "--output",
        type=Path,
        help="Report output path (used with --report; default: report_<table>_<timestamp>.json/md)",
    )
    return parser


# 一个无参数、有返回值、无副作用的工厂函数——典型的"创建 → 配置 → 返回"三步结构
#  ┌──────────┬──────────────────────────────┬───────────────────────────────────────────────────────────────────┐
#  │   步骤   │             代码             │                               说明                                │
#  ├──────────┼──────────────────────────────┼───────────────────────────────────────────────────────────────────┤
#  │ 创建对象 │ argparse.ArgumentParser(...) │ 造出一个空解析器                                                  │
#  ├──────────┼──────────────────────────────┼───────────────────────────────────────────────────────────────────┤
#  │ 配置对象 │ .add_argument(...) 调三次    │ 声明三个参数（--table、--data、--config），注意这时并没有读命令行 │
#  ├──────────┼──────────────────────────────┼───────────────────────────────────────────────────────────────────┤
#  │ 返回对象 │ return parser                │ 把配好的解析器交给调用者                                          │
#  └──────────┴──────────────────────────────┴───────────────────────────────────────────────────────────────────┘


def _default_report_path(table: str, fmt: str) -> Path:
    """没传 --output 时自动命名：report_<表名>_<时间戳>.<后缀>，放在当前目录。

    时间戳用 %Y%m%d_%H%M%S 保证文件名唯一（同一表同一秒跑两次才会撞名）。
    """
    ext = "json" if fmt == "json" else "md"
    # astimezone() 加本地时区，满足 ruff DTZ005；strftime 只取年月日时分秒做文件名
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    return Path.cwd() / f"report_{table}_{timestamp}.{ext}"


def render_results(table: str, results: list[dict]) -> str:
    # 函数② render_results()：把结果列表格式化成「[PASS] order_id :: not_null (...)」
    """Format check results as terminal-friendly text.

    Example:
        [PASS] order_id :: not_null  (null_count=0, total_count=3)
        [FAIL] amount :: range  (out_of_range_count=1, ...)
        [FAIL] table :: row_count  (row_count=0, min_rows=1)
    """
    lines = [f"Table: {table}", "-" * 60]  # 样式美化用的
    ##['Table: 2', '------------------------------------------------------------']
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


# ============ 固定骨架：总指挥五段式（基本不用改） ============
def main(argv: list[str] | None = None) -> int:
    # 函数③ main()：总指挥，五段式（解析→加载→校验→执行→收尾）
    """Run the CLI and return the process exit code.

    Exit codes:
        0 = all checks passed
        1 = at least one check failed (CI / 调度系统靠它判断)
        2 = usage error (表不存在、文件找不到等)
    """
    # argv 参数平时是 None，parse_args 自己去读真正的命令行给；
    # 测试时可以传 ["--table", "x", "--data", "y"] 模拟命令行，不用真的起子进程
    args = build_parser().parse_args(
        argv
    )  # 得到一个装满目标参数的特制容器args，这三个参数就是前面定义的build_parser
    """
    parser = build_parser()            # 第 1 步：调函数，拿回 parser 对象
    args = parser.parse_args(argv)     # 第 2 步：调对象的方法，拿回 args
    args = ...                         # 第 3 步：存起来
    """
    rules = load_rules(args.config)
    # 检验表名
    if args.table not in rules.get("tables", {}):  # 字典.get(键, 默认值)是字典的安全取值方法看【
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
    # ---- 结果导出（可选）：--report 指定格式，--output 指定路径 ----
    # 放在打印之后：终端报告照常显示，导出是额外的留档动作。
    # 注意：导出不影响退出码——有检查失败仍然返回 1，CI 判断不变。
    if args.report:
        output = args.output or _default_report_path(args.table, args.report)
        export_report(results, args.report, output, args.table)
        print(f"Report written to {output}")
    # all() + 生成器表达式：所有结果都 passed 才返回 True。
    # main 返回的数字会被 sys.exit 转成进程退出码——退出码就是 CLI 和 CI 之间的"协议"
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    # 开关：if __name__ == "__main__" → sys.exit(main())
    # 这个 if 的作用：python -m core.cli 时执行 main；被 import 时只拿函数不执行。
    # sys.exit(数字) 把数字变成进程退出码，CI / 调度系统靠它判断这次检查成败。
    sys.exit(main())
#  ③④ 步的 return 2 = 命令没跑成（表名写错 / 文件找不到）→ 老板要查命令
# ⑦ 的 return 1 = 检查跑完了但数据不合格 → 老板要查数据
# —— CI 靠这个数字决定：是修命令，还是催人修数据
