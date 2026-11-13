# data-quality-monitor

轻量级数据质量监控工具：规则写在 YAML 里，代码读配置、对接 **CSV 或数据库**执行检查，输出 PASS/FAIL 结果与报告，并用进程退出码对接 CI / 调度系统。

一个用于练习「配置驱动 + 规则引擎 + 多数据源 + 日志体系 + 契约测试 + 覆盖率量化 + CI/CD」的数据工程实践项目。

A lightweight data quality monitoring tool. Rules are declared in YAML, checked against CSV or database data, and results are reported with process exit codes.

## 已实现功能

### 质量规则（7 个）

| 类型 | 规则 | 说明 |
|------|------|------|
| 列级 | `not_null` | 非空检查 |
| 列级 | `unique` | 唯一性检查（空值不算重复） |
| 列级 | `range` | 数值范围检查 `[min_value, max_value]`（边界值合法） |
| 列级 | `allowed_values` | 枚举值检查：值必须属于给定集合（空值不算违规） |
| 列级 | `null_ratio` | 缺失率阈值检查：缺失率 ≤ `max_ratio` 通过（恰好等于容忍上限不违规） |
| 列级 | `zscore` | 统计异常检测（\|z\| > threshold，默认 3σ，边界由数据自动算出） |
| 表级 | `row_count` | 最少行数检查 `min_rows` |

### 工程能力

- **配置驱动**：改 `config/rules.yaml` 不用改代码
- **配置校验**：运行前由 `validator` 检查规则名、参数、类型是否合法，错误一次性列出并以退出码 2 中止，不把坏配置带进检查
- **多数据源**：CSV 文件，或通过 SQLAlchemy 连接数据库（SQLite / MySQL / 达梦 DM8），同一套规则两种来源
- **多表批量**：`--table` 支持多表、`--all` 全量、`--tables-file` / `--data-file` 从清单文件读取
- **预检与容错**：`--dry-run` 只看哪些表有规则、不执行；`--skip-missing` 显式跳过无规则表（告警而非失败）
- **结果导出**：`--report json|markdown` 把检查结果写成报告文件（JSON 给程序、Markdown 给人）
- **全链路日志**：标准库 logging，统一格式含时间/级别/文件/函数/行号，支持 `--log-level` 调级别、`--log-file` 落盘
- **契约测试**：YAML 里声明的每条规则必须有对应实现且参数匹配，CI 自动拦截「配置写了、代码没写」
- **测试覆盖率量化**：基于 pytest-cov / coverage.py，同时统计**语句覆盖 + 分支覆盖**，列出未覆盖行；设 90% 质量门槛（不达标命令非 0 退出、CI 变红），并可生成 HTML 覆盖率报告逐行查看
- **Fail fast**：未知规则名直接抛 `ValueError`，不静默跳过
- **CI**：GitHub Actions 在 push / PR 时自动跑 ruff + pytest（多版本矩阵）+ 覆盖率门槛 + CLI 冒烟测试

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
dqm --table TableA --data data/TableA.csv

# 3. 检查违规数据 → 出现 FAIL，退出码 1
dqm --table TableA --data data/TableA_bad.csv

# 4. 检查空表 → 表级 row_count 规则 FAIL
dqm --table TableA --data data/TableA_empty.csv

# 5. 多表批量检查（表与数据顺序一一对应；TableB 含一个设计好的 zscore 异常，退出码 1）
dqm --table TableA TableB --data data/TableA.csv data/TableB.csv

# 6. 预检：只看哪些表有规则，不执行检查（仍需指定数据源占位）
dqm --all --dry-run --data data/TableA.csv data/TableB.csv

# 7. 从数据库检查（SQLite 示例）
dqm --table TableA --db sqlite:///data/demo.db

# 8. 导出业务报告（JSON / Markdown）
dqm --table TableA --data data/TableA.csv --report json --output report.json
dqm --table TableA --data data/TableA.csv --report markdown --output report.md

# 9. 调整日志级别并同时写入文件
dqm --table TableA --data data/TableA.csv --log-level DEBUG --log-file run.log
```

输出示例：

```
Table: TableA
------------------------------------------------------------
[PASS] order_id :: not_null  (null_count=0, total_count=3, null_ratio=0.0)
[PASS] order_id :: unique  (duplicate_count=0, total_count=3, duplicate_ratio=0.0)
[PASS] amount :: range  (out_of_range_count=0, total_count=3, ...)
[PASS] status :: allowed_values  (disallowed_count=0, total_count=3, ...)
[PASS] table :: row_count  (row_count=3, min_rows=1)
```

## 项目结构

```
data-quality-monitor/
├── .github/workflows/ci.yml   ← CI：push/PR 自动跑 ruff + pytest + 覆盖率 + 冒烟
├── config/
│   └── rules.yaml             ← 规则配置（改配置不改代码）
├── core/
│   ├── checker.py             ← 规则引擎：检查函数 + 分派表 + run_checks 调度
│   ├── cli.py                 ← 命令行入口，把配置/数据/检查串成一条链，决定退出码
│   ├── config_loader.py       ← 读 rules.yaml，转成 Python 字典
│   ├── data_loader.py         ← 数据源：CSV 或 SQLAlchemy 数据库，统一返回 DataFrame
│   ├── validator.py           ← 配置校验：规则名/参数/类型，运行前拦截错误
│   ├── reporter.py            ← 结果导出：JSON / Markdown，单表与多表
│   └── logging_utils.py       ← 统一日志配置：控制台/文件 handler、格式、级别
├── data/                      ← 演示数据（CSV + demo.db）
├── scripts/                   ← 演示/建库脚本（含 logging 演示、demo 库构建）
├── tests/                     ← 9 个测试文件，覆盖全部 core 模块
├── notes/daily/               ← 每日学习日志（个人成长档案）
├── pyproject.toml             ← 依赖、ruff/pytest/coverage 配置、dqm 命令入口
├── LICENSE
└── README.md
```

## 测试与质量

```bash
pytest                                          # 全量单元测试 + 契约测试
pytest --cov                                    # 跑测试并统计覆盖率
pytest --cov --cov-report=term-missing          # 覆盖率表 + 列出未覆盖的具体行号
pytest --cov --cov-report=html                  # 生成 HTML 覆盖率报告（htmlcov/，逐行高亮）
pytest -v                                       # 详细看每个用例
pytest --html=report.html --self-contained-html # 生成浏览器可看的 HTML 测试报告
pytest --junitxml=test-results.xml              # 生成 JUnit XML（供 CI 平台解析）
ruff check .                                    # 代码规范检查
ruff format .                                   # 代码格式化
```

**覆盖率量化口径**：

| 指标 | 含义 | 当前值 |
|------|------|--------|
| 语句覆盖（Stmts） | 可执行语句被测试跑到的比例 | 447 条，全部覆盖 |
| 分支覆盖（Branch） | if/else 等分支两条路是否都走到 | 144 条，全部覆盖 |
| 未覆盖（Miss） | 没跑到的语句/分支 | 0 |
| 质量门槛（fail_under） | 低于该比例命令非 0 退出、CI 变红 | 90% |

当前状态：**132 个测试全部通过，core 包覆盖率 100%**（语句 447、分支 144，零遗漏），高于 90% 门槛。

> 测试报告（`report.html`、`test-results.xml`）和 `.idea/`、`.venv/` 等均已在 `.gitignore` 忽略，不提交到仓库。

## 怎么加一条新规则

1. 在 `core/checker.py` 写检查函数，返回统一 schema 的 dict（`rule` / `passed` / 指标字段）
2. 注册进分派表：列级规则进 `RULE_FUNCTIONS`，表级规则进 `TABLE_RULE_FUNCTIONS`
3. 在 `config/rules.yaml` 声明规则，**参数键名必须与函数签名对齐**
4. 在 `tests/` 补单元测试；契约测试会自动覆盖新声明的规则
5. 全量跑 `pytest --cov` 确认通过且覆盖率不回退

## 文档索引

| 文档 | 内容 |
|------|------|
| 日志系统操作手册.md | logging 配置、级别、文件/控制台 handler、全链路日志 |
| 测试日志与报告操作手册.md | pytest 失败定位、`--tb`、JUnit XML、HTML 报告、caplog |
| 测试覆盖率操作手册.md | coverage / pytest-cov 用法与覆盖率门槛 |
| 项目验收操作手册.md | 端到端验收步骤 |
| 达梦连接操作文档.md | 达梦 DM8 驱动安装与连接 |
| pandas操作详解.md | pandas 相关知识点梳理 |

## Roadmap

- [x] 统计异常检测（z-score / 均值±Nσ）
- [x] 枚举值检查（allowed_values）
- [x] 缺失率阈值（null_ratio）
- [x] 结果导出（JSON / Markdown 报告）
- [x] 数据库数据源（SQLAlchemy，含达梦）
- [x] 全链路日志体系
- [x] 测试覆盖率量化（语句+分支，90% 门槛，HTML 报告）
- [ ] 更多规则：`regex`
- [ ] 告警（Webhook 通知）
- [ ] 接入 Airflow 定时调度

## 学习笔记

`notes/daily/` 记录了这个项目每天的开发思路、卡点和收获，按日期归档。
