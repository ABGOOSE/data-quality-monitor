"""pandas 知识延展演示：用真实数据跑一遍开发中最常用的操作。"""

import numpy as np
import pandas as pd

# 造两张"业务表"：订单表 + 客户表
orders = pd.DataFrame(
    {
        "order_id": [1, 2, 3, 4, 5, 6],
        "cust_id": [101, 102, 101, 103, None, 102],
        "amount": [100, 250, 80, 999, 50, 1200],
        "status": ["paid", "paid", "refund", "paid", "paid", "paid"],
        "created": [
            "2026-01-03",
            "2026-01-05",
            "2026-02-01",
            "2026-02-14",
            "2026-03-02",
            "2026-03-20",
        ],
    }
)
customers = pd.DataFrame(
    {
        "cust_id": [101, 102, 103, 104],
        "name": ["Alice", "Bob", "Carol", "Dave"],
        "city": ["深圳", "广州", "深圳", "北京"],
        "level": ["VIP", "普通", "普通", "VIP"],
    }
)

print("=" * 60)
print("【1】.dt 时间序列：把字符串转成日期，再提取年月/季度")
print("=" * 60)
orders["created"] = pd.to_datetime(orders["created"])
orders["month"] = orders["created"].dt.to_period("M")  # 月份
orders["quarter"] = orders["created"].dt.to_period("Q")  # 季度
print(orders[["order_id", "created", "month", "quarter"]].to_string(index=False))

print("\n" + "=" * 60)
print("【2】.str 字符串：不用循环，整列做字符串操作")
print("=" * 60)
print("城市大写:", customers["city"].str.upper().tolist())
print("名字长度:", customers["name"].str.len().tolist())

print("\n" + "=" * 60)
print("【3】cut 分箱：把连续数值切成区间（如金额分档）")
print("=" * 60)
bins = [0, 100, 500, np.inf]
labels = ["小额", "中额", "大额"]
orders["amount_level"] = pd.cut(orders["amount"], bins=bins, labels=labels)
print(orders[["order_id", "amount", "amount_level"]].to_string(index=False))

print("\n" + "=" * 60)
print("【4】merge 合并：类似 SQL JOIN，把客户信息拼到订单上")
print("=" * 60)
merged = orders.merge(customers, on="cust_id", how="left")  # 左连接
print(merged[["order_id", "cust_id", "amount", "name", "city"]].to_string(index=False))

print("\n" + "=" * 60)
print("【5】groupby 分组聚合：按城市/客户统计（类似 GROUP BY）")
print("=" * 60)
# 只看成功支付的
valid = merged[(merged["status"] == "paid") & merged["name"].notna()]
summary = valid.groupby("city").agg(
    订单数=("order_id", "count"),
    总金额=("amount", "sum"),
    平均金额=("amount", "mean"),
)
print(summary.to_string())

print("\n" + "=" * 60)
print("【6】groupby + transform：分组计算后把结果'对齐'回每一行")
print("=" * 60)
# 每个客户的平均订单金额，作为新列加回每一行（行数不变）
merged["cust_avg"] = valid.groupby("cust_id")["amount"].transform("mean")
print(merged[["order_id", "cust_id", "amount", "cust_avg"]].to_string(index=False))

print("\n" + "=" * 60)
print("【7】pivot_table 透视表：行=城市，列=状态，值=金额")
print("=" * 60)
pivot = pd.pivot_table(
    merged,
    index="city",
    columns="status",
    values="amount",
    aggfunc="sum",
    fill_value=0,
)
print(pivot.to_string())

print("\n" + "=" * 60)
print("【8】缺失值处理：fillna 填充 / dropna 删除")
print("=" * 60)
print("缺失 cust_id 的行数:", int(orders["cust_id"].isna().sum()))
filled = orders.copy()
filled["cust_id"] = filled["cust_id"].fillna(-1)  # 用 -1 标记未知
print("填充后缺失数:", int(filled["cust_id"].isna().sum()))

print("\n" + "=" * 60)
print("【9】concat 拼接：多张表上下堆在一起")
print("=" * 60)
a = pd.DataFrame({"x": [1, 2]})
b = pd.DataFrame({"x": [3, 4]})
print(pd.concat([a, b], ignore_index=True).to_string(index=False))

print("\n完成。")
