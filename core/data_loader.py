"""Load data from CSV files or databases into a pandas DataFrame.

数据源加载器：把"数据从哪来"这件事统一收口。
不管数据来自 CSV 还是数据库，读出来都是 DataFrame，
所以下游的 run_checks / render / reporter 完全不关心数据来源。

- CSV：直接用 pandas.read_csv
- 数据库：用 SQLAlchemy 建引擎，pandas.read_sql_table 读整表
"""

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

# 模块级 logger；__name__ 是 "core.data_loader"，会传播到 core 顶层 logger。
logger = logging.getLogger(__name__)


def load_csv(path: str | Path) -> pd.DataFrame:
    """Read a CSV file into a DataFrame.

    Args:
        path: Path to the CSV file.

    Returns:
        A DataFrame with the file contents.
    """
    logger.debug("reading CSV file: %s", path)
    df = pd.read_csv(path)
    logger.debug("CSV loaded: %d row(s), %d column(s)", len(df), len(df.columns))
    return df


def load_table(db_url: str, table_name: str) -> pd.DataFrame:
    """Read a whole database table into a DataFrame.

    Args:
        db_url: SQLAlchemy connection URL, e.g. "sqlite:///demo.db" or
            "mysql+pymysql://user:pass@host:3306/db".
        table_name: The database table to read.

    Returns:
        A DataFrame with the table contents.
    """
    logger.debug("reading database table '%s' via %s", table_name, db_url)
    # create_engine 不立刻连接，只是"备好一辆车"；真正连接发生在查询时。
    engine = create_engine(db_url)
    try:
        # read_sql_table 直接读整张表（SELECT * FROM table_name），
        # 也可以用 read_sql("SELECT ...", engine) 写自定义查询。
        df = pd.read_sql_table(table_name, engine)
        logger.debug("table loaded: %d row(s), %d column(s)", len(df), len(df.columns))
        return df
    finally:
        # 释放连接池，避免连接泄漏。
        engine.dispose()


def load_dataframe(
    *,
    csv_path: str | Path | None = None,
    db_url: str | None = None,
    table_name: str | None = None,
) -> pd.DataFrame:
    """统一入口：根据参数决定从 CSV 还是数据库读。

    关键字参数（* 后面的参数必须用名字传）：
        csv_path: 走 CSV 时传文件路径。
        db_url: 走数据库时传连接串。
        table_name: 走数据库时要读的表名。

    Returns:
        A DataFrame from the selected source.

    Raises:
        ValueError: 两个数据源都没给，或给了 db_url 却没给 table_name。
    """
    if db_url is not None:
        if table_name is None:
            raise ValueError("table_name is required when reading from a database (db_url)")
        logger.info("data source: database table '%s'", table_name)
        return load_table(db_url, table_name)

    if csv_path is not None:
        logger.info("data source: CSV '%s'", csv_path)
        return load_csv(csv_path)

    # 两个数据源都没给：属于用法错误，直接报错（fail-fast），不返回空数据。
    raise ValueError("Provide either a csv_path or a db_url with a table_name")
