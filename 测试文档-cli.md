# data-quality-monitor 测试操作步骤手册

> 这是一份操作手册：每一步输什么命令、预期看到什么、出问题怎么办，照着做就能把全部测试跑通。
>
> 环境：Windows + PowerShell + 项目根目录 `E:\github1\data-quality-monitor`
>
> 当前测试规模：**114 个测试，分布在 6 个测试文件**。

---

## 第 0 步：打开 PowerShell

按 `Win` 键，输入 `powershell`，回车，打开 PowerShell 窗口。

> 不要用 PowerShell ISE，用普通 PowerShell 窗口即可。

---

## 第 1 步：进入项目目录

```powershell
cd E:\github1\data-quality-monitor
```

**验证**：命令行前面应该变成：

```
PS E:\github1\data-quality-monitor>
```

---

## 第 2 步：激活虚拟环境（关键！）

虚拟环境 `.venv` 里装着 pytest、ruff、dqm 这些工具。不激活就用不了它们。

```powershell
.\.venv\Scripts\Activate.ps1
```

**验证（激活成功的标志）**：命令行最前面出现 **`(.venv)`**：

```
(.venv) PS E:\github1\data-quality-monitor>
```

**如果报错**：

```
无法加载文件 ...Activate.ps1，因为在此系统上禁止运行脚本
```

说明系统禁止运行脚本，执行下面这条（只需一次）：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

弹出确认时输入 `Y` 回车，然后再执行一次 `Activate.ps1`。

**不想激活？** 可以不激活，用完整路径调用（后面所有命令前面都加上 `E:\github1\data-quality-monitor\.venv\Scripts\`）：

```powershell
E:\github1\data-quality-monitor\.venv\Scripts\pytest.exe
```

---

## 第 3 步：跑全部测试（最常用）

```powershell
pytest -q
```

> `-q` 是 quiet（安静模式），只显示进度点和最后汇总，输出更干净。

**期望输出**（最后一行）：

```
114 passed in 1.6s
```

**怎么看输出**：

- 那一串 `.`（点号）：每个 `.` 代表一个测试通过
- 出现 `F`：有测试**断言失败**（结果和预期不符）
- 出现 `E`：有测试**运行时报错**（比如 ImportError）

**如果失败**：往上翻输出，找到 `====== FAILURES ======` 段落，那里有每个失败测试的完整原因，格式是：

```
_____ test_xxx _______

    def test_xxx():
        ...
>       assert ...
E       AssertionError: ...
```

`>` 指向出错的那一行代码，`E` 是具体的错误信息。

---

## 第 4 步：跑单个文件 / 单个测试（调试时用）

```powershell
# 只跑 test_checker.py 这一个文件
pytest tests/test_checker.py

# 只跑一个测试（名字用 文件::测试函数）
pytest tests/test_checker.py::test_zscore_detects_outliers

# 按关键字过滤（跑所有名字里含 zscore 的测试）
pytest tests/test_checker.py -k zscore

# 显示每个测试的详细名字
pytest -v
```

> 每次跑 114 个太慢？开发时就用 `-k` 只跑你正在改的那一组，最后交付前再跑全量。

---

## 第 5 步：跑代码规范检查

```powershell
ruff check .
ruff format --check .
```

**期望输出**：

```
All checks passed!
18 files already formatted
```

- `ruff check .`：检查代码有没有语法、导入、风格问题（lint）。
- `ruff format --check .`：检查格式是否统一，`--check` 只检查、不改文件；显示 `18 files already formatted` 说明全部符合规范。

> 文档（.md）和 notes 已在 pyproject 里配置为不参与检查，所以文档里的示例代码不会影响结果。

**如果报错**：输出会指出位置，例如：

```
E501 Line too long (101 > 100)
   --> core/checker.py:42:5
```

意思是 `core/checker.py` 第 42 行第 5 列开始，某行超过 100 字符。打开对应行改短即可。

---

## 第 6 步：跑 CLI 端到端测试（模拟真实使用）

测试通过 ≠ 命令行能跑。端到端测试用真实命令验证整条链路。

> 每条命令后可以输入 `$LASTEXITCODE` 查看退出码。退出码含义：
> - `0` = 检查跑完，数据全部合格
> - `1` = 检查跑完，但数据有问题
> - `2` = 命令本身用错了（表名写错、文件找不到等）

### 6.1 单表正常数据 → 6 条全 PASS，退出码 0

```powershell
dqm --table TableA --data data/TableA.csv
$LASTEXITCODE
```

**期望**：看到 `Table: TableA` 和 6 条 `[PASS]`，退出码 `0`。

### 6.2 单表坏数据 → 5 条 FAIL，退出码 1

```powershell
dqm --table TableA --data data/TableA_bad.csv
$LASTEXITCODE
```

**期望**：5 条 `[FAIL]`（not_null / unique / range / allowed_values / null_ratio）+ 1 条 `[PASS]`（row_count，因为有 3 行），退出码 `1`。

### 6.3 单表空数据 → 行数规则 FAIL，退出码 1

```powershell
dqm --table TableA --data data/TableA_empty.csv
$LASTEXITCODE
```

**期望**：5 条 `[PASS]` + 1 条 `[FAIL]`（row_count，0 行，要求至少 1 行），退出码 `1`。

### 6.4 异常值检测 → 尖峰必须被抓，退出码 1

```powershell
dqm --table TableB --data data/TableB.csv
$LASTEXITCODE
```

**期望**：

```
[FAIL] request_count :: zscore  (outlier_count=1, total_count=15, outlier_ratio=0.0667, threshold=3)
```

退出码 `1`。

### 6.5 多表批量 → 一条命令查多张表，退出码 1

```powershell
dqm --table TableA TableB --data data/TableA.csv data/TableB.csv
$LASTEXITCODE
```

**期望**：依次出现 `Table: TableA` 和 `Table: TableB`，两张表都检查（共 7 条检查，6 过 1 败），退出码 `1`。

> 注意：`--data` 后面文件的顺序必须和 `--table` 后面表的顺序一一对应。

### 6.6 --all 全量检查 → 自动查配置里所有表

```powershell
dqm --all --data data/TableA.csv data/TableB.csv
```

**期望**：不用手动列表名，工具自动把 rules.yaml 里的两张表都查一遍。

### 6.7 --tables-file 从文件读表清单（项目已自带清单）

`config/` 下已经有现成的 `config/tables.txt`（内容是 TableA、TableB），直接引用它的地址：

```powershell
dqm --tables-file config/tables.txt --data data/TableA.csv data/TableB.csv
$LASTEXITCODE
```

**期望**：注释和空行被忽略，正确读出两张表并检查，退出码 `1`。

### 6.8 --data-file 从文件读 CSV 路径清单（项目已自带清单）

`config/` 下已经有现成的 `config/data_list.txt`（内容是 data/TableA.csv、data/TableB.csv）：

```powershell
dqm --table TableA TableB --data-file config/data_list.txt
$LASTEXITCODE
```

**期望**：正确读出两个 CSV 路径，两张表都检查，退出码 `1`。

### 6.9 全文件驱动（两个自带清单一起用）

表名、CSV 路径都从文件读，命令里不用写任何具体表名或路径：

```powershell
dqm --tables-file config/tables.txt --data-file config/data_list.txt
```

> 清单里的 `data/...` 是相对路径，必须在项目根目录运行 dqm 才有效。

### 6.10 --dry-run 预检（只看范围，不跑检查）

```powershell
dqm --table TableA --data data/TableA.csv --dry-run
```

**期望**：看到 `[DRY-RUN]` 和 `[ok] TableA`，但没有 `[PASS]` 结果行，退出码 `0`；预检不读数据、不写任何文件。

### 6.11 --skip-missing 宽松模式（跳过无规则表，继续查）

```powershell
dqm --table TableA NoSuch --data data/TableA.csv data/TableA_bad.csv --skip-missing
```

**期望**：先打印警告 `[skip] NoSuch`，然后正常输出 TableA 的 6 条结果，退出码 `0`。

### 6.12 报告导出（--report）→ 文件真的生成

```powershell
dqm --table TableA --data data/TableA.csv --report json --output report_demo.json
```

**期望**：最后一行出现 `Report written to report_demo.json`，退出码仍是 `0`（导出不影响退出码）。

查看内容：

```powershell
Get-Content report_demo.json -Encoding UTF8
```

**期望**：能看到 `"total_checks": 6`、`"passed_checks": 6`、`"failed_checks": 0`。

Markdown 格式同理：

```powershell
dqm --table TableA --data data/TableA_bad.csv --report markdown --output report_demo.md
```

> 演示完可删：`Remove-Item report_demo.json, report_demo.md`

---

> `dqm` 命令找不到？回到第 2 步——八成是 venv 没激活。备选方案：
> ```powershell
> E:\github1\data-quality-monitor\.venv\Scripts\dqm.exe --table TableA --data data/TableA.csv
> ```
> 或者用 python 模块方式：
> ```powershell
> E:\github1\data-quality-monitor\.venv\Scripts\python.exe -m core.cli --table TableA --data data/TableA.csv
> ```

---

## 第 7 步：交付前的完整检查清单（每次改完代码跑一遍）

按顺序执行，全过才算完成：

| 序号 | 命令 | 期望 |
|------|------|------|
| 1 | `pytest -q` | `114 passed`，无 F/E |
| 2 | `ruff check .` | `All checks passed!` |
| 3 | `ruff format --check .` | `18 files already formatted` |
| 4 | `dqm --table TableA --data data/TableA.csv` | 6 条全 `[PASS]`，退出码 `0` |
| 5 | `dqm --table TableA --data data/TableA_bad.csv` | 5 条 `[FAIL]`，退出码 `1` |
| 6 | `dqm --table TableA TableB --data data/TableA.csv data/TableB.csv` | 两张表都检查，退出码 `1` |
| 7 | `dqm --tables-file config/tables.txt --data-file config/data_list.txt` | 全文件驱动，退出码 `1` |

> 这套清单和 CI（GitHub Actions）里跑的是同一套东西——本地全过，推上去 CI 才会变绿。

---

## 第 8 步：TDD 红绿循环（写新功能时的标准操作）

以「加一条新规则」为例，标准流程是：

```text
① 写测试（先想清楚：通过/失败/边界/空值四个场景）
② 跑 pytest           → 期望：新测试【红】（失败），旧测试全绿
③ 写实现（checker.py）
④ 跑 pytest           → 期望：全部【绿】
⑤ 注册分派表 + 改 rules.yaml
⑥ 跑 pytest           → 期望：契约测试自动覆盖，仍然全绿
⑦ 跑第 7 步的完整清单 → 端到端验证
```

**判断红得对不对**：新测试失败的原因必须是「功能还没实现」，而不是「测试写错了」。比如 zscore 当时红的原因是 `ImportError: cannot import name 'check_zscore'`——这就对了。

---

## 附录 A：常见问题排查

| 现象 | 原因 | 解决办法 |
|------|------|---------|
| `'pytest' 不是内部或外部命令` / `无法将"pytest"项识别为 cmdlet` | venv 没激活 | 执行第 2 步激活，或改用完整路径 `.venv\Scripts\pytest.exe` |
| `无法将"dqm"项识别为...` | venv 没激活 / 没安装 | 激活 venv；若仍不行，重新 `pip install -e ".[dev]"` |
| `ModuleNotFoundError: No module named 'core'` | 没在项目根目录运行 | 先 `cd E:\github1\data-quality-monitor` 再跑 |
| `Activate.ps1 禁止运行脚本` | 系统执行策略限制 | 见第 2 步的 `Set-ExecutionPolicy` |
| 测试报 `ImportError: cannot import name 'xxx'` | 函数还没实现 / import 写错 | 检查 `core/checker.py` 里函数是否存在、测试顶部 import 是否一致 |
| ruff 报 `E501 Line too long` | 行超长（>100 字符） | 打开对应文件行，拆行或缩短 |
| 命令能跑但 `$LASTEXITCODE` 和预期不一样 | 数据文件或参数和手册不一致 | 确认命令里的表名、文件路径和手册完全一致 |

---

## 附录 B：114 个测试清单（按 6 个文件分组，对照参考）

### test_checker.py（38 个）—— 检查规则本身

| 组 | 测试 | 测什么 |
|----|------|--------|
| not_null（3） | `all_valid` / `with_nulls` / `empty_series` | 非空检查三场景 |
| unique（4） | `all_distinct` / `with_duplicates` / `ignores_nulls` / `empty_series` | 唯一性四场景 |
| range（5） | `all_within` / `with_outliers` / `boundary_values_pass` / `ignores_nulls` / `empty_series` | 范围五场景 |
| row_count（4） | `pass` / `fail` / `boundary_passes` / `empty_table` | 行数四场景 |
| run_checks（8） | `all_pass` / `detects_violations` / `skips_missing_columns` / `runs_table_rules` / `table_rule_fails_on_empty_table` / `result_carries_column_name` / `unknown_column_rule_raises` / `unknown_table_rule_raises` | 调度逻辑八场景 |
| zscore（6） | `detects_outliers` / `normal_data_passes` / `boundary_strict` / `insufficient_data_passes` / `constant_series_passes` / `ignores_nulls` | 异常检测六场景 |
| allowed_values（3） | `passes_when_all_in_set` / `fails_on_out_of_set` / `ignores_null` | 枚举值三场景 |
| null_ratio（5） | `below_threshold_passes` / `above_threshold_fails` / `boundary_equal_passes` / `all_null_does_not_crash` / `empty_series_passes` | 空值率五场景 |

### test_cli.py（38 个）—— 命令行整条链路

| 组 | 测试 | 测什么 |
|----|------|--------|
| 基础退出码（4） | `all_pass_returns_zero` / `violations_return_one` / `unknown_table_returns_two` / `missing_file_returns_two` | 三种退出码 |
| 报告（6） | `report_json_writes_file` / `report_keeps_exit_code_one` / `report_default_output_writes_to_cwd` / `no_report_writes_nothing` / `invalid_report_format_exits_two` / `default_report_path_unknown_format_raises` | 报告导出与副作用 |
| 默认路径（1） | `default_report_path_known_formats_have_correct_ext` | 自动命名后缀 |
| 多表（4） | `multi_tables_one_fails_returns_one` / `multi_tables_all_pass_returns_zero` / `multi_tables_data_count_mismatch_returns_two` / `multi_tables_unknown_name_returns_two` | 多表批量与文件数校验 |
| --all（2） | `all_flag_checks_all_tables` / `table_and_all_mutually_exclusive` | 全量与互斥 |
| 多表报告（1） | `multi_table_report_json_groups_by_table` | 多表 JSON 分组 |
| --tables-file（4） | `tables_file_reads_list_and_ignores_comments` / `tables_file_not_found_returns_two` / `tables_file_unknown_table_in_list_returns_two` / `missing_tables_report_is_structured_and_deduped` | 表清单读取与去重 |
| --dry-run（3） | `dry_run_all_valid_returns_zero` / `dry_run_missing_returns_one` / `dry_run_has_no_file_side_effect` | 预检三场景 |
| --skip-missing（3） | `skip_missing_continues_with_valid_table` / `skip_missing_uses_correct_file_mapping` / `skip_missing_all_skipped_returns_two` | 宽松模式与文件映射 |
| 缺失文件留存（5） | `strict_writes_missing_report_file` / `lenient_writes_missing_report_and_continues` / `all_skipped_still_writes_report` / `no_missing_writes_no_report` / `dry_run_does_not_write_missing_report` | 缺失表文件生成规则 |
| --data-file（5） | `data_file_reads_csv_list` / `data_file_multiple_paths` / `data_file_not_found_returns_two` / `data_file_count_mismatch_returns_two` / `tables_file_and_data_file_together` | CSV 清单与全文件驱动 |

### test_config_loader.py（4 个）—— 配置加载

| 测试 | 测什么 |
|------|--------|
| `load_rules_returns_dict` | 配置能读成字典 |
| `load_rules_structure` | 字典结构正确 |
| `all_rules_have_implementations` | 契约：每条规则有实现 |
| `rule_params_match_function_signature` | 契约：参数能对齐函数签名 |

### test_data_loader.py（7 个）—— 数据读取

| 测试 | 测什么 |
|------|--------|
| `load_csv_returns_dataframe` | CSV 读成 DataFrame |
| `load_table_returns_dataframe` | 数据库表读成 DataFrame |
| `load_dataframe_from_csv` / `load_dataframe_from_db` | 统一入口两种来源 |
| `load_dataframe_no_source_raises` / `load_dataframe_db_without_table_raises` | 缺参数时报错 |
| `csv_and_db_contents_match` | CSV 和数据库读出内容一致 |

### test_reporter.py（10 个）—— 报告导出

| 组 | 测试 | 测什么 |
|----|------|--------|
| JSON（3） | `export_json_creates_file` / `export_json_contains_summary` / `export_json_contains_all_results` | JSON 文件与汇总 |
| Markdown（4） | `export_markdown_creates_file` / `export_markdown_contains_summary` / `export_markdown_has_one_row_per_result` / `export_markdown_details_generic` | Markdown 表格 |
| 分派（3） | `export_report_dispatches_json` / `export_report_dispatches_markdown` / `export_report_unknown_format_raises` | 格式分派与异常 |

### test_validator.py（17 个）—— 配置合法性校验

| 组 | 测试 | 测什么 |
|----|------|--------|
| 整体结构（5） | `valid_config_has_no_errors` / `config_not_a_dict` / `missing_tables_key` / `tables_not_a_dict` / `tables_empty` | 顶层结构 |
| 表/列结构（4） | `table_config_not_a_dict` / `columns_not_a_dict` / `column_rule_list_not_a_list` / `checks_not_a_list` | 表与列的类型 |
| 规则字典（3） | `rule_not_a_dict` / `rule_missing_rule_key` / `rule_name_not_string` | 规则字典字段 |
| 规则名（2） | `unknown_column_rule` / `unknown_table_rule` | 未知规则拦截 |
| 参数（3） | `unexpected_parameter` / `missing_required_parameter` / `optional_parameter_can_be_omitted` | 参数对齐校验 |

---

> 合计：38 + 38 + 4 + 7 + 10 + 17 = **114 个测试**。
