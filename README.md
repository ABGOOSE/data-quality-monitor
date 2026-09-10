# data-quality-monitor

A lightweight data quality monitoring tool with rule engine, statistical anomaly detection, and alerting.

\## Status

Project initialized, first commit coming soon.

## 2026/09/08 
## test from codex
This line is added in VS Code to test git integration.

## 2026/09/09  项目目录结构喝职责总览
data-quality-monitor/          ← 项目根目录，所有东西的家
├── config/                    ← 配置文件（rules.yaml），改配置不用改代码
│   └── __init__.py            ← 门牌：让Python认识config是个包
├── core/                      ← 核心业务逻辑（checker.py, anomaly.py...）
│   └── __init__.py            ← 门牌：让Python认识core是个包
│   └── config_loader.py       ← 逻辑：负责读取 rules.yaml，返回一个规则字典。
│   └── checker.py             ← 逻辑：负责对 DataFrame 执行规则检查
├── data/                      ← 示例数据、临时数据文件
│   └── .gitkeep               ← 占位：让git跟踪这个空目录
├── tests/                     ← 测试（test_checker.py...）
│   └── __init__.py            ← 门牌：让Python认识tests是个包
├── notes/                     ← 学习笔记、调研记录（你的个人成长档案）
│   └── daily/                 ← 每日学习日志，按日期命名
├── .gitignore                 ← 告诉git哪些文件不要跟踪（.venv/, __pycache__/...）
├── LICENSE                    ← 开源协议（MIT）
├── README.md                  ← 项目门面：介绍项目是干嘛的、怎么用
└── pyproject.toml             ← Python项目配置：依赖、工具设置
