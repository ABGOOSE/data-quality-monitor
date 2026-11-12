"""Command-line entry point: dqm --table <name> --data <csv>.

把「读配置 -> 读数据 -> 跑检查 -> 打印结果」串成一条完整链路，
将来接 Airflow 定时调度、面试现场 demo 用的都是这个入口。
新增规则时 cli **一行都不用改**—— 因为它不拥有规则知识
"""

import argparse  # 命令行参数解析器，读懂用户敲了什么命令          进入命令
import sys  # 是「访问 Python 解释器本身」的接口，你和解释器的对讲机      退出码、错误通道
from datetime import datetime  # 生成报告文件名的时间戳
from pathlib import Path  # 路径处理

from sqlalchemy.exc import SQLAlchemyError  # 数据库错误的基类，用来统一捕获连接/读表失败

from core.checker import run_checks  # 从 core/checker.py 里导入 run_checks 函数，负责执行检查逻辑
from core.config_loader import (
    load_rules,  # 从 core/config_loader.py 里导入 load_rules 函数，负责加载规则配置
)
from core.data_loader import (
    load_dataframe,  # 从 core/data_loader.py 导入统一数据加载，CSV 或数据库都读成 DataFrame
)
from core.reporter import (
    export_report,  # 单表报告导出（--report 用）
    export_report_multi,  # 多表分组报告导出（一次查多张表时用）
)
from core.validator import (
    validate_rules,  # 从 core/validator.py 导入配置校验，加载后先体检，把配置错误挡在入口
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

    # parser.add_argument("--table", nargs="+") 的意思是：
    # “以后命令行里出现 --table a b c，就把它后面的值收集成 ['a','b','c']，存到 args.table 这个属性上；
    # --help 里也自动带上这条说明；用户拼错成 --tabel 时自动报错。”
    # parser.add_mutually_exclusive_group(...) 是什么
    # add_argument 是往容器里加“参数”；add_mutually_exclusive_group 是往容器里加“一圈约束”，这圈约束里装的是若干个参数，
    # 规则是“最多只能有一个出现”。

    # 表选择：三种方式三选一（互斥组）。
    #   --table TableA TableB   指定一张或多张表（nargs="+" 把多个值收集成列表）
    #   --all                   检查 rules.yaml 里配置的所有表
    #   --tables-file t.txt     从文件读表名（每行一个，#注释、空行忽略），表多时用
    # required=True：三个都不传时 argparse 直接报错退出（退出码 2）。
    table_group = parser.add_mutually_exclusive_group(required=True)
    table_group.add_argument(
        "--table",
        nargs="+",  # 接收一个或多个值，args.table 是 list[str]
        help="One or more table names defined in rules.yaml",
    )
    table_group.add_argument(
        "--all",
        action="store_true",  # 出现这个开关就为 True，不接值
        help="Check all tables defined in rules.yaml",
    )
    table_group.add_argument(
        "--tables-file",
        type=Path,  # argparse 自动转成 Path 对象
        help="Path to a file listing target tables, one per line (# for comments, blank lines ignored)",
    )
    # 数据源三选一：--data 直接给 CSV、--data-file 从文件读 CSV 清单、--db 走数据库。
    # --data 用 nargs="+"：多表时传多个文件，顺序和 --table 一一对应。
    # --data-file 和 --tables-file 对称：文件里每行一个 CSV 路径，#注释、空行忽略，文件多时用。
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--data",
        nargs="+",
        help="CSV file paths, one per table; order must match --table",
    )
    source_group.add_argument(
        "--data-file",
        type=Path,  # argparse 自动转成 Path 对象
        help="Path to a file listing CSV paths, one per line (# for comments, blank lines ignored)",
    )
    source_group.add_argument(
        "--db",
        help="Database connection URL, e.g. sqlite:///data/demo.db or "
        "mysql+pymysql://user:pass@host:3306/db",
    )
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
    # --dry-run：预检（preflight），只列出哪些表有规则、哪些没有，
    # 不读数据、不跑检查、不导出，用于正式跑之前确认范围，避免漏表/误判。
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preflight: only show which tables have rules; do not run checks",
    )
    # --skip-missing：宽松模式（lenient），无规则的表跳过并警告，继续查有规则的表；
    # 不传时默认严格（strict）：有无规则表就报错 return 2。
    parser.add_argument(
        "--skip-missing",
        action="store_true",
        help="Lenient mode: skip tables without rules (warn instead of failing)",
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
    # 显式分支，不允许未知格式静默兜底成 md（和 export_report 的 fail-fast 口径一致）
    if fmt == "json":
        ext = "json"
    elif fmt == "markdown":
        ext = "md"
    else:
        raise ValueError(f"Unknown report format '{fmt}'. Available: json, markdown")
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


def _read_list_file(path: Path) -> list[str]:
    """从文件读清单：每行一个条目，忽略空行和 # 开头的注释行。

    通用工具：--tables-file 用它读表名、--data-file 用它读 CSV 路径，逻辑完全一样。
    条目多时命令行太长，放文件里更好维护、可进 git。
    文件不存在由调用方（main）捕获 FileNotFoundError 并报退出码 2。
    """
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):  # 空行、注释行跳过
            continue
        items.append(line)
    return items


def _build_dry_run_report(
    requested: list[str],
    valid: list[str],
    missing: list[str],
    db_url: str | None,
    csv_files: list[str] | None,
) -> str:
    """生成预检（dry-run）文本：只展示范围，不执行任何检查。

    分三块：请求了哪些表、哪些有规则（会查）、哪些没规则（需处理），最后说明数据源。
    """
    lines = [
        "[DRY-RUN] Preflight check — no data is read and no checks are executed.",
        "-" * 60,
        f"Requested tables: {len(requested)}",
        "",
        f"Tables WITH rules ({len(valid)}):",
    ]
    if valid:
        lines.extend(f"  [ok] {t}" for t in valid)
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append(f"Tables WITHOUT rules ({len(missing)}):")
    if missing:
        lines.extend(f"  [missing] {t}" for t in missing)
    else:
        lines.append("  (none)")
    lines.append("")
    # 数据源说明：数据库连接串，或 CSV 文件个数
    if db_url:
        lines.append(f"Data source: database ({db_url})")
    else:
        lines.append(f"Data source: {len(csv_files)} CSV file(s)")
    return "\n".join(lines)


def _write_missing_report(
    missing: list[str],
    available: list[str],
    config_path: Path,
    reason: str,
) -> Path:
    """把"无规则表"清单写成文件留存，返回文件路径。

    终端输出会消失，文件用于事后审计/追责。
    reason："strict"（严格模式，拒绝）或 "lenient"（宽松模式，跳过）。
    """
    now = datetime.now().astimezone()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    path = Path.cwd() / f"missing_tables_{timestamp}.txt"
    lines = [
        "Data Quality Monitor — Missing Tables Report",
        "=" * 60,
        f"Generated at: {now.isoformat()}",
        f"Rules file:   {config_path}",
        f"Reason:       {reason}",
        "-" * 60,
        f"Tables without rules ({len(missing)}):",
    ]
    lines.extend(f"  - {t}" for t in missing)
    lines.append("-" * 60)
    lines.append("Tables available in rules.yaml:")
    lines.extend(f"  - {t}" for t in available)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _run_one_table(
    table: str,
    csv_path: str | None,
    args: argparse.Namespace,
    rules: dict,
) -> tuple[list[dict], str | None]:
    """读一张表的数据并跑检查，供 main 循环调用。

    把"读数据 + 跑检查"这两步封装起来，main 只管循环和聚合，不用关心每张表怎么读。

    Returns:
        (results, None)：成功，results 是这张表的检查结果列表。
        ([], 错误信息)：读数据失败（文件找不到 / 数据库连接失败），main 据此 return 2。
    """
    try:
        df = load_dataframe(csv_path=csv_path, db_url=args.db, table_name=table)
    except FileNotFoundError:
        return [], f"data file not found: {csv_path}"
    except SQLAlchemyError as exc:
        return [], f"failed to read table '{table}' from database: {exc}"
    results = run_checks(df, rules["tables"][table])
    return results, None


# ============ 固定骨架：总指挥（解析→加载→校验→循环执行→收尾） ============
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

    # 配置 schema 校验：加载后立刻体检，把"配置乱写"的问题挡在最前面。
    config_errors = validate_rules(rules)
    if config_errors:
        for error in config_errors:
            print(f"Config error: {error}", file=sys.stderr)
        return 2

    available_tables = rules.get("tables", {})
    # 确定"原始请求"的表名单：三种方式三选一
    if args.all:
        requested_tables = list(available_tables.keys())
    elif args.tables_file is not None:
        try:
            requested_tables = _read_list_file(args.tables_file)
        except FileNotFoundError:
            print(f"Error: tables file not found: {args.tables_file}", file=sys.stderr)
            return 2
    else:
        requested_tables = list(args.table)  # nargs="+" 已经是 list

    if not requested_tables:
        print("Error: no table to check (config defines no tables)", file=sys.stderr)
        return 2

    # 分成有规则（valid）和无规则（missing）两组；missing 去重保序。
    valid_tables = [t for t in requested_tables if t in available_tables]
    missing_tables = list(dict.fromkeys(t for t in requested_tables if t not in available_tables))

    # 统一解析 CSV 数据源（三种来源归一为 csv_files，数据库模式为 None）：
    #   --db        → None（按表名读库）
    #   --data-file → 从文件读 CSV 路径清单
    #   --data      → 直接用命令行给的路径
    if args.db:
        csv_files = None
    elif args.data_file is not None:
        try:
            csv_files = _read_list_file(args.data_file)
        except FileNotFoundError:
            print(f"Error: data file list not found: {args.data_file}", file=sys.stderr)
            return 2
    else:
        csv_files = list(args.data)  # nargs="+" 已经是 list

    # ① 预检：只打印范围清单，不读数据、不检查、不导出
    if args.dry_run:
        print(
            _build_dry_run_report(
                requested_tables, valid_tables, missing_tables, args.db, csv_files
            )
        )
        return 1 if missing_tables else 0

    # ② 处理无规则表：宽松模式跳过，严格模式报错（默认严格）
    if missing_tables:
        if args.skip_missing:
            # 先把缺失表清单写成文件留存（即使下面全跳过也有记录）
            missing_path = _write_missing_report(
                missing_tables,
                list(available_tables),
                args.config,
                "lenient mode — tables without rules are skipped",
            )
            print(
                f"Warning: skipping {len(missing_tables)} table(s) without rules:",
                file=sys.stderr,
            )
            for t in missing_tables:
                print(f"  [skip] {t}", file=sys.stderr)
            print(f"Missing tables report written to {missing_path}", file=sys.stderr)
            if not valid_tables:
                # 跳完一张有效表都不剩，没法继续
                print("Error: no valid table left to check after skipping", file=sys.stderr)
                return 2
            target_tables = valid_tables
        else:
            # 严格模式：先写缺失表文件留存，再结构化列出并终止
            missing_path = _write_missing_report(
                missing_tables,
                list(available_tables),
                args.config,
                "strict mode — tables without rules are rejected",
            )
            print(
                f"Error: {len(missing_tables)} table(s) have no rules in {args.config}:",
                file=sys.stderr,
            )
            for t in missing_tables:
                print(f"  [missing] {t}", file=sys.stderr)
            print(
                f"Tables defined in rules.yaml: {', '.join(available_tables)}",
                file=sys.stderr,
            )
            print(f"Missing tables report written to {missing_path}", file=sys.stderr)
            return 2
    else:
        target_tables = valid_tables  # 全部有效

    # ③ 准备每张表的数据来源（csv_files 已统一，无论来自 --data 还是 --data-file）
    if csv_files is not None:
        # 文件数按"原始请求表数"校验；再用"表→文件"映射，只取实际要查的表的文件
        # （这样跳过某表时，它对应的文件也一起排除，不会错位）
        if len(csv_files) != len(requested_tables):
            print(
                f"Error: CSV data expects {len(requested_tables)} file(s) for "
                f"{len(requested_tables)} table(s), but got {len(csv_files)}",
                file=sys.stderr,
            )
            return 2
        file_map = dict(zip(requested_tables, csv_files))
        csv_paths = [file_map[t] for t in target_tables]
    else:
        csv_paths = [None] * len(target_tables)  # 数据库模式：每张表都按表名读

    # 逐表处理：读数据 → 跑检查 → 打印。任一表有 FAIL 就把退出码标成 1。
    per_table: list[tuple[str, list[dict]]] = []
    exit_code = 0
    for table, csv_path in zip(target_tables, csv_paths):
        results, error = _run_one_table(table, csv_path, args, rules)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 2  # 读数据失败：fail-fast，立即停止
        print(render_results(table, results))
        per_table.append((table, results))
        if not all(result["passed"] for result in results):
            exit_code = 1

    # ---- 结果导出（可选）：单表走旧函数，多表走按表分组的新函数 ----
    if args.report:
        if len(per_table) == 1:
            table, results = per_table[0]
            output = args.output or _default_report_path(table, args.report)
            export_report(results, args.report, output, table)
        else:
            output = args.output or _default_report_path("multi", args.report)
            export_report_multi(per_table, args.report, output)
        print(f"Report written to {output}")

    return exit_code


if __name__ == "__main__":
    # 开关：if __name__ == "__main__" → sys.exit(main())
    # 这个 if 的作用：python -m core.cli 时执行 main；被 import 时只拿函数不执行。
    # sys.exit(数字) 把数字变成进程退出码，CI / 调度系统靠它判断这次检查成败。
    sys.exit(main())
#  ③④ 步的 return 2 = 命令没跑成（表名写错 / 文件找不到）→ 老板要查命令
# ⑦ 的 return 1 = 检查跑完了但数据不合格 → 老板要查数据
# —— CI 靠这个数字决定：是修命令，还是催人修数据
