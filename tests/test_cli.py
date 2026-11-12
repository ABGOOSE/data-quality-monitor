"""Unit tests for CLI entry point (core.cli.main)."""

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine

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


# ==================== --tables-file：从文件读表清单 ====================


def test_main_tables_file_reads_list_and_ignores_comments(tmp_path, capsys):
    """--tables-file：读文件里的表名，忽略注释行和空行。

    文件内容里 TableA 过、TableB 坏 → 整体退出 1。
    """
    tf = tmp_path / "tables.txt"
    tf.write_text(
        "# 我的表清单\n\nTableA\n\n# 下面是另一张\nTableB\n",
        encoding="utf-8",
    )
    code = main(["--tables-file", str(tf), "--data", str(GOOD_CSV), str(TABLEB_CSV)])
    assert code == 1
    out = capsys.readouterr().out
    assert "Table: TableA" in out
    assert "Table: TableB" in out


def test_main_tables_file_not_found_returns_two(tmp_path, capsys):
    """--tables-file 文件不存在：退出 2，错误信息走 stderr。"""
    code = main(["--tables-file", str(tmp_path / "nope.txt"), "--data", str(GOOD_CSV)])
    assert code == 2
    assert "not found" in capsys.readouterr().err


def test_main_tables_file_unknown_table_in_list_returns_two(tmp_path, capsys):
    """文件里写了不存在的表名：走统一的表名校验，退出 2。"""
    tf = tmp_path / "tables.txt"
    tf.write_text("TableA\nNoSuch\n", encoding="utf-8")
    code = main(["--tables-file", str(tf), "--data", str(GOOD_CSV), str(TABLEB_CSV)])
    assert code == 2
    assert "NoSuch" in capsys.readouterr().err


def test_main_missing_tables_report_is_structured_and_deduped(tmp_path, capsys):
    """无规则表：结构化输出（[missing] 标记、去重、提示可用表）。"""
    tf = tmp_path / "tables.txt"
    # NoSuch 写两遍，验证去重；再加一个无规则表
    tf.write_text("NoSuch\nNoSuch\nAnotherMissing\n", encoding="utf-8")
    code = main(
        [
            "--tables-file",
            str(tf),
            "--data",
            str(GOOD_CSV),
            str(GOOD_CSV),
            str(GOOD_CSV),
        ]
    )
    assert code == 2
    err = capsys.readouterr().err
    assert "[missing] NoSuch" in err
    assert "[missing] AnotherMissing" in err
    # 去重：NoSuch 只出现一次（[missing] 行）
    assert err.count("[missing] NoSuch") == 1
    # 提示 rules 里实际有哪些表
    assert "Tables defined in rules.yaml" in err


# ==================== --dry-run：预检（只报告，不执行） ====================


def test_main_dry_run_all_valid_returns_zero(capsys):
    """预检全有效：返回 0，列出 [ok] 表，但不跑检查（没有 [PASS] 结果行）。"""
    code = main(["--table", "TableA", "--data", str(GOOD_CSV), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out
    assert "[ok] TableA" in out
    assert "[PASS]" not in out  # 预检不执行检查


def test_main_dry_run_missing_returns_one(capsys):
    """预检发现无规则表：返回 1，并在清单里点名 [missing]。"""
    code = main(
        [
            "--table",
            "TableA",
            "NoSuch",
            "--data",
            str(GOOD_CSV),
            str(GOOD_CSV),
            "--dry-run",
        ]
    )
    assert code == 1
    out = capsys.readouterr().out
    assert "[ok] TableA" in out
    assert "[missing] NoSuch" in out


def test_main_dry_run_has_no_file_side_effect(tmp_path):
    """预检即使带了 --report/--output，也不写任何文件（在导出前就返回）。"""
    out = tmp_path / "should_not_exist.json"
    code = main(
        [
            "--table",
            "TableA",
            "--data",
            str(GOOD_CSV),
            "--dry-run",
            "--report",
            "json",
            "--output",
            str(out),
        ]
    )
    assert code == 0
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []


# ==================== --skip-missing：宽松模式（跳过无规则表） ====================


def test_main_skip_missing_continues_with_valid_table(capsys):
    """宽松模式：跳过 NoSuch，继续查 TableA；警告走 stderr，结果全 PASS，退出码 0。"""
    code = main(
        [
            "--table",
            "TableA",
            "NoSuch",
            "--data",
            str(GOOD_CSV),
            str(BAD_CSV),
            "--skip-missing",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "[skip] NoSuch" in captured.err
    assert "Table: TableA" in captured.out
    assert "[PASS]" in captured.out


def test_main_skip_missing_uses_correct_file_mapping(capsys):
    """宽松模式文件不错位：TableA 用它对应的第一个文件（GOOD_CSV 全过），
    NoSuch 对应的第二个文件被一起排除。"""
    code = main(
        [
            "--table",
            "TableA",
            "NoSuch",
            "--data",
            str(GOOD_CSV),  # 对应 TableA
            str(BAD_CSV),  # 对应 NoSuch（应被排除，不影响结果）
            "--skip-missing",
        ]
    )
    assert code == 0  # 若错用了 BAD_CSV，这里会变成 1
    assert "[FAIL]" not in capsys.readouterr().out


def test_main_skip_missing_all_skipped_returns_two(capsys):
    """宽松模式下所有表都无规则：一张有效表都不剩，退出 2。"""
    code = main(
        [
            "--table",
            "NoSuch",
            "AnotherNo",
            "--data",
            str(GOOD_CSV),
            str(GOOD_CSV),
            "--skip-missing",
        ]
    )
    assert code == 2
    assert "no valid table left" in capsys.readouterr().err


# ==================== 缺失表文件留存（审计留痕） ====================


def test_main_strict_writes_missing_report_file(tmp_path, monkeypatch):
    """严格模式：生成 missing_tables 文件，内容含缺失表和可用表，退出码 2。"""
    monkeypatch.chdir(tmp_path)
    code = main(["--table", "NoSuch", "AnotherMissing", "--data", str(GOOD_CSV), str(GOOD_CSV)])
    assert code == 2
    files = list(tmp_path.glob("missing_tables_*.txt"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "- NoSuch" in text
    assert "- AnotherMissing" in text
    assert "strict mode" in text
    assert "- TableA" in text  # 可用表也列出


def test_main_lenient_writes_missing_report_and_continues(tmp_path, monkeypatch):
    """宽松模式：生成缺失表文件，同时继续检查有效表，退出码 0。"""
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "--table",
            "TableA",
            "NoSuch",
            "--data",
            str(GOOD_CSV),
            str(BAD_CSV),
            "--skip-missing",
        ]
    )
    assert code == 0
    files = list(tmp_path.glob("missing_tables_*.txt"))
    assert len(files) == 1
    assert "lenient mode" in files[0].read_text(encoding="utf-8")


def test_main_all_skipped_still_writes_report(tmp_path, monkeypatch):
    """全跳过（退出 2）也必须留文件，不能因为终止就没记录。"""
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "--table",
            "NoSuch",
            "AnotherNo",
            "--data",
            str(GOOD_CSV),
            str(GOOD_CSV),
            "--skip-missing",
        ]
    )
    assert code == 2
    assert len(list(tmp_path.glob("missing_tables_*.txt"))) == 1


def test_main_no_missing_writes_no_report(tmp_path, monkeypatch):
    """全部表都有规则：不生成缺失表文件。"""
    monkeypatch.chdir(tmp_path)
    code = main(["--table", "TableA", "--data", str(GOOD_CSV)])
    assert code == 0
    assert list(tmp_path.glob("missing_tables_*.txt")) == []


def test_main_dry_run_does_not_write_missing_report(tmp_path, monkeypatch):
    """dry-run 即使有缺失表也不写文件（保持无副作用）。"""
    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "--table",
            "TableA",
            "NoSuch",
            "--data",
            str(GOOD_CSV),
            str(GOOD_CSV),
            "--dry-run",
        ]
    )
    assert code == 1
    assert list(tmp_path.glob("missing_tables_*.txt")) == []


# ==================== --data-file：从文件读 CSV 路径清单 ====================


def test_main_data_file_reads_csv_list(tmp_path, capsys):
    """--data-file：从文件读 CSV 路径，忽略注释行和空行，正常检查退出 0。"""
    df_file = tmp_path / "data_list.txt"
    df_file.write_text(f"# CSV 清单\n\n{GOOD_CSV}\n", encoding="utf-8")
    code = main(["--table", "TableA", "--data-file", str(df_file)])
    assert code == 0
    assert "[PASS]" in capsys.readouterr().out


def test_main_data_file_multiple_paths(tmp_path, capsys):
    """--data-file 多表：每行一个路径，顺序和表一一对应（TableB 离群 → 退出 1）。"""
    df_file = tmp_path / "data_list.txt"
    df_file.write_text(f"{GOOD_CSV}\n{TABLEB_CSV}\n", encoding="utf-8")
    code = main(["--table", "TableA", "TableB", "--data-file", str(df_file)])
    assert code == 1
    out = capsys.readouterr().out
    assert "Table: TableA" in out
    assert "Table: TableB" in out


def test_main_data_file_not_found_returns_two(tmp_path, capsys):
    """--data-file 文件本身不存在：退出 2，错误信息走 stderr。"""
    code = main(["--table", "TableA", "--data-file", str(tmp_path / "nope.txt")])
    assert code == 2
    assert "not found" in capsys.readouterr().err


def test_main_data_file_count_mismatch_returns_two(tmp_path, capsys):
    """--data-file 里路径数和表数对不上：退出 2。"""
    df_file = tmp_path / "data_list.txt"
    df_file.write_text(f"{GOOD_CSV}\n", encoding="utf-8")  # 只有 1 个路径，表有 2 张
    code = main(["--table", "TableA", "TableB", "--data-file", str(df_file)])
    assert code == 2
    assert "expects 2 file(s)" in capsys.readouterr().err


def test_main_tables_file_and_data_file_together(tmp_path, capsys):
    """--tables-file 和 --data-file 同时用：表名、CSV 路径都从文件读（全文件驱动）。"""
    tf = tmp_path / "tables.txt"
    tf.write_text("TableA\nTableB\n", encoding="utf-8")
    df_file = tmp_path / "data_list.txt"
    df_file.write_text(f"{GOOD_CSV}\n{TABLEB_CSV}\n", encoding="utf-8")
    code = main(["--tables-file", str(tf), "--data-file", str(df_file)])
    assert code == 1
    out = capsys.readouterr().out
    assert "Table: TableA" in out
    assert "Table: TableB" in out


# ==================== main 内的配置校验入口 ====================


def test_main_invalid_config_returns_two(tmp_path, capsys):
    """配置能被 YAML 解析但 schema 不合法：main 打印 Config error 并 return 2。"""
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("other: 1\n", encoding="utf-8")  # 缺少必需的 tables 键
    code = main(["--table", "TableA", "--data", str(GOOD_CSV), "--config", str(bad_config)])
    assert code == 2
    assert "Config error" in capsys.readouterr().err


# ==================== 空请求表 ====================


def test_main_empty_tables_file_returns_two(tmp_path, capsys):
    """tables-file 只有注释和空行：解析出 0 张表，return 2。"""
    tf = tmp_path / "empty.txt"
    tf.write_text("# 只有注释\n\n   \n", encoding="utf-8")
    code = main(["--tables-file", str(tf), "--data", str(GOOD_CSV)])
    assert code == 2
    assert "no table to check" in capsys.readouterr().err


# ==================== dry-run 全部无规则 ====================


def test_main_dry_run_all_missing_lists_none(tmp_path, capsys):
    """dry-run 一张有效表都没有：valid 区块显示 (none)，并点名 missing。"""
    tf = tmp_path / "tables.txt"
    tf.write_text("NoSuch\n", encoding="utf-8")
    code = main(["--tables-file", str(tf), "--data", str(GOOD_CSV), "--dry-run"])
    assert code == 1
    out = capsys.readouterr().out
    assert "(none)" in out
    assert "[missing] NoSuch" in out


# ==================== render_results 空明细分支 ====================


def test_render_results_without_detail_keys(capsys):
    """结果只有元信息键、没有任何指标时：明细为空也能正常渲染（走 if detail 的空分支）。"""
    from core.cli import render_results

    print(render_results("TableX", [{"rule": "custom", "passed": True, "column": None}]))
    out = capsys.readouterr().out
    assert "Table: TableX" in out
    assert "[PASS] table :: custom" in out


# ==================== 数据库模式（SQLite，CI 也能跑） ====================


@pytest.fixture
def sqlite_db(tmp_path):
    """造一个含 TableA 的 SQLite 库，返回 SQLAlchemy 连接串。"""
    db_path = tmp_path / "test.db"
    df = pd.read_csv(GOOD_CSV)
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    df.to_sql("TableA", engine, if_exists="replace", index=False)
    engine.dispose()
    return f"sqlite:///{db_path.as_posix()}"


def test_main_db_mode_reads_table(sqlite_db, capsys):
    """--db 数据库模式：按表名读 TableA，全过退出 0。"""
    code = main(["--table", "TableA", "--db", sqlite_db])
    assert code == 0
    assert "[PASS]" in capsys.readouterr().out


def test_main_db_dry_run_shows_database_source(sqlite_db, capsys):
    """--db + --dry-run：数据源说明显示 database，而不是 CSV。"""
    code = main(["--table", "TableA", "--db", sqlite_db, "--dry-run"])
    assert code == 0
    assert "Data source: database" in capsys.readouterr().out


def test_main_db_connection_failure_returns_two(tmp_path, capsys):
    """数据库读表失败（连接/表不存在）：捕获 SQLAlchemyError，return 2。"""
    db_dir = tmp_path / "a_directory"
    db_dir.mkdir()  # 指向一个已存在的目录，SQLite 无法把它当数据库打开，抛 OperationalError
    url = f"sqlite:///{db_dir.as_posix()}"
    code = main(["--table", "TableA", "--db", url])
    assert code == 2
    assert "failed to read table" in capsys.readouterr().err
