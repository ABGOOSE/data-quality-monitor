"""Build demo tables in a DM (达梦) database from CSV files."""

# 把项目自带的 CSV 数据导入达梦数据库，生成 TableA / TableB，供 dqm 检查。
# 用法：python scripts/build_dm_demo.py
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 达梦连接串：dm+dmPython://用户:密码@主机:端口/
# 注意：本机用 127.0.0.1（localhost 在部分环境解析有问题）
DM_URL = "dm+dmPython://SYSDBA:Dmxc_202601@127.0.0.1:5236/"

# 表名 -> CSV 文件名（表名与 rules.yaml 一致）
TABLES = {
    "TableA": "TableA.csv",
    "TableB": "TableB.csv",
}


def main() -> None:
    engine = create_engine(DM_URL)
    try:
        for table, csv_name in TABLES.items():
            csv_path = PROJECT_ROOT / "data" / csv_name
            df = pd.read_csv(csv_path)
            # if_exists="replace"：已存在则先删再建，方便反复执行
            df.to_sql(table, engine, if_exists="replace", index=False)
            print(f"已导入 {table}: {len(df)} 行，来自 {csv_name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
