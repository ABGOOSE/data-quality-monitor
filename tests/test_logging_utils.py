"""Tests for core/logging_utils.setup_logging."""

import logging

from core.logging_utils import setup_logging


def test_setup_logging_console_only():
    """默认配置：只挂一个控制台 StreamHandler，propagate 关闭，门槛为 INFO。"""
    lg = setup_logging(level="INFO")
    assert lg.name == "core"
    assert lg.propagate is False
    assert lg.level == logging.INFO
    assert len(lg.handlers) == 1
    assert isinstance(lg.handlers[0], logging.StreamHandler)


def test_setup_logging_idempotent():
    """重复调用不叠加 handler：连调两次后控制台 handler 仍是 1 个。"""
    setup_logging()
    setup_logging()
    assert len(logging.getLogger("core").handlers) == 1


def test_setup_logging_writes_file_and_creates_parent(tmp_path):
    """带 log_file：多一个 FileHandler，父目录自动创建，日志真实写入文件。"""
    nested = tmp_path / "sub" / "dir" / "app.log"  # 父目录 deliberately 尚不存在
    lg = setup_logging(level="DEBUG", log_file=nested)

    assert len(lg.handlers) == 2  # 控制台 + 文件
    assert isinstance(lg.handlers[1], logging.FileHandler)
    assert nested.exists()  # 父目录已被自动创建，文件已生成

    lg.info("hello log file")
    text = nested.read_text(encoding="utf-8")
    assert "hello log file" in text


def test_setup_logging_level_filter(tmp_path):
    """门槛设 WARNING：INFO 被过滤不写文件，WARNING 正常写入。"""
    log_file = tmp_path / "filtered.log"
    lg = setup_logging(level="WARNING", log_file=log_file)
    lg.info("this info is filtered out")
    lg.warning("this warning stays")

    text = log_file.read_text(encoding="utf-8")
    assert "this info is filtered out" not in text
    assert "this warning stays" in text
