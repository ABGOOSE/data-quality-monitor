"""Unit tests for CLI entry point (core.cli.main)."""

import json
from pathlib import Path

import pytest

from core.cli import main

# 项目根定位：tests/ 的上一级。用 __file__ 动态算，不写死绝对路径。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOOD_CSV = PROJECT_ROOT / "data" / "sample_orders.csv"
BAD_CSV = PROJECT_ROOT / "data" / "sample_orders_bad.csv"


def test_main_all_pass_returns_zero(capsys):
    """正常数据：返回 0，终端打印 [PASS]。

    argv 注入：main([...]) 直接传参数列表，模拟命令行，不起子进程。
    capsys 是 pytest 内置的"输出捕获器"：拿 main 里 print 的内容。
    """
    code = main(["--table", "sample_orders", "--data", str(GOOD_CSV)])
    assert code == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out


def test_main_violations_return_one(capsys):
    """坏数据：返回 1。退出码就是 CLI 和 CI 之间的协议，必须守住。"""
    code = main(["--table", "sample_orders", "--data", str(BAD_CSV)])
    assert code == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out


def test_main_unknown_table_returns_two(capsys):
    """表不存在：返回 2（用法错误），错误信息走 stderr 而不是 stdout。"""
    code = main(["--table", "no_such_table", "--data", str(GOOD_CSV)])
    assert code == 2
    err = capsys.readouterr().err
    assert "no_such_table" in err


def test_main_missing_file_returns_two(capsys):
    """数据文件不存在：返回 2。"""
    code = main(
        ["--table", "sample_orders", "--data", str(PROJECT_ROOT / "data" / "nope.csv")]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "not found" in err


def test_main_report_json_writes_file(tmp_path, capsys):
    """--report json：报告文件真的生成，退出码不变（正常数据 0）。"""
    out = tmp_path / "r.json"
    code = main(
        [
            "--table", "sample_orders",
            "--data", str(GOOD_CSV),
            "--report", "json",
            "--output", str(out),
        ]
    )
    assert code == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    # sample_orders 有 5 条规则（not_null/unique/range/allowed_values/row_count），全过 → 5
    assert data["passed_checks"] == 5
    assert data["failed_checks"] == 0
    assert "Report written to" in capsys.readouterr().out


def test_main_report_keeps_exit_code_one(tmp_path):
    """坏数据 + --report：报告生成，但退出码仍 1——导出不影响成败判断。"""
    out = tmp_path / "r.md"
    code = main(
        [
            "--table", "sample_orders",
            "--data", str(BAD_CSV),
            "--report", "markdown",
            "--output", str(out),
        ]
    )
    assert code == 1
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "| FAIL |" in text


def test_main_report_default_output_writes_to_cwd(tmp_path, monkeypatch):
    """--report 不传 --output：自动命名（report_表名_时间戳.json）写到当前目录。

    monkeypatch.chdir 把"当前目录"临时切到 tmp_path——自动命名的文件
    就落在 tmp_path，不会污染项目根目录。
    """
    monkeypatch.chdir(tmp_path)
    code = main(["--table", "sample_orders", "--data", str(GOOD_CSV), "--report", "json"])
    assert code == 0
    files = list(tmp_path.glob("report_sample_orders_*.json"))
    assert len(files) == 1


def test_main_no_report_writes_nothing(tmp_path):
    """不传 --report：不生成任何报告文件（旧行为保持，向后兼容）。"""
    code = main(["--table", "sample_orders", "--data", str(GOOD_CSV)])
    assert code == 0
    assert list(tmp_path.iterdir()) == []


def test_main_invalid_report_format_exits_two():
    """--report 传非法值：argparse 直接拒绝，以 SystemExit(2) 退出。

    argparse 的 choices 校验是"拒绝并退出"，不是返回退出码——
    所以这里捕获 SystemExit 而不是接收返回值。
    """
    with pytest.raises(SystemExit) as excinfo:
        main(["--table", "sample_orders", "--data", str(GOOD_CSV), "--report", "yaml"])
    assert excinfo.value.code == 2
