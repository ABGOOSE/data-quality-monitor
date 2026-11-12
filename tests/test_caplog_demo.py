"""caplog 演示：测试里 logging 的正确用法。

caplog 是 pytest 内置的日志捕获夹具（fixture），它的作用不是"报告测试失败"
（这件事 pytest 的 assert 已经自动做了），而是断言"被测代码有没有按预期发出日志"。

例如：当配置校验通过时，validator 应该 logger.info 一条成功日志；
我们用 caplog 把这条日志抓出来验证，确保日志行为本身也被测试覆盖。
"""

import logging

import pandas as pd

from core.checker import run_checks
from core.validator import validate_rules


def test_validator_logs_success(caplog):
    """配置合法时，应发出一条含 'config validation passed' 的 INFO 日志。"""
    config = {"tables": {"T": {"checks": [{"rule": "row_count", "min_rows": 1}]}}}

    # caplog 默认只捕获 WARNING 及以上；用 at_level 显式放行 "core" 的 INFO。
    with caplog.at_level(logging.INFO, logger="core"):
        errors = validate_rules(config)

    assert errors == []
    # caplog.records 是这次调用产生的全部日志记录，逐条检查消息内容
    assert any("config validation passed" in record.message for record in caplog.records)


def test_checker_logs_finish_summary(caplog):
    """run_checks 完成后，应发出一条含 'checks finished' 的统计日志。"""
    df = pd.DataFrame({"id": [1, 2]})
    rules = {"checks": [{"rule": "row_count", "min_rows": 1}]}

    with caplog.at_level(logging.INFO, logger="core"):
        results = run_checks(df, rules)

    assert len(results) == 1
    assert any("checks finished" in record.message for record in caplog.records)


def test_caplog_captures_level_and_name(caplog):
    """演示可按级别字段精确断言：抓到的记录带 levelname 与 logger 名。"""
    df = pd.DataFrame({"id": [1, 2]})
    rules = {"checks": [{"rule": "row_count", "min_rows": 1}]}

    with caplog.at_level(logging.INFO, logger="core"):
        run_checks(df, rules)

    # 至少有一条 INFO 级别的记录，且来自 core 包下的 logger
    assert any(
        record.levelname == "INFO" and record.name.startswith("core") for record in caplog.records
    )
