"""Export check results to report files (JSON / Markdown).

把 run_checks 的结果从"终端一闪而过"变成"可归档的文件"：
- JSON：给程序看（报表系统、存库、历史对比）
- Markdown：给人看（周报、工单、交付业务方）

和 config_loader 一样是纯函数模块，不碰配置、不碰数据，只负责"把结果写成文件"。
"""

import json
from datetime import datetime
from pathlib import Path

# 元信息键：描述这条结果本身（什么规则、过没过、哪一列），不是检查指标。
# 渲染详情时跳过它们，和 cli.py 的 _META_KEYS 是同一套约定。
_META_KEYS = {"rule", "passed", "column"}


def _format_detail(result: dict) -> str:
    """把一条结果里的指标键值对拼成 "key=value, key=value" 明细串。

    跳过元信息键，只展示检查出来的指标（null_count、out_of_range_count 等）。
    新规则加任何指标键都能自动渲染——不用改这里，这是通用性的来源。
    """
    return ", ".join(
        f"{key}={value}" for key, value in result.items() if key not in _META_KEYS
    )


def _target_name(result: dict) -> str:
    """结果的目标名：列级规则是列名，表级规则（column=None）显示为 table。"""
    return result["column"] if result["column"] is not None else "table"


def _summary(results: list[dict]) -> dict:
    """汇总统计：总数 / 通过数 / 失败数。"""
    return {
        "total_checks": len(results),
        "passed_checks": sum(1 for result in results if result["passed"]),
        "failed_checks": sum(1 for result in results if not result["passed"]),
    }


def export_json(
    results: list[dict],
    output_path: Path,
    table_name: str,
    generated_at: str | None = None,
) -> Path:
    """Export check results to a JSON report file.

    Args:
        results: Check results from run_checks.
        output_path: Where to write the report.
        table_name: Name of the checked table (shown in the report).
        generated_at: ISO timestamp; injected in tests for stable output.

    Returns:
        The output path (convenience for chaining / printing).
    """
    # 时间戳可注入：默认取当前时间，测试传固定值才能断言精确内容
    if generated_at is None:
        # astimezone() 给 naive datetime 加上本地时区，满足 ruff DTZ005（时间戳必须带时区）
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "table": table_name,
        "generated_at": generated_at,
        **_summary(results),
        "results": results,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def export_markdown(
    results: list[dict],
    output_path: Path,
    table_name: str,
    generated_at: str | None = None,
) -> Path:
    """Export check results to a Markdown report file.

    报告结构：标题 + 汇总 + 表格，每行一条检查结果。
    """
    if generated_at is None:
        generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    summary = _summary(results)
    lines = [
        f"# Data Quality Report: {table_name}",
        "",
        f"- 生成时间：{generated_at}",
        f"- 总检查数：{summary['total_checks']}",
        f"- 通过：{summary['passed_checks']}",
        f"- 失败：{summary['failed_checks']}",
        "",
        "| 状态 | 目标 | 规则 | 详情 |",
        "|---|---|---|---|",
    ]
    for result in results:
        status = "PASS" if result["passed"] else "FAIL"
        lines.append(
            f"| {status} | {_target_name(result)} | {result['rule']} | {_format_detail(result)} |"
        )
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def export_report(
    results: list[dict],
    fmt: str,
    output_path: Path,
    table_name: str,
    generated_at: str | None = None,
) -> Path:
    """Dispatch to the matching exporter by format name.

    Args:
        results: Check results from run_checks.
        fmt: "json" or "markdown".
        output_path: Where to write the report.
        table_name: Name of the checked table.
        generated_at: ISO timestamp (injected in tests).

    Returns:
        The output path.

    Raises:
        ValueError: If fmt is not supported (fail fast, same as checker).
    """
    if fmt == "json":
        return export_json(results, output_path, table_name, generated_at=generated_at)
    if fmt == "markdown":
        return export_markdown(results, output_path, table_name, generated_at=generated_at)
    raise ValueError(f"Unknown report format '{fmt}'. Available: json, markdown")
