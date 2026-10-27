"""Tests for core/data_loader.py."""

# 数据源加载器的测试：覆盖 CSV / SQLite 两种读取、统一入口，以及错误用法。
# 用 pytest 的 tmp_path 造临时 CSV 和临时数据库，测试自包含、不依赖 demo.db。
import pandas as pd
import pytest
from sqlalchemy import create_engine

from core.data_loader import load_csv, load_dataframe, load_table


@pytest.fixture
def sample_df():
    """一份固定的测试数据。"""
    return pd.DataFrame(
        {
            "id": [1, 2, 3],
            "amount": [10.0, 20.0, 30.0],
        }
    )


@pytest.fixture
def sqlite_db(tmp_path, sample_df):
    """在临时目录造一个 SQLite 库，里面有一张 MyTable。"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    sample_df.to_sql("MyTable", engine, index=False)
    engine.dispose()
    return db_path


def test_load_csv_returns_dataframe(tmp_path, sample_df):
    """load_csv 读 CSV：返回 DataFrame，列名和行数正确。"""
    csv_path = tmp_path / "data.csv"
    sample_df.to_csv(csv_path, index=False)
    df = load_csv(csv_path)
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["id", "amount"]
    assert len(df) == 3


def test_load_table_returns_dataframe(sqlite_db):
    """load_table 读数据库表：返回 DataFrame，列名和行数正确。"""
    df = load_table(f"sqlite:///{sqlite_db}", "MyTable")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 3
    assert list(df.columns) == ["id", "amount"]


def test_load_dataframe_from_csv(tmp_path, sample_df):
    """统一入口走 csv_path：能读到数据。"""
    csv_path = tmp_path / "data.csv"
    sample_df.to_csv(csv_path, index=False)
    df = load_dataframe(csv_path=csv_path)
    assert len(df) == 3


def test_load_dataframe_from_db(sqlite_db):
    """统一入口走 db_url + table_name：能读到数据。"""
    df = load_dataframe(db_url=f"sqlite:///{sqlite_db}", table_name="MyTable")
    assert len(df) == 3


def test_load_dataframe_no_source_raises():
    """两个数据源都没给：ValueError，提示要提供数据源。"""
    with pytest.raises(ValueError, match="Provide either"):
        load_dataframe()


def test_load_dataframe_db_without_table_raises(sqlite_db):
    """给了 db_url 但没给 table_name：ValueError。"""
    with pytest.raises(ValueError, match="table_name is required"):
        load_dataframe(db_url=f"sqlite:///{sqlite_db}")


def test_csv_and_db_contents_match(tmp_path, sample_df, sqlite_db):
    """同一份数据，从 CSV 和从数据库读出来内容一致（证明数据源可互换）。"""
    csv_path = tmp_path / "data.csv"
    sample_df.to_csv(csv_path, index=False)
    from_csv = load_dataframe(csv_path=csv_path)
    from_db = load_dataframe(db_url=f"sqlite:///{sqlite_db}", table_name="MyTable")
    # pandas 专用断言：两个 DataFrame 内容必须完全相等。
    pd.testing.assert_frame_equal(from_csv, from_db)
