# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 接口自动化测试工具 — Claude Code 工作指引
> 每次对话启动时 Claude 会自动加载此文件

---

## ⛔ 强制约束：磁盘路径

**所有开发文件、生成数据、缓存路径优先使用 E 盘（`E:\项目...`），禁止在 C 盘生成临时大文件。**

适用范围包括但不限于：Python 虚拟环境与 pip 缓存、Node 依赖与 npm 缓存、
数据库数据文件与 Docker 数据卷、构建产物、测试报告、截图、日志。

落地方式：

- 本项目所有路径一律落在 `E:\项目\接口测试工具\` 下
- 新增缓存类工具时显式指定缓存目录到 E 盘，例如：
  - `PIP_CACHE_DIR=E:\项目\接口测试工具\.cache\pip`
  - `npm config set cache "E:\项目\接口测试工具\.cache\npm" --location=project`
- ⚠️ Docker 数据卷默认落在 C 盘（Docker Desktop 的 WSL 虚拟磁盘）。
  如需彻底满足本约束，要在 Docker Desktop → Settings → Resources 里
  把 Disk image location 改到 E 盘。

---

## 当前工程结构（重要）

本仓库现在包含**两套代码**：

| 目录 | 说明 | 状态 |
|---|---|---|
| `backend/` + `frontend/` | **新** 鑫测试平台（FastAPI + Vue3 + MySQL） | 开发中（已完成 Day 1–12） |
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

> 接口已做全站 JWT 校验（Day 8）。在 `/docs` 上调试要先点右上角 **Authorize**
> 填 `access_token`，否则业务接口一律 401。

### 新工程架构

```
frontend (Vue3 + Element Plus, 5173)
    │  axios  /api/*  →  vite proxy
backend  (FastAPI, 8000)
    ├── api/        路由
    ├── models/     SQLAlchemy ORM（11 张表）
    ├── schemas/    Pydantic 请求 / 响应模型
    └── services/   ★ 执行引擎，复用自旧桌面版
                    assertion_engine / variable_resolver / api_executor
                    web_executor（31 种 Web 操作）/ scenario_runner / report_generator
    │  SQLAlchemy
MySQL 8 (Docker, 3307)
```

### 用例的两条独立线路（Day 6 起）

「接口测试」与「UI 测试」是**两条独立线路**：各有自己的菜单、列表页与全屏编辑页。

- 路由：`/cases/api`、`/cases/web`，编辑页共用 `views/CaseEditor.vue`，
  由路由 `meta.caseType` 决定渲染哪半部分（类型专属表单拆到
  `components/ApiCaseForm.vue` / `WebCaseForm.vue`）
- 编辑页**没有类型下拉** —— 从哪个菜单进来就是哪种类型；保存后回所属列表
- 项目 id 走 query 传递（`?project=29`），刷新不丢
- Web 步骤的**操作与字段规格定义在后端** `services/web_executor.py` 的 `ACTION_SPEC`，
  `/api/web/status` 下发，前端照着渲染。**新增操作只改后端规格即可，不要在前端硬编码字段判断**

### 全站鉴权（Day 8 起）

接口已统一校验 JWT，**守卫不挂在各个路由函数上**，而是集中在 `main.py` 的
`include_router(..., dependencies=guard)` —— 这样 11 个路由模块一行都不用改，
豁免清单也只在 `main.py` 一处看得见。

- 依赖实现：`api/deps.py` 的 `get_current_user`（验签 + 确认 `sub` 用户还在）
- **新增路由模块时，记得在 `main.py` 里一起挂上 `dependencies=guard`**，否则它默认是裸奔的
- 豁免只有四类，都是有理由的：`/api/auth/login`（还没登录）、`/api/health`
  （`start.bat` 与前端登录前探活）、`/api/demo/*`（Selenium 直接打开）、
  报告 HTML 与截图两条路由（拆在 `reports.public_router`）
- 报告的豁免是**被迫的、不是偏好**：`window.open` 与 `<img src>` 走浏览器导航，
  任何前端写法都带不上 `Authorization` 头。这两条路由各自有 `../` 越界防护兜底
- 前端登录态在 `api/session.js`（单独一层是为了避开 `auth ↔ request` 循环引用）；
  `request.js` 收到 401 会清登录态并整页跳登录页

### 列表分页（Day 9 起）

**接口返回形状是刻意不对称的，别「顺手统一一下」：**

| 接口 | 形状 | 理由 |
|---|---|---|
| 用例 / 执行 / 缺陷 / 计划 / 场景 / 报告 | `{ items, total }` | 会随使用增长 |
| 项目 / 环境 / 数据集 | **裸数组** | 同时是下拉数据源（8 / 4 / 1 处调用） |

后三个**不能**分页：分页会让选择器静默只显示头一页的选项，用户看不到任何报错，
只会发现「我的环境呢」。这种缺陷比列表卡更隐蔽。`verify_all.py` 里有断言钉住它们。

- 参数统一 `limit`（1–200，默认 20）+ `offset`（≥0），越界一律 **422**。
  **不用 `page` / `page_size`** —— `executions` 接口本来就带 `limit`，不引第二套风格。
  前端算 `offset = (页码 - 1) * limit`
- `total` 是**满足筛选条件的全部条数**，不是本页条数。后端由 `paginate()` 单独 count
  （不能拿 `len(rows)` 顶替），前端「共 N 条」必须读它
- 换项目 / 改筛选条件 → **回第 1 页**再查。否则会停在一个新条件下根本不存在的页上，
  用户看到空表会以为没数据
- 分页条统一用 `components/PagePagination.vue`，各列表页不要自己写 `el-pagination`
- **多选项的表格不要分页** —— 报告页那张「勾选执行记录」是跨记录勾选的，
  表头「全选」在分页下只选得到当前页。这类表改用一次性大 `limit` 取回
- ⚠️ 把某个列表接口当**下拉数据源**用时，记得显式传大 `limit`（后端上限 200），
  否则选择器只剩 20 条。计划 / 场景的用例选择器就是这么做的，
  取不全时界面上要**明说**，不能悄悄少几条

> 执行中心的统计卡走 `GET /executions/stats`（统计整个项目，与分页无关）。
> 该路由**必须声明在 `/executions/{execution_id}` 之前**，否则 `stats` 会被当成
> 执行 id 解析成整数，直接 422 —— FastAPI 按声明顺序匹配。

### AI 辅助（Day 10 起）

DeepSeek 接入，两个端点：`POST /api/ai/generate-cases`、`POST /api/ai/analyze-failure`。

- **超时 60 秒**（整批生成偶尔要几十秒），只对「暂时性故障」重试 1 次：
  超时 / 429 / 5xx。401 / 402 / 400 是配置问题，重试没有意义
- **前端 axios 默认 30 秒超时会先把调用掐断** —— `api/ai.js` 里显式放大到 180 秒。
  再动这两个接口的超时，两边要一起改
- 返回不是 JSON 时，**重新调一次模型**（提示词补「只输出 JSON」），
  不是把同一段文本再解析一遍。三层兜底：`json.loads` → 剥围栏 → 正则取最外层括号
- 提示词是后端常量（`services/ai_prompts.py`）。断言规则**必须把引擎真正实现的那几组
  列给模型**，否则它会编出引擎跑不通的断言，用户拿到手一跑就报错
- `ai_task` 表**没有 project_id / case_id**，上下文写进 `input` 的 JSON。每次调用含失败都落一条
- 执行记录**没有类型字段**，`case_type`（api / web）是接口按 `case_id` 回查填充的。
  前端靠它把「AI 分析失败」限制在接口执行上（Web 的 `result_json` 里是 steps，
  没有 request / response，喂给模型只能得到空话）

> ⚠️ 验收时想确认路由注册，**别查 `app.routes`** —— 这一版 FastAPI 把
> `include_router` 进来的路由包成了 `_IncludedRouter`，那里看不到。
> 查 `app.openapi()["paths"]`。

**已知技术债**：`views/AIAssistant.vue` 里内联了一份生成 / 分析弹窗，
与 `components/AiGenerateDialog.vue`、`AiAnalysisDialog.vue` 重复。
用户选择维持现状（不改已验收的页面），后续可重构合并。

### 设置页（Day 11 起）

三块：账号（改密码）/ 浏览器驱动检测 / 系统参数只读展示。两个端点：
`POST /api/auth/password`、`GET /api/system/info`。

> ⚠️ **往 `auth.router` 里加路由，必须自己声明 `Depends(get_current_user)`** ——
> 这个 router 在 `main.py` 里是**没挂 `guard`** 的（它对全站豁免，因为 `/login`
> 必须免登录）。往里加东西默认就是裸奔的。验收里有无 token → 401 的断言钉着这条。

- `GET /system/info` **刻意合并成一个接口**：版本 / 用户 / 数据库 / 目录 / 驱动 /
  AI 配置状态都是「本机当前状态」，拆开请求会出现互相矛盾的组合
- **回显前先脱敏**：数据库地址只回 scheme / host / port / 库名 / 用户，**不回密码**；
  AI 只回「配没配」的布尔值，**不回 key**。这些字段都会渲染到页面上
  （还进浏览器历史与截图），验收里有两条断言扫 `test123456` 与 `sk-`
- **版本号的唯一来源是 `main.py` 的 `app.version`**（当前 `2.0.0`），
  设置页读它，不在前端再写一份
- 驱动检测走 `check_browser()` 的**廉价探测**：只看浏览器装没装、驱动缓存目录能不能写，
  **不启动浏览器也不下载驱动**。代价是**拿不到版本号**，页面显示可执行文件路径。
  别为了显示版本号在这里启动浏览器 —— 这一页会立刻变得需要等几十秒
- `verify_all.py` 里验改密码**用临时用户 `verify_tmp_user`，跑完删掉**，
  绝不拿 admin 试：脚本中途挂掉会把人锁在门外（文档里到处写着 `admin123`）

### Web 登录态复用（Day 12 起）

「登录一次、后面每条用例都不用再登」—— 登录用例导出浏览器状态，「需要登录态」的
用例注入后执行。两个端点：`GET` / `DELETE /api/projects/{id}/web-session`。

> ⚠️ **隔离模型没有被改动**：每条用例照旧各起各的浏览器、各关各的 `${driver.quit()}`。
> 共享的只是**状态数据**，不是浏览器。别顺手"优化"成共用一个 driver。

- 用例上的两个标记：`login_case`（执行通过后导出状态）、`needs_login`（执行前注入）
- **注入顺序是硬性的，不能调换**：`driver.get(origin)` 当跳板 → `add_cookie` →
  JS 写两个 storage → 才轮到用例自己的第一步。浏览器只允许在**目标域**上写 cookie
  与 storage，在空白页或别的域上 `add_cookie` 会被**静默丢弃** —— 不抛异常、也不生效，
  是最难查的那类失败
- ⚠️ **两个 Selenium 的坑，实测复现过才写的清洗逻辑**（`_clean_cookie`）：
  `sameSite` 只认 `Strict/Lax/None`，Chrome 会给 `'unspecified'`，而 Selenium
  用的是 **assert** 而不是返回错误 → 直接 `AssertionError`；
  `expiry` 必须是**整数秒**，浮点会被拒（`invalid argument: invalid 'expiry'`）
- **只在登录用例整条通过时才导出** —— 跑挂的登录用例存下来的是半登录的残次品，
  留给别人用只会制造更难查的失败
- 降级口径：标了「需要登录态」但没有可用状态时**照常执行**，只在结果里标
  `session.missing` 并在界面提示。**不静默跳过、也不直接报错**
- 单条执行（`api/executions.py`）与计划批量（`api/plans.py`）**共用**
  `web_session.prepare_for_case()` / `finish_case()` —— 两条路径各写一份，
  早晚出现"一边记了 missing、另一边没记"
- 导出的原始状态走 `result["_captured_session"]` 返回，**落库前必须 pop 掉**：
  那里面是等价于会话令牌的东西，混进 `execution.result_json` 会永久留在执行历史里。
  接口摘要同理，**只回 storage 的 key、不回 value**
- 靶页是 `static/demo/login-state.html`（登录并写三个通道）与 `protected.html`
  （无登录表单，只看有没有带过来的状态）。**别改 `index.html`** —— Day 4 那 44 项
  断言依赖它现有的 DOM

**能力边界（不要过度承诺）**：
- **登录态是否过期，程序无法可靠判定。** cookie 的到期时间读得到（`expires_at`），
  但 localStorage 里的 JWT 何时失效前端不暴露任何信号，而且"被重定向到登录页"
  各家站点表现都不同。目前只做到「cookie 到期就在界面上提醒一句」，
  **不参与任何执行决策**
- 跨域注入天然无效：用例第一步若跳到别的域名，注入一定不生效 —— 这是浏览器的
  同源规则，不是 bug，界面上已写明
- ⚠️ **库里存的 cookie 等价于会话令牌，是明文。测试工具场景可接受，
  生产环境必须加密**（至少整表加密或改用 KMS 托管）

**改 test_case 表结构前先看这里**：`create_all` **只建表、不给已有表加列**。
往已有表加字段要把 DDL 登记到 `database._ADDED_COLUMNS`，由 `ensure_schema()`
在启动时幂等补齐。这仍是过渡手段，表结构再稳定些应整体换成 Alembic。

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

> 按优先级排列，修一个划一个。详细背景见 `dev_logs/` 与 `time/CHANGELOG.md`。

### 新平台（当前在做，Day 9 逐条核对过代码）

按投入产出比排，**完整版与核实方式见 `time/CHANGELOG.md` 的「待规划」**：

1. ✅ **列表分页** —— 已完成（Day 9）。6 个会长的接口改 `{ items, total }`，
   项目 / 环境 / 数据集保持裸数组。契约见上文「列表分页」一节
2. ✅ **设置页** —— 已完成（Day 11）。账号 / 驱动检测 / 系统参数，见上文「设置页」一节
3. 📝 **无 Setup / Teardown**（前置 + 后置步骤）—— 全后端无实现
4. 📝 **缺陷无附件 / 评论 / 指派** —— ⚠️ 表里没有这些字段，**要先改表**
5. 📝 **无用例导入 / 导出**（JSON / Excel）
6. 📝 **Web 用例不支持场景串联 / 数据驱动** —— 这两条链路只走接口执行器
7. 📝 **接口用例串行执行** —— 无并发
8. 📝 **前后端没一起 Docker 化** —— 只有数据库跑了 compose
9. 📝 **窄视口表格横向溢出** —— 操作列已 `fixed="right"` 保证可点，整体仍需横向滚动
10. 📝 **pytest 脚本导出未搬** —— 旧桌面版 `script_generator.py` 新平台 0 处引用
11. 📝 **定时执行** —— 独立工程，需常驻调度器
12. 📝 **登录态过期无法自动判定** —— Day 12 引入的能力边界，只能靠 cookie 到期时间
    提醒，**不假装能自动检测**。做法与理由见上文「Web 登录态复用」一节

### 已完成，别当待办

Web UI 执行已迁移（Day 4）、`_capture_screenshot()` 老 bug 已修（Day 4）、
测试计划已实现（Day 5）、场景混入 Web 用例已修（Day 6）、缺陷管理已实现（Day 7）、
**全站 JWT 校验 + 登录页**已实现（Day 8）、**列表分页 + 执行统计接口**已实现（Day 9）、
**AI 辅助（用例生成 / 失败分析）**已实现（Day 10，见上文「AI 辅助」一节）、
**设置页**已实现（Day 11，见上文「设置页」一节）、
**Web 登录态复用**已实现（Day 12，见上文「Web 登录态复用」一节）——
**侧栏 11 个页面至此全部有实际内容，占位页清零**。
Day 12 顺手修掉 `${base_url}` 变量注入：`open_url` 与 `ApiCaseForm` 的字段提示
都写着「支持 `${base_url}`」，但两边都只注入了 `variables_json`。
**接口侧同样存在这个问题，Day 12 未修**（用户划的范围是「不动接口测试」）。
Day 9 另外修掉三个静默缺陷：计划编辑器保存会丢用例、报告文件名同一秒互相覆盖、
列表页挂载时重复请求一次。

### 旧桌面版（已冻结）

GUI 相关的历史问题随 UI 弃用而失效，不再跟踪（含 settings_page 未存 environment_id、
web_test_page 的 start_url、PyInstaller 打包测试等）。
