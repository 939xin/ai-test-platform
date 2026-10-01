# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 接口自动化测试工具 — Claude Code 工作指引
> 每次对话启动时 Claude 会自动加载此文件

---

## 当前工程结构（重要）

本仓库现在包含**两套代码**：

| 目录 | 说明 | 状态 |
|---|---|---|
| `backend/` + `frontend/` | **新** AI 辅助软件测试平台（FastAPI + Vue3 + MySQL） | 开发中（7 天 MVP） |
| `app/` + `main.py` 等 | **旧** PySide6 桌面版 | 冻结，作为引擎复用源 |

新工程的执行引擎（`backend/app/services/`）大量复用旧桌面版 `app/engine`、`app/utils`
的逻辑（断言、变量解析、请求构造、Selenium 步骤执行）。改引擎逻辑时两边都要看一眼。

### 新工程启动

```bash
# 1. 数据库（MySQL 8；映射到 3307 —— 本机 3306 已被占用）
docker compose up -d mysql

# 2. 后端
cd backend
cp .env.example .env            # 首次
venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# 3. 前端
cd frontend
npm run dev                     # http://localhost:5173，/api 已代理到 8000
```

默认账号 `admin` / `admin123`。后端接口文档在 http://localhost:8000/docs。

### 新工程架构

```
frontend (Vue3 + Element Plus, 5173)
    │  axios  /api/*  →  vite proxy
backend  (FastAPI, 8000)
    ├── api/        路由
    ├── models/     SQLAlchemy ORM（10 张表）
    └── services/   ★ 执行引擎，复用自旧桌面版
                    assertion_engine / variable_resolver / api_executor
    │  SQLAlchemy
MySQL 8 (Docker, 3307)
```

### 前端规范（用户明确要求，必须遵守）

**所有前端页面必须优先使用现有前端 Skill 和 `frontend/src/components/` 下的公共组件，禁止引入新的 UI 库。**

- 设计参考 skill：`C:\Users\23395\.claude\skills\frontend-design`
  （注意：**项目内没有 `.claude/skills/`**，skill 装在用户级目录）
- 组件库**只用 Element Plus**，不引入 Tailwind / shadcn / Ant Design 等
- 公共组件统一放 `frontend/src/components/`，`@` 别名指向 `frontend/src`
- 设计令牌在 `frontend/src/styles/variables.css`（深青蓝 `#16697A` + 语义信号色）。
  **改配色改这里**，不要在组件里散落写死色值
- 数据类内容（URL / 状态码 / JSON / 耗时）统一加 `.mono` 类走等宽字体

---

## 项目概述

**接口自动化测试工具** — Windows 桌面应用，提供接口测试（pytest + requests）和 Web UI 测试（Selenium）两大功能。

- 技术栈：PySide6 + pytest + Selenium + SQLite
- 目标用户：软件测试人员
- UI 风格：实用为主，蓝色主题

---

## 常用命令

```bash
# 启动虚拟环境（Windows Git Bash）
source venv/Scripts/activate

# 首次初始化环境（建 venv + 装依赖 + 建目录）
scripts/setup.bat

# 启动应用
python main.py

# 预填演示数据
python tests/seed_test_data.py

# 打包（输出 dist/接口自动化测试工具.exe）
scripts/build.bat
# 或直接：pyinstaller build.spec --clean --noconfirm
```

### 验证脚本（都是普通脚本，不是 pytest 用例）

```bash
python tests/test_comprehensive.py   # 全量自测：11 张表 + CRUD 边界，95 项
python tests/verify_engine.py        # 引擎层端到端，不依赖 GUI
python tests/verify_e2e.py           # 用户操作链路：建环境→选用例→执行→看响应
python tests/verify_api_truth.py     # 真实网络验证，需外网可访问 httpbin.org
python tests/test_localhost.py       # 需本机 localhost:5000 有服务在跑
```

> ⚠️ `tests/` 下的 `test_*.py` 名字像 pytest 用例，实际是**带 import 副作用的脚本**（顶层直接执行 DB 操作）。
> 必须用 `python tests/xxx.py` 单个运行；直接 `pytest tests/` 会重复执行副作用、结果不可信。
> 「跑单个验证」= 只运行对应的那一个脚本文件。

### 快速导入验证（改完代码先跑这个）

```bash
python -c "
import sys; sys.path.insert(0, '.')
from app.database.models import init_db; init_db()
from app.ui.main_window import MainWindow
from app.engine.api_runner import APIRunner
from app.engine.web_runner import WebRunner
print('All imports OK')
"
```

---

## 架构

三层单向依赖，**数据库是唯一事实来源**，UI 不直接碰引擎内部状态：

```
UI 层 (PySide6)          用户操作 → 写 DB
    │  Signal / Slot
引擎层 (QThread 子类)     从 DB 读用例 → 执行 → 写结果表 → 生成报告
    │  DBManager
数据层 (SQLite + WAL)     11 张表，外键约束
```

**一次执行的完整数据流**：

1. UI 把用例/环境写进 DB
2. `APIRunner` / `WebRunner` 按 `case_id` **实时从 DB 读取**配置并执行
3. 结果写 `test_results`（用例级）+ `test_result_details`（步骤/断言级）+ `screenshots`（Base64）
4. `ReportGenerator.generate_from_results(result_ids)` 从 DB 反查结果 → 输出 `reports/{api|web}_report_r{id}_{时间戳}.html`，文件名带 `result_id` 便于回溯
5. `ReportViewer` 展示历史结果，可调 `export_html_to_pdf()` 转 PDF

**页面注册机制**（`main.py` + `main_window.py`）：
`main.py` 实例化 5 个页面 → `window.register_page(key, widget)` 加入 `QStackedWidget`；首页 `home_page.navigate_to` 信号连到 `window.switch_page`。
新增页面要同时改三处：`main.py` 创建+注册、`main_window._create_nav_bar()` 的 `nav_items`、`switch_page` 的 key 约定。

### 关键约定

- **数据库**：不用 ORM。`DBManager.execute/fetch_all/fetch_one/insert/update/delete`，**每次调用新建连接**（WAL + `busy_timeout=5000`）。跨多步的原子操作用 `DBManager.get_raw_conn()` 自己管事务。
- `DBManager.insert` 会**过滤掉值为 `None` 的字段**，让表默认值生效（默认值多依赖 `datetime('now','localtime')`）。
- **异步执行**：耗时操作必须是 `QThread` 子类，通过 `Signal` 回传 UI。现有信号：
  - `APIRunner`：`log_signal(str)` / `case_finished(dict)` / `finished_signal(str)`
  - `WebRunner`：`log_signal(str)` / `finished_signal(str)`
  UI 只连信号，绝不直接调 `run()`。
- **样式**：`blue_theme.qss` 只追加不改已有规则。`main_window._load_stylesheet()` 会把 `url(icons/` 替换成绝对路径（Qt QSS 的 `url()` 相对工作目录而非 QSS 文件），新增图标放 `app/ui/styles/icons/`。
- **导出是快照**：`ScriptGenerator` 生成的是导出那一刻的用例副本（输出到 `scripts/api_export_*` / `scripts/web_export_*`），改 DB 不会同步已导出的脚本。

### 容易踩的坑

- `app/engine/api_runner.py` 是**进程内直接用 `requests` 逐条执行**，不是 pytest、不起子进程。只有 `script_generator.py` 生成出来的脚本才是 pytest 脚本。
- `api_runner._execute_one_case()` 里写死 `actual_timeout = min(timeout, 10)`，用例里配的 timeout 超过 10 秒不生效。
- 断言语义：`expected_value` 为空串的断言被**静默跳过**；用例**没有任何断言**时，HTTP ≥ 400 自动判 fail，其余判 pass。
- `report_generator.py` 的 docstring 说「基于 Jinja2 模板」，实际是**内联 HTML 字符串拼接**，`templates/` 目录为空、代码里没有 Jinja2 依赖。改报告样式直接改 `_build_html()`。
- 变量解析 `${变量名}` 由 `VariableResolver` 处理：运行时变量（步骤间提取）优先于全局变量，未匹配的占位符**原样保留**。

---

## 标准文件路径索引

> 开发时优先参考以下文件，不要凭记忆做决策。

| 文档 | 路径 | 用途 |
|------|------|------|
| 功能需求 | [docs/requirements/功能需求规格.md](docs/requirements/功能需求规格.md) | 完整功能需求清单 |
| 技术规范 | [docs/technical/技术规范.md](docs/technical/技术规范.md) | 技术选型、架构、数据库设计 |
| UI 设计规范 | [docs/design/UI设计规范.md](docs/design/UI设计规范.md) | 配色、组件、布局标准 |
| 开发流程 | [docs/process/开发流程.md](docs/process/开发流程.md) | 开发阶段、验证方式、启动命令 |
| 行为准则 | [AGENT.md](AGENT.md) | 命名/风格/禁止行为，与本文件互补 |
| 版本日志 | [time/CHANGELOG.md](time/CHANGELOG.md) | 各版本功能清单 |
| 开发日志 | [dev_logs/](dev_logs/) | 每日开发日志（按日期命名） |
| 实施计划 | [.claude/plans/](.claude/plans/) | Claude Code 计划文件 |

---

## 关键文件说明

### 入口和配置
- `main.py` — 应用入口，初始化 DB + 创建 MainWindow + 注册所有页面
- `requirements.txt` — Python 依赖清单
- `build.spec` — PyInstaller 配置（datas 里带了 QSS 和 Qt plugins，新增非 .py 资源要同步加进去）

### 数据层
- `app/database/models.py` — 11 张表结构 + `DBManager` 静态 CRUD + `init_db()`；库文件在 `data/test_tool.db`

### UI 层
- `app/ui/main_window.py` — 主窗口，顶部导航 + QStackedWidget 页面切换 + QSS 加载
- `app/ui/home_page.py` — 首页，双入口卡片，发 `navigate_to` 信号
- `app/ui/api_test_page.py` — 接口测试页，用例表格 + 工具栏 + 导出脚本/报告
- `app/ui/web_test_page.py` — Web 测试页，用例表格 + 浏览器选择 + 导出 Excel/JSON/脚本
- `app/ui/report_viewer.py` — 报告查看器，历史结果列表 + 统计 + PDF 导出
- `app/ui/settings_page.py` — 设置页（环境/变量/驱动三个 Tab）+ EnvEditDialog + VariableEditDialog
- `app/ui/components/api_case_dialog.py` — 接口用例编辑弹窗
- `app/ui/components/web_case_dialog.py` — Web 用例基本信息弹窗
- `app/ui/components/step_editor.py` — Web 步骤编排器弹窗（15 种操作 + 8 种定位）
- `app/ui/styles/blue_theme.qss` — 全局 Qt 样式表

### 引擎层
- `app/engine/api_runner.py` — 接口执行（QThread，进程内 requests 逐条执行+断言）
- `app/engine/web_runner.py` — Web 执行（QThread，Selenium 逐步执行，失败自动截图）
- `app/engine/script_generator.py` — 从 DB 读用例，生成独立 pytest 脚本到 `scripts/`
- `app/engine/report_generator.py` — 读 `test_results` 生成 HTML 报告到 `reports/`
- `app/engine/excel_exporter.py` / `json_exporter.py` — Web 用例导出

### 工具层
- `app/utils/browser_manager.py` — 驱动检测/创建（webdriver-manager 自动下载，支持自定义路径）
- `app/utils/variable_resolver.py` — 解析 `${变量名}` 占位符
- `app/utils/pdf_exporter.py` — Chrome CDP `Page.printToPDF` 转 PDF

---

## 代码风格（摘自 AGENT.md）

| 规则 | 示例 |
|------|------|
| 类名 | `PascalCase` — `MainWindow`, `DBManager` |
| 函数 | `snake_case` — `switch_page()`, `_load_stylesheet()` |
| 私有方法 | `_` 前缀 — `_create_nav_bar()` |
| UI 组件属性 | 类型后缀 — `self.btn_save`, `self.table`, `self.name_edit` |
| 信号命名 | snake_case — `navigate_to`, `log_signal` |
| 文件路径 | 用 `os.path` 拼接，不硬编码绝对路径 |
| 文案 | 界面中文、注释中文、变量名英文 |

---

## 工作原则

### 1. 开发前必读
- **先读规范再动手**：修改任何模块前，先查看对应的 `docs/` 文档
- **查看开发日志**：`dev_logs/` 最新日志了解当前进度和待办
- **查看版本清单**：`time/CHANGELOG.md` 确认版本范围

### 2. 开发策略
- **分步推进**：每次只完成一个明确的功能点，不要一口气改所有文件
- **优先复用**：有成熟的 Python 库/Skill 直接用，不要重复造轮子
- **先验证再继续**：每完成一个模块，运行验证确保无回归
- **严谨编码**：写代码前先看清楚已有代码结构，保持风格一致

### 3. 禁止行为
- ❌ 一口气改 10 个文件
- ❌ 不验证就认为代码没问题
- ❌ 引入不必要的重依赖
- ❌ 擅自改变 UI 配色或布局风格（以 `docs/design/UI设计规范.md` 为准）

### 4. 每日收尾
- 更新 `dev_logs/YYYY-MM-DD.md`，记录今日完成和待办
- 如有重要变更，更新 `time/CHANGELOG.md`

---

## 已知问题清单

> 按优先级排列，修一个划一个。

1. ⚠️ settings_page.py — Web 用例创建时未保存 environment_id
2. ⚠️ web_runner.py — 执行结果保存逻辑需完善（报告路径关联 result_id）
3. ⚠️ web_test_page.py — 启动 URL 未写入 web_test_cases.start_url
4. 📝 应用完整启动验证（模拟 GUI 初始化）
5. 📝 端到端测试：接口用例创建→执行→报告
6. 📝 端到端测试：Web 用例创建→步骤编排→执行
7. 📝 PyInstaller 打包测试
