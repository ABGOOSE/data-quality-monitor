# data-quality-monitor 测试操作步骤手册

> 这是一份操作手册：每一步输什么命令、预期看到什么、出问题怎么办，照着做就能把全部测试跑通。
>
> 环境：Windows + PowerShell + 项目根目录 `E:\github1\data-quality-monitor`

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
pytest
```

**期望输出**（最后一行）：

```
53 passed in 0.xx s
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

# 显示每个测试的详细名字（不加 -q 时用）
pytest -v
```

> 每次跑 34 个太慢？开发时就用 `-k` 只跑你正在改的那一组，最后交付前再跑全量。

---

## 第 5 步：跑代码规范检查

```powershell
ruff check .
ruff format --check .
```

**期望输出**（两条命令都是）：

```
All checks passed!
```

**如果报错**：输出会指出位置，例如：

```
E501 Line too long (101 > 100)
   --> core/checker.py:42:5
```

意思是 `core/checker.py` 第 42 行第 5 列开始，某行超过 100 字符。打开对应行改短即可。

---

## 第 6 步：跑 CLI 端到端测试（模拟真实使用）

测试通过 ≠ 命令行能跑。端到端测试用真实命令验证整条链路。

**6.1 正常数据 → 必须全部 PASS**

```powershell
dqm --table TableA --data data/TableA.csv
```

**期望输出**：

```
Table: TableA
------------------------------------------------------------
[PASS] order_id :: not_null  (...)
[PASS] order_id :: unique  (...)
[PASS] amount :: range  (...)
[PASS] table :: row_count  (...)
```

**6.2 验证退出码 = 0**（数据合格时工具必须"成功退出"）：

```powershell
$LASTEXITCODE
```

**期望输出**：`0`

**6.3 违规数据 → 必须有 FAIL，退出码 = 1**

```powershell
dqm --table TableA --data data/TableA_bad.csv
$LASTEXITCODE
#用 rules.yaml 里定义的规则，检查 orders.csv 这份数据，表名是 orders。
```

**期望输出**：出现 3 条 `[FAIL]`，`$LASTEXITCODE` 是 `1`。

**6.4 最新规则：统计异常检测 → 尖峰必须被抓**

```powershell
dqm --table TableB --data data/TableB.csv
```

**期望输出**：

```
[FAIL] request_count :: zscore  (outlier_count=1, total_count=15, outlier_ratio=0.0667, threshold=3)
```

`$LASTEXITCODE` 是 `1`。

**6.5 报告导出（--report）→ 文件真的生成**

```powershell
dqm --table TableA --data data/TableA.csv --report json --output report_demo.json
```

**期望输出**：最后一行 `Report written to report_demo.json`。

**验证文件内容**：

```powershell
Get-Content report_demo.json -Encoding UTF8
```

**期望输出**：看到 `"passed_checks": 3`。退出码仍是 0（导出不影响成败判断）。

```powershell
dqm --table TableA --data data/TableA_bad.csv --report markdown --output report_demo.md
```

**期望输出**：3 行 `[FAIL]` + `Report written to report_demo.md`，`$LASTEXITCODE` 是 `1`。

> 演示完可删：`Remove-Item report_demo.json, report_demo.md`

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
| 1 | `pytest` | `53 passed` |
| 2 | `ruff check .` | `All checks passed!` |
| 3 | `ruff format --check .` | `All checks passed!` |
| 4 | `dqm --table TableA --data data/TableA.csv` | 全 `[PASS]` |
| 5 | `$LASTEXITCODE`（接上条） | `0` |
| 6 | `dqm --table TableA --data data/TableA_bad.csv` | 3 条 `[FAIL]` |
| 7 | `$LASTEXITCODE`（接上条） | `1` |

> 这套清单和 CI（GitHub Actions）里跑的是同一套东西——本地全过，推上去 CI 才可能绿。

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
| `无法将"dqm"项识别为...` | venv 没激活 / 没安装 | 激活 venv；若仍不行，重新 `pip install -e ".[dev]"`
| `ModuleNotFoundError: No module named 'core'` | 没在项目根目录运行 | 先 `cd E:\github1\data-quality-monitor` 再跑 |
| `Activate.ps1 禁止运行脚本` | 系统执行策略限制 | 见第 2 步的 `Set-ExecutionPolicy` |
| 测试报 `ImportError: cannot import name 'xxx'` | 函数还没实现 / import 写错 | 检查 `core/checker.py` 里函数是否存在、`tests/test_checker.py` 顶部 import 是否一致 |
| ruff 报 `E501 Line too long` | 行超长（>100 字符） | 打开对应文件行，拆行或缩短 |

## 附录 B：53 个测试清单（对照参考）

**test_checker.py（30 个）**

| 组 | 测试 | 测什么 |
|----|------|--------|
| not_null | `all_valid` / `with_nulls` / `empty_series` | 非空检查三场景 |
| unique | `all_distinct` / `with_duplicates` / `ignores_nulls` / `empty_series` | 唯一性四场景 |
| range | `all_within` / `with_outliers` / `boundary_values_pass` / `ignores_nulls` / `empty_series` | 范围五场景 |
| row_count | `pass` / `fail` / `boundary_passes` / `empty_table` | 行数四场景 |
| run_checks | `all_pass` / `detects_violations` / `skips_missing_columns` / `runs_table_rules` / `table_rule_fails_on_empty_table` / `result_carries_column_name` / `unknown_column_rule_raises` / `unknown_table_rule_raises` | 调度逻辑八场景 |
| zscore | `detects_outliers` / `normal_data_passes` / `boundary_strict` / `insufficient_data_passes` / `constant_series_passes` / `ignores_nulls` | 统计异常六场景 |

**test_config_loader.py（4 个）**

| 测试 | 测什么 |
|------|--------|
| `load_rules_returns_dict` | 配置能读成字典 |
| `load_rules_structure` | 字典结构正确 |
| `all_rules_have_implementations` | 契约：每条规则有实现 |
| `rule_params_match_function_signature` | 契约：每个参数能对齐函数签名 |

**test_cli.py（9 个）**

| 测试 | 测什么 |
|------|--------|
| `main_all_pass_returns_zero` | 正常数据退出码 0 |
| `main_violations_return_one` | 坏数据退出码 1 |
| `main_unknown_table_returns_two` | 表不存在退出码 2（错误走 stderr） |
| `main_missing_file_returns_two` | 数据文件不存在退出码 2 |
| `main_report_json_writes_file` | `--report json` 真的生成报告文件 |
| `main_report_keeps_exit_code_one` | 坏数据 + 导出，退出码仍 1 |
| `main_report_default_output_writes_to_cwd` | 不传 `--output` 自动命名写当前目录 |
| `main_no_report_writes_nothing` | 不传 `--report` 无文件副作用（向后兼容） |
| `main_invalid_report_format_exits_two` | 非法格式 argparse 拒绝（SystemExit 2） |
