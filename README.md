# data-quality-monitor

轻量级数据质量监控工具：规则写在 YAML 里，代码读配置执行检查，输出 PASS/FAIL 结果。
一个用于练习「配置驱动 + 规则引擎 + 契约测试 + CI」的数据工程实践项目。

A lightweight data quality monitoring tool. Rules are declared in YAML, checked against CSV data, and results are reported with process exit codes.

## 已实现功能

| 类型 | 规则 | 说明 |
|------|------|------|
| 列级 | `not_null` | 非空检查 |
| 列级 | `unique` | 唯一性检查（空值不算重复） |
| 列级 | `range` | 数值范围检查 `[min_value, max_value]`（边界值合法） |
| 表级 | `row_count` | 最少行数检查 `min_rows` |

- **配置驱动**：改 `config/rules.yaml` 不用改代码
- **契约测试**：YAML 里声明的每条规则，必须有对应实现且参数匹配（`tests/test_config_loader.py`），CI 每次跑测试自动拦截「配置写了、代码没写」的情况
- **Fail fast**：配置里出现未知规则名直接抛 `ValueError`，不静默跳过
- **CLI 入口**：`dqm --table <表名> --data <csv>`，有规则失败时退出码 1，可直接接 CI / Airflow 调度
- **CI**：GitHub Actions 每次 push / PR 自动跑 ruff + pytest + CLI 冒烟测试

## 快速开始

```bash
# 1. 创建虚拟环境并安装（顺便装好 dqm 命令）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
# source .venv/bin/activate
pip install -e ".[dev]"

# 2. 检查正常数据 → 全部 PASS，退出码 0
dqm --table sample_orders --data data/sample_orders.csv

# 3. 检查违规数据 → 3 条 FAIL，退出码 1
dqm --table sample_orders --data data/sample_orders_bad.csv

# 4. 检查空表 → 表级 row_count 规则 FAIL
dqm --table sample_orders --data data/sample_orders_empty.csv
```

输出示例：

```
Table: sample_orders
------------------------------------------------------------
[PASS] order_id :: not_null  (null_count=0, total_count=3, null_ratio=0.0)
[PASS] order_id :: unique  (duplicate_count=0, total_count=3, duplicate_ratio=0.0)
[PASS] amount :: range  (out_of_range_count=0, total_count=3, ...)
[PASS] table :: row_count  (row_count=3, min_rows=1)
```

## 怎么加一条新规则

1. 在 `core/checker.py` 写检查函数，返回统一 schema 的 dict（`rule` / `passed` / 指标字段）
2. 注册进分派表：列级规则进 `RULE_FUNCTIONS`，表级规则进 `TABLE_RULE_FUNCTIONS`
3. 在 `config/rules.yaml` 声明规则，**参数键名必须与函数签名对齐**
4. 在 `tests/` 补单元测试；契约测试会自动覆盖新声明的规则

## 项目结构

```
data-quality-monitor/
├── .github/workflows/ci.yml   ← CI：push/PR 自动跑 ruff + pytest
├── config/                    ← 声明要求
│   ├── __init__.py
│   └── rules.yaml             ← 规则配置（改配置不改代码）
├── core/
│   ├── __init__.py
│   ├── checker.py             ← 规则引擎：检查函数 + 分派表 + run_checks调度
│   ├── cli.py                 ← 把配置、数据、检查串成一条链，命令行入口：dqm --table --data                         ← 存放的是测试数据，即我们这套流程的原材料
│   └── config_loader.py       ← 把yaml转化成python可读，读 rules.yaml 返回字典
├── data/                      ← 示例数据（正常 / 违规 / 空表 三种 CSV）
├── tests/
│   ├── __init__.py
│   ├── test_checker.py        ← 检查逻辑单元测试，检查函数行为对不对，
│   └── test_config_loader.py  ← 契约测试查「config 和 core 对得上对不上」
├── notes/daily/               ← 每日学习日志（个人成长档案）
├── pyproject.toml             ← 依赖、ruff/pytest 配置、dqm 命令入口
├── LICENSE
└── README.md
```

## 测试

```bash
pytest          # 单元测试 + 契约测试
ruff check .    # 代码规范检查
ruff format .   # 代码格式化
```

## Roadmap

- [ ] 统计异常检测（z-score / 均值±Nσ）
- [ ] 更多规则：`regex`、`allowed_values`、`null_ratio` 阈值
- [ ] 结果导出（JSON / Markdown 报告）
- [ ] 告警（Webhook 通知）
- [ ] 接入 Airflow 定时调度

## 学习笔记

`notes/daily/` 记录了这个项目每天的开发思路、卡点和收获，按日期归档。
