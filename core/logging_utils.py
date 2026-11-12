"""统一日志配置：项目里所有模块共用一套 Logger / Handler / Formatter。

- 是什么：把"创建记录器、加处理器、定格式、设门槛"这些重复动作收敛到一个函数，
  程序入口只需调用一次，全项目的日志就按统一规则输出。
- 为什么：业务模块各自手写 logging 配置会风格不一、还容易重复打印；集中配置后，
  改级别、改格式、加文件输出都只动这一个文件。
- 用在哪：core/cli.py 的 main() 开头调用 setup_logging(...)；
  其他业务模块内部直接用 logging.getLogger(__name__) 发日志即可。

用法：
    from core.logging_utils import setup_logging
    setup_logging(level="INFO", log_file=Path("app.log"))
"""

import logging
from pathlib import Path

# 顶层 logger 的名字，和包名 core 对齐。
# core.cli、core.checker 等模块用 __name__ 取到的名字都以 "core." 开头，
# 会按层级向上传播（propagate）到这个顶层 logger，从而统一走下面配置的 handler。
_ROOT_LOGGER_NAME = "core"

# 统一日志排版，定位信息做到"文件:函数:行号"，一眼锁定出错位置：
#   时间 | 级别（左对齐占 8 格）| 文件名:函数名:行号 | 消息正文
# 各字段含义：
#   asctime  发生时间（精确到毫秒）；levelname 级别；
#   filename 实际文件名（如 cli.py）；funcName 触发日志的函数名；lineno 行号
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(filename)s:%(funcName)s:%(lineno)d | %(message)s"


def setup_logging(
    level: int | str = logging.INFO,
    log_file: Path | str | None = None,
) -> logging.Logger:
    """配置并返回项目顶层 logger。

    幂等设计：重复调用不会叠加 handler（每次先清空再重建），保证全局只有一套输出。

    Args:
        level: 日志门槛，可传 logging.INFO 这类常量，或字符串 "INFO"。
            只有数值 >= 该门槛的日志才会输出，例如设 INFO 时 DEBUG 不显示。
        log_file: 给了路径就额外增加一个文件处理器，把日志同时写进文件；
            不传则只输出到控制台。父目录不存在会自动创建。

    Returns:
        配置好的顶层 Logger 对象。
    """
    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    root_logger.setLevel(level)
    # 不再向 Python 根 logger 传播：本项目自己接管输出，避免同一条日志在控制台打印两次。
    root_logger.propagate = False

    formatter = logging.Formatter(_LOG_FORMAT)

    # 幂等：先清掉可能已存在的旧 handler，再重新添加。
    root_logger.handlers.clear()

    # Handler 1：控制台输出（StreamHandler 默认写到 stderr）。
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    # Handler 2：可选的文件输出。
    if log_file is not None:
        log_file = Path(log_file)
        # 父目录可能尚不存在，先建好，避免 FileHandler 因目录缺失报错。
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger
