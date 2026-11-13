# pytest-html 引入操作手册（傻瓜式全流程 + 验证）

> 适用项目：`data-quality-monitor`
> 环境：Windows + PowerShell，虚拟环境在 `.venv\`
> 目标：从零引入 pytest-html，让测试结果生成一个**浏览器可看、红绿分明、可点击**的 HTML 报告文件。

---

## 一、先搞懂三原则

### 是什么（What）

`pytest-html` 是一个 **pytest 插件**（不是独立软件），装好后给 pytest 增加 `--html` 参数，跑测试时自动生成一个 HTML 报告文件。

### 为什么用（Why）

- 终端报告一闪而过、滚屏后找不到，也不方便点进去改代码
- HTML 报告用浏览器打开：红绿分明、可筛选排序、失败可展开看堆栈、可保存发人
- 它是**开发工具**，不是业务运行依赖，所以放进 `dev` 组，不进核心 dependencies

### 用在哪（Where）

- 本地写完代码，想直观看到全部用例通过情况
- 把报告发给同事、或归档留痕
- 配合 CI 作为构建产物（artifact）下载

---

## 二、前置检查（逐条确认）

```powershell
Set-Location E:\github1\data-quality-monitor
```

### 检查 1：虚拟环境存在

```powershell
Test-Path .\.venv\Scripts\python.exe
```

**预期**：`True`。

### 检查 2：pytest 可用

```powershell
.\.venv\Scripts\pytest.exe --version
```

**预期**：打印 `pytest 9.1.1`。

---

## 三、引入全流程（6 步，照做即可）

### 步骤 1：安装 pytest-html

```powershell
.\.venv\Scripts\python.exe -m pip install pytest-html
```

**预期**：末尾出现 `Successfully installed ... pytest-html-4.2.0 ...`，同时自动装上它的依赖（pytest-metadata、jinja2、MarkupSafe）。

> 用 `python -m pip` 而不是直接 `pip`，能保证装进当前 `.venv`，不会误装到别的环境。

### 步骤 2：确认安装成功

```powershell
.\.venv\Scripts\python.exe -m pip show pytest-html
```

**预期**：看到 `Name: pytest-html`、`Version: 4.2.0`、`Requires: jinja2, pytest, pytest-metadata`。

### 步骤 3：确认 pytest 已识别插件

```powershell
.\.venv\Scripts\pytest.exe --trace-config | Select-String "plugins:"
```

**预期**：输出一行包含 `plugins: cov-7.1.0, html-4.2.0, metadata-3.1.1`。看到 `html-4.2.0` 就说明插件已注册成功。

### 步骤 4：同步写入 pyproject.toml（关键，别只装不登记）

用编辑器打开 `pyproject.toml`，在 `[project.optional-dependencies]` 的 `dev` 列表里加一行：

```toml
dev = [
    "pytest>=7.0",
    "pytest-cov>=5.0",
    "pytest-html>=4.0",
    "ruff>=0.4",
]
```

> 为什么必须登记：别人（或 CI、未来的你）克隆仓库后，靠 `pip install -e ".[dev]"` 一键装齐开发工具。只在本机 pip install 而不写进配置，换环境就会缺这个插件。

### 步骤 5：生成 HTML 报告

```powershell
.\.venv\Scripts\pytest.exe --html=report.html --self-contained-html
```

**预期**：末尾出现 `- Generated html report: file:///E:/.../report.html` 和 `132 passed`。

两个参数：

| 参数 | 作用 |
|------|------|
| `--html=report.html` | 报告输出路径 |
| `--self-contained-html` | 把 CSS/JS 全部内联进单个 HTML，拷贝/发人时不丢样式 |

### 步骤 6：浏览器打开查看

```powershell
Start-Process report.html
```

**预期**：默认浏览器打开报告，顶部是环境信息和汇总，下面是用例表格，每个测试一行、按结果标颜色。

### 步骤 7：把报告加进 .gitignore（不提交）

报告每次跑都变，不该进仓库。打开 `.gitignore`，确认含这一行：

```
report.html
```

---

## 四、验证步骤（逐条核对，全部通过才算成功）

### 验证 1：插件已安装且版本正确

```powershell
.\.venv\Scripts\python.exe -m pip show pytest-html | Select-String "Version"
```

**预期**：`Version: 4.2.0`。

### 验证 2：pytest 已加载该插件

```powershell
.\.venv\Scripts\pytest.exe --trace-config | Select-String "html-4.2.0"
```

**预期**：能匹配到 `pytest-html-4.2.0` 相关行。

### 验证 3：报告文件确实生成且非空

```powershell
Get-ChildItem report.html | Select-Object Name, Length
```

**预期**：文件存在，`Length` 约 19 万字节（非空）。

### 验证 4：报告内容包含全部用例

```powershell
Select-String -Path report.html -Pattern "test_validator_logs_success"
```

**预期**：能匹配到测试名，说明用例写进了报告。

### 验证 5：Git 不跟踪报告文件

```powershell
git check-ignore report.html
"退出码: $LASTEXITCODE"
```

**预期**：打印 `report.html`，退出码 `0`（0 表示被忽略）。

### 验证 6：代码风格与全量测试不受影响

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\pytest.exe
```

**预期**：`All checks passed!` + `132 passed`。

---

## 五、命令速查表

| 目的 | 命令 |
|------|------|
| 安装插件 | `python -m pip install pytest-html` |
| 查看版本 | `python -m pip show pytest-html` |
| 确认插件加载 | `pytest --trace-config \| Select-String "plugins:"` |
| 生成 HTML 报告 | `pytest --html=report.html --self-contained-html` |
| 浏览器打开 | `Start-Process report.html` |
| 确认被 git 忽略 | `git check-ignore report.html` |

---

## 六、踩坑与注意

1. **装了但 pytest 不认**：检查是不是装进了别的环境，务必用 `.venv` 里的 `python -m pip`，并用 `--trace-config` 确认。
2. **只 pip install 没改 pyproject**：换机器/CI 就缺插件，必须同步登记到 dev 组。
3. **没加 `--self-contained-html`**：会额外生成一个 assets 目录，单文件移动后样式丢失；要发人就加这个参数。
4. **把 report.html 提交了**：每次跑都变，会产生版本噪音，务必加 `.gitignore`。
5. **报告里看到红叉**：点该用例展开看断言和堆栈，点蓝色链接跳到代码行，和终端排障是同一套信息。

---

## 七、一句话总结

> 引入 pytest-html 就是「**pip 安装 → 确认插件加载 → 写进 pyproject 的 dev 组 → 用 `--html --self-contained-html` 生成 → 浏览器查看 → gitignore 忽略**」六步；它把终端里的测试结果变成可点击、可保存、可分享的网页报告，且作为开发工具不污染业务依赖。
