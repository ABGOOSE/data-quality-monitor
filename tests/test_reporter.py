"""Unit tests for reporter module."""

import json

import pytest

from core.reporter import export_json, export_markdown, export_report

# 模拟 run_checks 的真实输出结构：rule/passed/column 元信息键 + 各自指标键。
# 列级结果 column 是列名；表级结果（row_count）column 是 None。
SAMPLE_RESULTS = [
    {
        "rule": "not_null",
        "passed": True,
        "null_count": 0,
        "total_count": 3,
        "null_ratio": 0.0,
        "column": "order_id",
    },
    {
        "rule": "unique",
        "passed": True,
        "duplicate_count": 0,
        "total_count": 3,
        "duplicate_ratio": 0.0,
        "column": "order_id",
    },
    {
        "rule": "range",
        "passed": False,
        "out_of_range_count": 1,
        "total_count": 3,
        "min_value": 0,
        "max_value": 1000000,
        "column": "amount",
    },
    {
        "rule": "row_count",
        "passed": True,
        "row_count": 3,
        "min_rows": 1,
        "column": None,
    },
]

# 固定时间戳：时间戳参数可注入，测试才能稳定复现（不用真实当前时间）
FIXED_TIME = "2026-09-23T10:00:00"


# ---------- JSON 导出 ----------
def test_export_json_creates_file(tmp_path):
    """JSON 文件应该被创建，且返回文件路径。"""
    out = tmp_path / "report.json"
    returned = export_json(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    assert returned == out
    assert out.exists()


def test_export_json_contains_summary(tmp_path):
    """JSON 里应该带汇总统计：表名、时间、总数/通过/失败。"""
    out = tmp_path / "report.json"
    export_json(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["table"] == "sample_orders"
    assert data["generated_at"] == FIXED_TIME
    assert data["total_checks"] == 4
    assert data["passed_checks"] == 3
    assert data["failed_checks"] == 1


def test_export_json_contains_all_results(tmp_path):
    """每条检查结果都要原样出现在 results 数组里，一条不能少。"""
    out = tmp_path / "report.json"
    export_json(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["results"]) == 4
    assert data["results"][0]["rule"] == "not_null"
    assert data["results"][2]["passed"] is False
    assert data["results"][3]["column"] is None


# ---------- Markdown 导出 ----------
def test_export_markdown_creates_file(tmp_path):
    """Markdown 文件应该被创建，且返回文件路径。"""
    out = tmp_path / "report.md"
    returned = export_markdown(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    assert returned == out
    assert out.exists()


def test_export_markdown_contains_summary(tmp_path):
    """Markdown 报告里应该有标题和汇总统计。"""
    out = tmp_path / "report.md"
    export_markdown(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    text = out.read_text(encoding="utf-8")
    assert "Data Quality Report: sample_orders" in text
    assert "总检查数" in text and "4" in text
    assert "通过" in text and "3" in text
    assert "失败" in text and "1" in text


def test_export_markdown_has_one_row_per_result(tmp_path):
    """每个结果一行状态标记；表级规则（column=None）目标显示为 table。"""
    out = tmp_path / "report.md"
    export_markdown(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    text = out.read_text(encoding="utf-8")
    assert text.count("| PASS |") == 3
    assert text.count("| FAIL |") == 1
    # 表级规则（column=None）目标显示为 table（表格行格式）
    assert "| PASS | table | row_count |" in text


def test_export_markdown_details_generic(tmp_path):
    """详情列是通用的：任何指标键自动渲染，以后加新规则不用改 reporter。"""
    out = tmp_path / "report.md"
    export_markdown(SAMPLE_RESULTS, out, "sample_orders", generated_at=FIXED_TIME)
    text = out.read_text(encoding="utf-8")
    assert "null_count=0" in text
    assert "out_of_range_count=1" in text
    assert "min_value=0" in text


# ---------- 分发器 ----------
def test_export_report_dispatches_json(tmp_path):
    """export_report 应该按格式分发到 export_json。"""
    out = tmp_path / "out.json"
    export_report(SAMPLE_RESULTS, "json", out, "sample_orders", generated_at=FIXED_TIME)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["table"] == "sample_orders"


def test_export_report_dispatches_markdown(tmp_path):
    """export_report 应该按格式分发到 export_markdown。"""
    out = tmp_path / "out.md"
    export_report(SAMPLE_RESULTS, "markdown", out, "sample_orders", generated_at=FIXED_TIME)
    assert "Data Quality Report" in out.read_text(encoding="utf-8")


def test_export_report_unknown_format_raises(tmp_path):
    """未知格式必须大声报错（fail fast），不能静默什么都不做。"""
    out = tmp_path / "out.txt"
    with pytest.raises(ValueError, match="yaml"):
        export_report(SAMPLE_RESULTS, "yaml", out, "sample_orders", generated_at=FIXED_TIME)
