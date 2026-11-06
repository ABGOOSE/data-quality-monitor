# 项目相关 pandas 操作详解（通俗版）

> 本文档只讲 **data-quality-monitor 项目里真正用到的 pandas 操作**，每个操作都按
> **「是什么 → 为什么这么用 → 用在哪」** 讲，并给出项目里的真实代码和可单独运行的小例子。
> 环境：pandas 3.0.5，Python 3.13。

---

## 目录

1. [先认识两个核心数据结构](#一先认识两个核心数据结构)
2. [数据读取：read_csv / read_sql_table](#二数据读取)
3. [数据写出：to_csv / to_sql](#三数据写出)
4. [查看数据：len / columns / 取列](#四查看数据)
5. [缺失值：isna / isnull / dropna](#五缺失值处理)
6. [布尔掩码：项目的核心思维](#六布尔掩码项目的核心思维)
7. [统计计算：sum / mean / std / round](#七统计计算)
8. [去重：duplicated](#八去重duplicated)
9. [集合判断：isin](#九集合判断isin)
10. [类型转换：astype / int](#十类型转换)
11. [向量化与广播：最重要的思维](#十一向量化与广播)
12. [计算下推：处理大表的正确姿势](#十二计算下推处理大表的正确姿势)
13. [项目操作速查表](#十三项目操作速查表)
14. [动手练习](#十四动手练习)

---

## 本文档统一使用的示例数据

后面的小例子都用这张表，你可以先在 Python 里跑出来：

```python
import pandas as pd

df = pd.DataFrame(
    {
        "order_id": [1, 2, 3, None],
        "amount": [100, 250, 80, 999],
        "status": ["paid", "paid", "refund", "paid"],
    }
)
print(df)
```

输出：

```
   order_id  amount  status
0       1.0     100    paid
1       2.0     250    paid
2       3.0      80  refund
3       NaN     999    paid
```

---

## 一、先认识两个核心数据结构

### 1. DataFrame（数据框）—— 一张二维表

- **是什么**：pandas 里的"整张表"，有行有列，像 Excel 的一个 sheet。
- **为什么**：我们处理的业务数据天然是表格，DataFrame 就是它在内存里的样子。
- **用在哪**：项目里数据一加载进来就是 DataFrame，表级规则（如 `row_count`）收到的也是它。

```python
type(df)  # <class 'pandas.core.frame.DataFrame'>
```

### 2. Series（序列）—— 表中的一列

- **是什么**：DataFrame 里的**单独一列**，带一组值和对应的行标签（index）。
- **为什么**：列级检查（非空、唯一、范围）都是针对"某一列"做的，所以函数收的是 Series。
- **用在哪**：项目里所有 `check_xxx` 列级规则的第一个参数都是 `pd.Series`。

```python
s = df["amount"]   # 取出一列，就是 Series
print(s)
```

输出：

```
0    100
1    250
2     80
3    999
Name: amount, dtype: int64
```

> **关系**：DataFrame 由多个 Series 拼起来；Series 是"一列"，DataFrame 是"多列"。

---

## 二、数据读取

### 1. pd.read_csv：把 CSV 文件读成 DataFrame

- **是什么**：读取逗号分隔的文本文件，自动解析成表格。
- **为什么**：CSV 是最通用的数据交换格式，不用装数据库就能用。
- **用在哪**：`core/data_loader.py` 的 `load_csv`。

```python
df = pd.read_csv("data/TableA.csv")
```

**项目里的真实代码（data_loader.py）：**

```python
def load_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)
```

### 2. pd.read_sql_table：把数据库整表读成 DataFrame

- **是什么**：通过 SQLAlchemy 连接，把一张数据库表（相当于 `SELECT * FROM 表`）读进来。
- **为什么**：接数据库后，数据不用先导 CSV，直接从库里读。
- **用在哪**：`data_loader.py` 的 `load_table`。

```python
from sqlalchemy import create_engine

engine = create_engine("sqlite:///data/demo.db")
df = pd.read_sql_table("TableA", engine)
engine.dispose()
```

> 还有个 `pd.read_sql("SELECT ...", engine)` 可以写自定义查询，而不是读整表。

---

## 三、数据写出

### 1. df.to_csv：写回 CSV 文件

- **是什么**：把 DataFrame 存成 CSV 文本。
- **为什么**：方便导出、给别人、留档。
- **用在哪**：项目测试里造临时 CSV。

```python
df.to_csv("output.csv", index=False)   # index=False 不写行号列
```

### 2. df.to_sql：写进数据库（重点）

- **是什么**：把 DataFrame 写进数据库的一张表，**内部自动"先建表、再插数据"**。
- **为什么**：不用手写 CREATE TABLE 和一堆 INSERT。
- **用在哪**：`scripts/build_dm_demo.py`、`build_demo_db.py`。

```python
df.to_sql("TableA", engine, if_exists="replace", index=False)
```

**关键参数：**

| 参数 | 含义 |
|------|------|
| `name` | 目标表名 |
| `con` | 数据库连接（engine） |
| `if_exists` | 表已存在怎么办：`fail` 报错 / `replace` 重建 / `append` 追加 |
| `index` | 是否把行索引写进去，**一般设 False** |

> 上一轮用 `echo=True` 已验证它内部执行顺序是：`CREATE TABLE ...` → `INSERT ...`。

---

## 四、查看数据

### 1. len()：数行数 / 元素个数

- **是什么**：Python 内置函数，pandas 对它做了支持，返回行数（DataFrame）或元素数（Series）。
- **为什么**：检查规则里几乎都要知道"总共有多少行"。
- **用在哪**：项目里每个检查函数都有 `total_count = len(series)`。

```python
len(df)            # 4（DataFrame 返回行数）
len(df["amount"])  # 4（Series 返回元素个数）
```

### 2. df.columns：拿到所有列名

- **是什么**：DataFrame 的属性，保存全部列名。
- **为什么**：要判断"配置里的列在数据里存不存在"。
- **用在哪**：`checker.py` 的 `if column not in df.columns`。

```python
print(df.columns)
# Index(['order_id', 'amount', 'status'], dtype='object')
```

### 3. df[列名]：取出一列

- **是什么**：用方括号加列名，从 DataFrame 里取出一列 Series。
- **为什么**：列级检查要先把目标列取出来。
- **用在哪**：`run_checks` 里 `series = df[column]`。

```python
s = df["amount"]   # 取出 amount 列
```

> 注意：这里的 `column` 必须是真实存在的列名，否则报 `KeyError`。项目里先用 `if column not in df.columns: continue` 挡住了。

### 4. 其他常用查看方法（了解即可）

```python
df.head(2)    # 前 2 行
df.tail(2)    # 后 2 行
df.shape      # (4, 3) = 4 行 3 列
df.dtypes     # 每列的数据类型
df.info()     # 整体信息（行数、类型、缺失）
df.describe() # 数值列的统计摘要
```

---

## 五、缺失值处理

### 1. isna()：判断每个元素是不是空

- **是什么**：返回一组**布尔值**（True/False），元素是空就 True。
- **为什么**：数空值、做空值检查全靠它。
- **用在哪**：`check_not_null`、`check_null_ratio`。

```python
print(df["order_id"].isna())
```

输出：

```
0    False
1    False
2    False
3     True
Name: order_id, dtype: bool
```

### 2. isnull()：isna 的别名

- **是什么**：`isnull()` 和 `isna()` **效果完全一样**，只是两个名字。
- **为什么**：pandas 为了兼容不同习惯（SQL 里叫 NULL）保留了两个写法。
- **建议**：项目统一用 `isna()`，记住一个就行。

### 3. dropna()：删掉空值

- **是什么**：返回一个去掉空元素的新 Series（不改变原数据）。
- **为什么**：很多规则"空值归 not_null 管"，做数值/枚举检查时先把空值剔除。
- **用在哪**：`unique`、`range`、`zscore`、`allowed_values` 都先 `dropna()`。

```python
s = df["order_id"]
print(s.dropna())   # 空的那一行被去掉，只剩 3 个值
```

### 4. fillna()：填充空值（了解）

```python
df["order_id"].fillna(-1)   # 空值用 -1 代替
```

---

## 六、布尔掩码：项目的核心思维

> **布尔掩码（boolean mask）** 是这个项目用得最多的机制，务必理解。

### 1. 比较运算：得到一组 True/False

- **是什么**：对整列做比较（`> < >= <= == !=`），每个元素比较后得到 True 或 False。
- **为什么**：不用逐行判断，一条命令整列比完。
- **用在哪**：`range` 检查。

```python
print(df["amount"] > 200)
```

输出：

```
0    False
1     True
2    False
3     True
Name: amount, dtype: bool
```

### 2. 逻辑组合：&（与）、|（或）、~（非）

- **是什么**：把多组布尔值组合起来。
- **为什么**：复杂条件需要"并且 / 或者 / 取反"。
- **用在哪**：
  - `range`：`(x < min) | (x > max)`（**或**）
  - `allowed_values`：`~isin(...)`（**取反**）

```python
mask = (df["amount"] < 100) | (df["amount"] > 900)  # 小于100 或 大于900
print(mask)
```

> ⚠️ 注意：pandas 里用的是**单个符号** `& | ~`，不是 Python 的 `and or not`；
> 而且每个比较条件通常要加括号，否则会因运算优先级出错。

### 3. 对布尔掩码做 .sum()：数有多少个 True

- **是什么**：True 当作 1，False 当作 0，求和就是"满足条件的个数"。
- **为什么**：这是数违规、数异常最方便的方式。
- **用在哪**：项目里几乎所有 `xxx_count` 都这么算。

```python
mask = df["amount"] > 200
print(int(mask.sum()))   # 2（有 2 个 True）
```

**项目里的真实代码（range 检查）：**

```python
out_of_range_count = int(((non_null < min_value) | (non_null > max_value)).sum())
```

---

## 七、统计计算

### 1. .sum()：求和

```python
df["amount"].sum()   # 1429（100+250+80+999）
```

### 2. .mean()：平均值

- **是什么**：所有非空值的平均数。
- **用在哪**：`zscore` 里算均值。

```python
df["amount"].mean()   # 357.25
```

### 3. .std()：标准差

- **是什么**：衡量数据"波动有多大"，值越分散 std 越大。
- **用在哪**：`zscore` 里算标准差。

```python
df["amount"].std()
```

### 4. round()：保留小数位

- **是什么**：Python 内置函数，控制比率的小数位数。
- **为什么**：比率（如 0.333333...）截取 4 位更整洁。
- **用在哪**：所有 `ratio` 字段。

```python
round(1 / 3, 4)   # 0.3333
```

### 5. .abs()：取绝对值

- **是什么**：把负数变正，正数不变。
- **用在哪**：`zscore` 里 `z_scores = (...).abs()`，因为只关心偏离大小、不关心方向。

```python
pd.Series([-3, 2, -1]).abs()   # [3, 2, 1]
```

---

## 八、去重：duplicated

### duplicated()：标记重复值

- **是什么**：返回布尔掩码，一个值如果**前面出现过**（第二次及以后）就标 True。
- **为什么**：数有多少个重复，做唯一检查。
- **用在哪**：`check_unique`。

```python
s = pd.Series([10, 20, 10, 30, 20])
print(s.duplicated())
```

输出：

```
0    False
1    False
2     True   # 10 重复了
3    False
4     True   # 20 重复了
dtype: bool
```

配合 `.sum()` 数重复个数：

```python
int(s.duplicated().sum())   # 2
```

**项目里的真实代码：**

```python
non_null = series.dropna()
duplicate_count = int(non_null.duplicated().sum())
```

> 相关的还有 `drop_duplicates()`：直接把重复值删掉，只留第一个。

---

## 九、集合判断：isin

### isin(列表)：判断值是否在某个集合里

- **是什么**：返回布尔掩码，值在给定列表里就 True。
- **为什么**：枚举列（状态、渠道）要判断"是不是允许的几个选项之一"。
- **用在哪**：`check_allowed_values`。

```python
allowed = ["paid", "shipped"]
print(df["status"].isin(allowed))
```

输出：

```
0     True
1     True
2    False   # refund 不在集合里
3     True
Name: status, dtype: bool
```

配合 `~` 取反，数"不在集合里"的违规个数：

```python
int((~df["status"].isin(allowed)).sum())   # 1
```

**项目里的真实代码：**

```python
disallowed_count = int((~non_null.isin(allowed_values)).sum())
```

---

## 十、类型转换

### 1. .astype()：转换数据类型

- **是什么**：把整列转成指定类型，返回新列。
- **为什么**：做数学计算前要确保是数值（比如从 CSV 读进来可能是字符串）。
- **用在哪**：`zscore` 里 `.astype(float)`。

```python
s = pd.Series(["1", "2", "3"])
print(s.astype(float))   # 字符串变成浮点数
```

### 2. int()：把 numpy/pandas 数值转成普通 Python 整数

- **是什么**：Python 内置函数。
- **为什么**：`.sum()` 返回的是 numpy 数字，转成 `int` 才能写进 JSON 报告、显示更干净。
- **用在哪**：所有计数 `int(... .sum())`。

```python
int(df["amount"].sum())   # 1429，普通 Python int
```

---

## 十一、向量化与广播

> 这是贯穿整个项目、也是 pandas 最值钱的思维。

### 1. 向量化：一条命令算整列

- **是什么**：不写 for 循环，直接对整列做运算，底层由 C 一次性算完。
- **为什么**：极快（100 万行毫秒级），代码还短。
- **用在哪**：项目所有检查都是向量化，没有一个手写循环。

```python
# 整列每个元素都 +1，不用循环
df["amount"] + 1
```

### 2. 广播：列和单个数字自动对齐运算

- **是什么**：一个 Series 和一个标量（单个数字）运算时，这个数字自动"广播"到每个元素。
- **用在哪**：`zscore` 的计算。

```python
# mean 是一个数字，non_null 是整列；相减时 mean 自动作用到每个元素
z_scores = ((non_null - mean) / std).abs()
```

### 3. 运算优先级（写代码的选择顺序）

```
向量化运算  >  pandas 内置函数  >  apply  >  手写 for 循环
（最快）                                        （最慢，尽量避免）
```

> `apply` 是逐行跑 Python，明显慢；只有向量化表达不了的复杂逻辑才用它。

---

## 十二、计算下推：处理大表的正确姿势

> 前面读数据库用的是 `read_sql_table`（整表 `SELECT *`）。但真实生产里表可能有上千万、上亿行，
> 整张拉进 pandas 会直接**撑爆内存**。这一章讲处理大表的标准工程方法——**计算下推（pushdown）**。

### 1. 是什么：计算下推

- **是什么**：把"过滤、聚合、JOIN"这些计算**推到数据库里先做**，让数据在原地算好，只把小结果拉进 pandas。
- **一句话理解**：让计算去找数据，而不是把数据搬来找计算。
- **为什么**：数据库有索引、并行、向量化执行引擎，在服务端算又快又省；整表搬到单机既慢又爆内存。
- **用在哪**：凡是数据在库里、且数据量较大的场景，都应该这么做；pandas 只负责拿到小结果后的精细处理。

### 2. 关键区别：read_sql_table vs read_sql

| 函数 | 实际执行 | 适合 |
|------|---------|------|
| `read_sql_table("表")` | `SELECT * FROM 表`（整表） | 小表、确实要全量 |
| `read_sql(sql)` | 你写的任意 SQL，可先过滤/聚合 | 大表，只取需要的小结果 |

```python
# ❌ 不要这样：整表拉，大表爆内存
df = pd.read_sql_table("big_orders", engine)

# ✅ 要这样：SQL 先在库里算小，只拉结果
sql = """
SELECT city,
       COUNT(*)    AS order_cnt,
       SUM(amount) AS total_amount,
       AVG(amount) AS avg_amount
FROM big_orders
WHERE created >= '2026-02-01'
GROUP BY city
"""
df = pd.read_sql(sql, engine)
```

> 实测：10 万行的表，整表拉取是 100000 行；用上面的 SQL 下推聚合后，只返回 **2 行**。

### 3. 封装 SQL 的三种常见做法

#### 做法一：参数化查询（复用 + 防注入）

- **是什么**：用 `:占位符` 传参数，而不是把值拼进 SQL 字符串。
- **为什么**：同一条 SQL 能反复用不同参数调用；更重要的是**防止 SQL 注入**（安全红线）。

```python
from sqlalchemy import text

sql = text("SELECT * FROM big_orders WHERE city = :city AND created >= :start")
df = pd.read_sql(sql, engine, params={"city": "深圳", "start": "2026-02-01"})
```

> 注意：用 `text()` 包起来的 SQL 才能用 `:名字` 占位符，参数通过 `params=` 传。

#### 做法二：把 SQL 放进单独的 .sql 文件

- **是什么**：长 SQL 独立成 `.sql` 文件，Python 读取后执行。
- **为什么**：SQL 长了之后，塞在 Python 字符串里难读、难维护；独立文件还能让 SQL 工具高亮、格式化。

```python
from pathlib import Path

sql = Path("queries/city_summary.sql").read_text(encoding="utf-8")
df = pd.read_sql(sql, engine)
```

#### 做法三：用数据库视图（VIEW）

- **是什么**：在数据库里先建好视图，pandas 直接读视图。
- **为什么**：复杂逻辑固化在库里，多个程序共享；pandas 端代码极简。

```sql
-- 在数据库里先建视图
CREATE VIEW v_city_summary AS
SELECT city, COUNT(*) AS order_cnt, SUM(amount) AS total_amount
FROM big_orders
GROUP BY city;
```

```python
df = pd.read_sql_table("v_city_summary", engine)  # 读视图，本质还是小结果
```

### 4. 避免大表的完整手段清单

> 1. **只 SELECT 需要的列，绝不 `SELECT *`**：列越少，传输和内存占用越小。
> 2. **WHERE 先过滤**：限定时间范围、业务条件，数据库能用索引快速定位，少扫数据。
> 3. **能在库里 GROUP BY / JOIN 的，就别拉到 pandas 再做**：服务端聚合后行数大幅减少。
> 4. **chunksize 分块读取**：结果仍然较大时，每次只持有一小块，处理完再读下一块。
>
> ```python
> total = 0
> for chunk in pd.read_sql(sql, engine, chunksize=10000):
>     # 内存里永远只有 1 万行，处理完这一块才读下一块
>     total += len(chunk)
> ```
>
> 5. **分区裁剪（partition pruning）**：查分区表时，WHERE 命中分区键，数据库只扫相关分区，不碰全表。

### 5. 完整可运行示例（SQLite，可直接跑）

```python
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

# 造一张 10 万行的"大表"，写进内存 SQLite
n = 100000
big = pd.DataFrame(
    {
        "id": np.arange(n),
        "city": np.where(np.arange(n) % 3 == 0, "广州",
                         np.where(np.arange(n) % 3 == 1, "深圳", "北京")),
        "amount": (np.arange(n) % 1000) + 10,
        "created": np.where(np.arange(n) % 3 == 0, "2026-01-15",
                            np.where(np.arange(n) % 3 == 1, "2026-02-15", "2026-03-15")),
    }
)
engine = create_engine("sqlite://")
big.to_sql("big_orders", engine, index=False)

# 对比 1：整表拉取
print("整表行数:", len(pd.read_sql_table("big_orders", engine)))  # 100000

# 对比 2：下推聚合后只拉 2 行
sql = """SELECT city, COUNT(*) AS order_cnt, SUM(amount) AS total_amount
         FROM big_orders WHERE created >= '2026-02-01' GROUP BY city"""
df_small = pd.read_sql(sql, engine)
print("下推后行数:", len(df_small))  # 2

# 对比 3：参数化查询
param_sql = text("SELECT * FROM big_orders WHERE city = :city AND created >= :start")
df_param = pd.read_sql(param_sql, engine, params={"city": "深圳", "start": "2026-02-01"})
print("参数化返回行数:", len(df_param))  # 33333

engine.dispose()
```

### 6. 为什么这样最优

- **数据不动**：计算在数据库服务端完成，享受索引、并行、向量化执行。
- **网络传输少**：只传结果，不传原始大表。
- **内存安全**：pandas 里永远是小 DataFrame，配合 chunksize 可处理任意大的表。
- **职责清晰**：SQL 干重活（大规模集合运算），pandas 干精细活（建模、画图、复杂逻辑）。

> **小结**：处理大表用 `read_sql` 而不是 `read_sql_table`，让数据库先过滤、聚合、JOIN 把大表算小，
> 再配合参数化、视图、`chunksize` 和分区裁剪，就能在不爆内存的前提下处理任意大的表。

---

## 十三、项目操作速查表

| pandas 操作 | 作用 | 项目里出现的位置 |
|-------------|------|-----------------|
| `pd.read_csv` | 读 CSV | `data_loader.load_csv` |
| `pd.read_sql_table` | 读数据库整表 | `data_loader.load_table` |
| `pd.read_sql` | 写自定义 SQL，下推计算只取小结果 | 第十二章（处理大表） |
| `df.to_sql` | 写进数据库 | `build_dm_demo.py`、`build_demo_db.py` |
| `df.to_csv` | 写 CSV | 测试里造数据 |
| `len(series/df)` | 数行数 | 所有检查函数 |
| `df.columns` | 取列名 | `run_checks` |
| `df[column]` | 取一列 | `run_checks` |
| `.isna()` | 判断空值 | `not_null`、`null_ratio` |
| `.dropna()` | 删空值 | `unique/range/zscore/allowed_values` |
| `.duplicated()` | 标记重复 | `check_unique` |
| `.isin()` | 是否在集合里 | `check_allowed_values` |
| `.sum()` | 求和 / 数 True | 所有计数 |
| `.mean()` | 平均值 | `check_zscore` |
| `.std()` | 标准差 | `check_zscore` |
| `.abs()` | 绝对值 | `check_zscore` |
| `.astype(float)` | 转浮点 | `check_zscore` |
| `int(...)` | 转 Python 整数 | 所有计数 |
| `round(...)` | 保留小数 | 所有比率 |
| `& \| ~` | 且 / 或 / 非 | `range`、`allowed_values` |

---

## 十四、动手练习

> 用下面的代码自己改、自己跑，巩固理解。预期答案写在注释里。

```python
import pandas as pd

data = pd.DataFrame(
    {
        "id": [1, 2, 3, 4, None],
        "score": [60, 95, 60, 100, 55],
        "grade": ["A", "B", "A", "C", "B"],
    }
)

# 1. 一共有多少行？
print(len(data))                          # 5

# 2. id 列有几个空值？
print(int(data["id"].isna().sum()))        # 1

# 3. score 列有几个重复值？
print(int(data["score"].duplicated().sum()))  # 1（60 重复）

# 4. score 大于 90 的有几行？
print(int((data["score"] > 90).sum()))     # 2（95 和 100）

# 5. grade 不在 ["A", "B"] 里的有几个？
print(int((~data["grade"].isin(["A", "B"])).sum()))  # 1（C）

# 6. 去掉空值后，id 还剩几个？
print(len(data["id"].dropna()))            # 4

# 7. score 的平均值是多少？
print(data["score"].mean())                # 74.0
```

---

## 一句话总结

> 这个项目对 pandas 的使用可以概括成一条主线：
> **用 `read_csv/read_sql_table` 把数据读成 DataFrame → 用 `df[列]` 取出 Series →
> 用「比较 + `&|~`」做出布尔掩码 → 用 `.sum()` 数违规/异常 → 用 `mean/std` 做统计 →
> 用 `to_sql/to_csv` 写出。**
> 全程向量化、不写循环，这就是 pandas 又快又简洁的根本原因。
