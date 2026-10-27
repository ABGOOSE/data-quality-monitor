"""Build a SQLite demo database from the CSV data files.

把 data/ 下的 CSV 写进一个 SQLite 数据库（data/demo.db），
用来演示"从数据库读数据"的流程，无需安装任何数据库服务。

重新生成：python scripts/build_demo_db.py
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

# 项目根：本脚本在 scripts/ 下，parents[0] 是 scripts/，parents[1] 是项目根。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "demo.db"

# 数据库表名 -> 对应的 CSV 文件。
TABLES = {
    "TableA": "TableA.csv",
    "TableB": "TableB.csv",
}


def main() -> None:
    # SQLite 连接串：sqlite:/// + 数据库文件路径（三斜杠后是相对/绝对路径）。
    engine = create_engine(f"sqlite:///{DB_PATH}")
    for table_name, csv_name in TABLES.items():
        df = pd.read_csv(PROJECT_ROOT / "data" / csv_name)
        # to_sql 把 DataFrame 写进数据库；if_exists="replace" 已存在就重建；
        # index=False 不把 pandas 的行索引写进去。
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        print(f"wrote table '{table_name}': {len(df)} rows")
    print(f"database written to {DB_PATH}")


if __name__ == "__main__":
    main()
