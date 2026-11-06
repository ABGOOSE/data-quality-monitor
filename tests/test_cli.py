"""Unit tests for CLI entry point (core.cli.main)."""

import json
from pathlib import Path

import pytest

from core.cli import main

# 项目根定位：tests/ 的上一级。用 __file__ 动态算，不写死绝对路径。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOOD_CSV = PROJECT_ROOT / "data" / "TableA.csv"
BAD_CSV = PROJECT_ROOT / "data" / "TableA_bad.csv"
TABLEB_CSV = PROJECT_ROOT / "data" / "TableB.csv"  # 含一个 zscore 离群点(620)，单独跑退出码 1


def test_main_all_pass_returns_zero(capsys):
    """正常数据：返回 0，终端打印 [PASS]。

    argv 注入：main([...]) 直接传参数列表，模拟命令行，不起子进程。
    capsys 是 pytest 内置的"输出捕获器"：拿 main 里 print 的内容。
    """
    code = main(["--table", "TableA", "--data", str(GOOD_CSV)])
    assert code == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out


def test_main_violations_return_one(capsys):
    """坏数据：返回 1。退出码就是 CLI 和 CI 之间的协议，必须守住。"""
    code = main(["--table", "TableA", "--data", str(BAD_CSV)])
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
    code = main(["--table", "TableA", "--data", str(PROJECT_ROOT / "data" / "nope.csv")])
    assert code == 2
    err = capsys.readouterr().err
    assert "not found" in err


def test_main_report_json_writes_file(tmp_path, capsys):
    """--report json：报告文件真的生成，退出码不变（正常数据 0）。"""
    out = tmp_path / "r.json"
    code = main(
        [
            "--table",
            "TableA",
            "--data",
            str(GOOD_CSV),
            "--report",
            "json",
            "--output",
            str(out),
        ]
    )
    assert code == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    # TableA 有 6 条规则（not_null/unique/range/allowed_values/null_ratio/row_count），全过 → 6
    assert data["passed_checks"] == 6
    assert data["failed_checks"] == 0
    assert "Report written to" in capsys.readouterr().out


def test_main_report_keeps_exit_code_one(tmp_path):
    """坏数据 + --report：报告生成，但退出码仍 1——导出不影响成败判断。"""
    out = tmp_path / "r.md"
    code = main(
        [
            "--table",
            "TableA",
            "--data",
            str(BAD_CSV),
            "--report",
            "markdown",
            "--output",
            str(out),
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
    code = main(["--table", "TableA", "--data", str(GOOD_CSV), "--report", "json"])
    assert code == 0
    files = list(tmp_path.glob("report_TableA_*.json"))
    assert len(files) == 1


def test_main_no_report_writes_nothing(tmp_path):
    """不传 --report：不生成任何报告文件（旧行为保持，向后兼容）。"""
    code = main(["--table", "TableA", "--data", str(GOOD_CSV)])
    assert code == 0
    assert list(tmp_path.iterdir()) == []


def test_main_invalid_report_format_exits_two():
    """--report 传非法值：argparse 直接拒绝，以 SystemExit(2) 退出。

    argparse 的 choices 校验是"拒绝并退出"，不是返回退出码——
    所以这里捕获 SystemExit 而不是接收返回值。
    """
    with pytest.raises(SystemExit) as excinfo:
        main(["--table", "TableA", "--data", str(GOOD_CSV), "--report", "yaml"])
    assert excinfo.value.code == 2


def test_default_report_path_unknown_format_raises():
    """内部函数 _default_report_path 直接传非法格式：必须抛 ValueError，不能静默兜底成 md。

    argparse choices 已在入口拦截，这里守的是"内部函数自身严谨"——
    万一以后有人绕过 choices 直接调用，也不能生成错误后缀的文件。
    """
    from core.cli import _default_report_path

    with pytest.raises(ValueError, match="Unknown report format"):
        _default_report_path("TableA", "pdf")


def test_default_report_path_known_formats_have_correct_ext(monkeypatch, tmp_path):
    """合法格式：json 扩展名 .json，markdown 扩展名 .md（防分支改坏）。"""
    from core.cli import _default_report_path

    monkeypatch.chdir(tmp_path)
    assert _default_report_path("t", "json").suffix == ".json"
    assert _default_report_path("t", "markdown").suffix == ".md"


# ==================== 多表批量 ====================


def test_main_multi_tables_one_fails_returns_one(capsys):
    """多表：TableA 过、TableB 有离群点 → 整体退出码 1（聚合任一失败）。"""
    code = main(["--table", "TableA", "TableB", "--data", str(GOOD_CSV), str(TABLEB_CSV)])
    assert code == 1
    out = capsys.readouterr().out
    assert "Table: TableA" in out
    assert "Table: TableB" in out


def test_main_multi_tables_all_pass_returns_zero(capsys):
    """多表：两张都过 → 0。

    这里用 TableA.csv 喂两次（同一规则跑两遍），纯粹验证"循环聚合、全过才 0"。
    """
    code = main(["--table", "TableA", "TableA", "--data", str(GOOD_CSV), str(GOOD_CSV)])
    assert code == 0


def test_main_multi_tables_data_count_mismatch_returns_two(capsys):
    """多表：表数 2、文件数 1 → 无法一一对应，退出 2。"""
    code = main(["--table", "TableA", "TableB", "--data", str(GOOD_CSV)])
    assert code == 2
    assert "expects 2 file(s)" in capsys.readouterr().err


def test_main_multi_tables_unknown_name_returns_two(capsys):
    """多表：其中一张表名拼错 → 退出 2，错误信息点名拼错的表。"""
    code = main(["--table", "TableA", "NoSuch", "--data", str(GOOD_CSV), str(TABLEB_CSV)])
    assert code == 2
    assert "NoSuch" in capsys.readouterr().err


def test_main_all_flag_checks_all_tables(capsys):
    """--all：遍历配置里所有表（TableA 过、TableB 坏）→ 退出 1。"""
    code = main(["--all", "--data", str(GOOD_CSV), str(TABLEB_CSV)])
    assert code == 1
    out = capsys.readouterr().out
    assert "Table: TableA" in out
    assert "Table: TableB" in out


def test_main_table_and_all_mutually_exclusive():
    """--table 和 --all 同时给：argparse 互斥组直接拒绝（SystemExit 2）。"""
    with pytest.raises(SystemExit) as excinfo:
        main(["--table", "TableA", "--all", "--data", str(GOOD_CSV)])
    assert excinfo.value.code == 2


def test_main_multi_table_report_json_groups_by_table(tmp_path):
    """多表 --report json：一个文件里 tables 数组按表分组，并带 totals 汇总。"""
    out = tmp_path / "multi.json"
    code = main(
        [
            "--table",
            "TableA",
            "TableB",
            "--data",
            str(GOOD_CSV),
            str(TABLEB_CSV),
            "--report",
            "json",
            "--output",
            str(out),
        ]
    )
    assert code == 1  # TableB 有离群点，但报告照样生成
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [t["table"] for t in data["tables"]] == ["TableA", "TableB"]
    assert data["totals"]["tables"] == 2
