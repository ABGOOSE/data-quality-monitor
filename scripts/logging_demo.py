"""logging 最小演示（教学用）。

运行后能亲眼看到三件事：
1. 5 个级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）长什么样；
2. 门槛（level）怎么过滤掉低级别的日志；
3. 同一条日志怎么同时输出到控制台和文件（StreamHandler + FileHandler）。

运行方式（在项目根目录）：
    .venv\\Scripts\\python.exe scripts\\logging_demo.py
"""

import logging
import tempfile
from pathlib import Path


def part_one_five_levels() -> None:
    """第 1 部分：门槛设到最低 DEBUG，5 个级别全部显示。"""
    print("\n" + "=" * 70)
    print("第 1 部分：门槛=DEBUG，5 个级别全部输出")
    print("=" * 70)

    # basicConfig：logging 自带的一键配置，适合演示和小脚本。
    # force=True：演示里要切换门槛，先清掉旧配置再重新配。
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        force=True,
    )
    logger = logging.getLogger("demo")  # 名为 demo 的记录器，记录会向上交给 root 输出

    logger.debug("DEBUG 级别，数值 10：最细的调试细节")
    logger.info("INFO 级别，数值 20：正常运行的关键节点")
    logger.warning("WARNING 级别，数值 30：出了意外但能继续")
    logger.error("ERROR 级别，数值 40：某个操作失败了")
    logger.critical("CRITICAL 级别，数值 50：致命错误")


def part_two_level_filter() -> None:
    """第 2 部分：门槛抬到 INFO，DEBUG 被过滤掉。"""
    print("\n" + "=" * 70)
    print("第 2 部分：门槛=INFO，注意 DEBUG 那行不见了")
    print("=" * 70)

    logging.basicConfig(
        level=logging.INFO,  # 只有数值 >= 20 的才输出
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        force=True,
    )
    logger = logging.getLogger("demo")

    logger.debug("这行 DEBUG 不会出现（10 < 门槛 20）")
    logger.info("这行 INFO 会出现（20 >= 20）")
    logger.warning("这行 WARNING 会出现")


def part_three_handlers() -> Path:
    """第 3 部分：显式搭建 Logger + 两个 Handler（控制台 + 文件）。"""
    print("\n" + "=" * 70)
    print("第 3 部分：同一条日志同时进控制台和文件")
    print("=" * 70)

    # 日志文件放系统临时目录，不污染项目；脚本末尾会打印完整路径方便打开
    log_file = Path(tempfile.gettempdir()) / "dqm_logging_demo.log"

    logger = logging.getLogger("demo.handlers")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # 清掉旧 Handler，避免重复打印
    logger.propagate = False  # 不向 root 传播：只走自己下面这两个 Handler，控制台不会重复

    # Formatter：统一排版，lineno 是触发日志那一行的行号
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )

    # Handler 1：控制台 StreamHandler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Handler 2：文件 FileHandler；mode="w" 每次运行覆盖，演示输出干净
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("这条日志同时出现在控制台，并写进文件")
    logger.warning("这条也一样，两个去向都有")
    return log_file


if __name__ == "__main__":
    part_one_five_levels()
    part_two_level_filter()
    log_path = part_three_handlers()
    print("\n" + "=" * 70)
    print(f"日志文件已写到：{log_path}")
    print("=" * 70)
