# reporter 测试：傻瓜操作手册

> 照着手册一步步做。每一步都告诉你三件事：
> **输入什么** → **应该看到什么** → **看到别的怎么办**。
>
> 环境：Windows 电脑 + PowerShell 蓝色窗口。

---

## 第 0 步 打开 PowerShell

1. 按键盘左下角的 **Win 键**（窗户图标那个键）
2. 直接打字输入：`powershell`
3. 按 **回车**
4. 屏幕上出现一个蓝色窗口（这就是 PowerShell），里面有一行 `PS C:\Users\GGDH>`

> 看到蓝色窗口 = 成功。接下来所有操作都在这个窗口里做。

---

## 第 1 步 进入项目文件夹

**输入（把下面整行复制进去，按回车）：**

```
cd E:\github1\data-quality-monitor
```

**成功的样子**：输入的那一行前面变成：

```
PS E:\github1\data-quality-monitor>
```

**没成功？** 报错 `无法找到路径` → 检查一下你的项目是不是真的在 E 盘这个位置（打开文件资源管理器看看）。

---

## 第 2 步 激活虚拟环境（不激活，下面的命令全都不能用）

**输入：**

```
.\.venv\Scripts\Activate.ps1
```

**成功的样子**：提示符前面多出 `(.venv)` 两个字：

```
(.venv) PS E:\github1\data-quality-monitor>
```

**报错 `禁止运行脚本`？** 分两步解决：

1. 输入：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` → 按回车 → 窗口问 `Y/N` → 输入 `Y` → 按回车
2. 再输入一次：`.\.venv\Scripts\Activate.ps1` → 按回车

**还是看不到 `(.venv)`？** 没关系，不要卡在这。后面每一步我都给了「不激活也能用的替代命令」，看到 `(.venv)` 就直接用短命令，看不到就用长命令。

---

## 第 3 步 跑 reporter 的测试

**输入：**

```
pytest tests\test_reporter.py
```

**成功的样子**：最后一行是：

```
10 passed in 0.xx s
```

（上面是一串点号 `...........`，点号越多代表通过的测试越多）

**看到 `1 failed` 或 `10 failed`？** → 去**第 8 步**查怎么处理。

**报错 `'pytest' 不是内部或外部命令`？** → 环境没激活，改用完整路径：

```
E:\github1\data-quality-monitor\.venv\Scripts\pytest.exe tests\test_reporter.py
```

---

## 第 4 步 跑全部测试（确认 reporter 没影响别的模块）

**输入：**

```
pytest
```

**成功的样子**：最后一行是：

```
44 passed in 0.xx s
```

> 44 = 30 个检查测试 + 4 个配置测试 + 10 个报告测试，一个不少。

---

## 第 5 步 跑代码规范检查

**输入：**

```
ruff check core tests
```

**成功的样子**：

```
All checks passed!
```

**报错 `'ruff' 不是...`？** 用完整路径：

```
E:\github1\data-quality-monitor\.venv\Scripts\ruff.exe check core tests
```

**看到 `E501` 之类报错？** → 去**第 8 步**。

---

## 第 6 步 手动验证报告真的能生成（真实命令，模拟你平时使用）

> 这一步不做也行（测试已经验证过了），但做了你能亲眼看到报告长什么样。演示文件会生成在当前目录，用完删掉（第 7 步）。

### 6.1 生成「正常数据」的 JSON 报告

**输入：**

```
dqm --table sample_orders --data data\sample_orders.csv --report json --output report_demo.json
```

**成功的样子**：屏幕先打印 3 行 `[PASS]`，最后一行是：

```
Report written to report_demo.json
```

**报错 `无法将"dqm"项识别为...`？** 用完整路径：

```
E:\github1\data-quality-monitor\.venv\Scripts\dqm.exe --table sample_orders --data data\sample_orders.csv --report json --output report_demo.json
```

### 6.2 打开 JSON 报告看内容

**输入：**

```
Get-Content report_demo.json -Encoding UTF8
```

**成功的样子**：看到里面有这几行（其他内容不用管）：

```
"table": "sample_orders",
"passed_checks": 3,
"failed_checks": 0,
```

### 6.3 生成「坏数据」的 Markdown 报告

**输入：**

```
dqm --table sample_orders --data data\sample_orders_bad.csv --report markdown --output report_demo.md
```

**成功的样子**：屏幕先打印 3 行 `[FAIL]`，最后一行 `Report written to report_demo.md`。

### 6.4 打开 Markdown 报告看内容

**输入：**

```
Get-Content report_demo.md -Encoding UTF8
```

**成功的样子**：看到表格里 3 行 `| FAIL |`：

```
| FAIL | order_id | not_null | null_count=1, ... |
| FAIL | order_id | unique | duplicate_count=1, ... |
| FAIL | amount | range | out_of_range_count=2, ... |
```

### 6.5 验证退出码（这是 CI 判断成败的依据）

**输入：**

```
$LASTEXITCODE
```

**成功的样子**：
- 刚跑完 6.1（正常数据）→ 显示 `0`
- 刚跑完 6.3（坏数据）→ 显示 `1`

> `0` = 数据合格（全 PASS）；`1` = 有违规（有 FAIL）。如果两个都对了，说明退出码协议没被破坏。

---

## 第 7 步 收尾：删掉演示文件（可选，但建议）

**输入：**

```
Remove-Item report_demo.json, report_demo.md
```

窗口会问 `是否确认` → 输入 `Y` → 回车。

> 不删也没事，只是项目目录会多两个演示文件。

---

## 第 8 步 出错了怎么办（对照表）

| 你看到 | 说明 | 怎么做 |
|--------|------|--------|
| `'pytest' 不是内部或外部命令` | 环境没激活 | 用完整路径命令（第 3 步括号里那个），或回去做第 2 步 |
| `无法将"dqm"项识别为` | 环境没激活 | 用完整路径 `E:\github1\data-quality-monitor\.venv\Scripts\dqm.exe ...` |
| `禁止运行脚本` | 系统不让激活 | 做第 2 步的 `Set-ExecutionPolicy` |
| 测试结果 `1 failed` 或更多 | 有测试没过 | 看失败信息里 `E  AssertionError` 那一行（指出哪句断言没满足），把整段红色文字复制给我 |
| `ModuleNotFoundError: No module named 'core'` | 不在项目目录跑 | 先做第 1 步 `cd E:\github1\data-quality-monitor` |
| ruff 报 `E501 Line too long` | 某行代码超过 100 字符 | 看它指的 `文件:行号`（如 `core/reporter.py:63`），打开那个文件对应行，把超长行拆短 |
| ruff 报 `DTZ005` | 时间戳没带时区 | 检查 `datetime.now()` 有没有 `.astimezone()` |
| 打开报告是乱码 | 查看方式不对 | 用 `Get-Content 文件名 -Encoding UTF8` 看 |
| `invalid choice: 'yaml'` | 报告格式写错了 | 只能写 `json` 或 `markdown` |

---

## 附录：这 10 个测试分别在守什么（了解即可，不用操作）

| 测试 | 一句话 |
|------|--------|
| `test_export_json_creates_file` | JSON 文件真的生成了 |
| `test_export_json_contains_summary` | JSON 里有汇总统计（总数/通过/失败） |
| `test_export_json_contains_all_results` | 每条结果都在，一条没丢 |
| `test_export_markdown_creates_file` | Markdown 文件真的生成了 |
| `test_export_markdown_contains_summary` | Markdown 里有标题和汇总 |
| `test_export_markdown_has_one_row_per_result` | 每个结果一行，表级规则显示为 table |
| `test_export_markdown_details_generic` | 指标详情自动渲染（新规则不用改报告） |
| `test_export_report_dispatches_json` | 说 json 就给 JSON |
| `test_export_report_dispatches_markdown` | 说 markdown 就给 Markdown |
| `test_export_report_unknown_format_raises` | 说别的格式就报错（fail fast） |
