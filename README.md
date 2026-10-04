# 鑫测试平台

> 接口测试 + Web UI 测试 | FastAPI · Vue3 · MySQL

面向软件测试人员的 Web 测试管理平台，目标闭环：

**项目 → 环境 → 用例 → 执行 → 报告 → 缺陷 → AI 辅助**

> 七环闭环已全部打通（含 AI 辅助），侧栏 11 个页面均有实际内容，见文末「开发状态」。

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue3 + Element Plus + Vite + Pinia |
| 后端 | FastAPI + SQLAlchemy 2.0 |
| 数据库 | MySQL 8（Docker） |
| 接口测试 | requests + jsonpath-ng |
| Web UI 测试 | Selenium WebDriver |
| AI 辅助 | DeepSeek API（📋 尚未接入） |
| 部署 | Docker Compose（目前只有数据库在用） |

---

## 架构

```
┌──────────────────────────────────────────────┐
│        前端 Vue3 + Element Plus               │
│              localhost:5173                  │
└───────────────────┬──────────────────────────┘
                    │  axios  /api/*  (vite proxy)
┌───────────────────▼──────────────────────────┐
│           后端 FastAPI  :8000                 │
│  ┌──────────┐   ┌──────────────────────────┐ │
│  │  api/    │──▶│  services/  ★ 执行引擎    │ │
│  │  路由层   │   │  断言 / 变量解析 / 请求构造 │ │
│  └──────────┘   │  Selenium 执行 / 报告生成  │ │
│                 └──────────────────────────┘ │
└───────────────────┬──────────────────────────┘
                    │  SQLAlchemy
┌───────────────────▼──────────────────────────┐
│        MySQL 8 (Docker, 127.0.0.1:3307)      │
└──────────────────────────────────────────────┘
```

**关于 `services/` 层**：执行引擎的断言逻辑、变量解析、请求构造、Selenium 步骤执行等，
复用自既有的桌面版实现，剥离了原桌面框架的线程外壳后改为无状态服务，供 FastAPI 直接调用。
整套引擎现在由 `backend/scripts/verify_all.py` 的 203 项验收覆盖。

---

## 快速开始

### 一键启动（推荐）

```bash
start.bat        # 依次拉起 Docker + MySQL + 后端 + 前端
stop.bat         # 全部停掉
```

首次运行会自动建 venv、装依赖、从 `.env.example` 复制配置，需要等一会儿。

> ⚠️ 依赖 Docker Desktop 已在运行 —— 脚本会先 `docker info` 探活，
> 没起会直接退出并提示，不会留下半启动状态。

### 手动启动

```bash
# 1. 数据库（映射到 3307，本机若已装 MySQL，3306 通常被占用）
docker compose up -d mysql

# 2. 后端
cd backend
cp .env.example .env                      # 首次
venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 3. 前端
cd frontend
npm run dev
```

> ⚠️ **后端不要加 `--reload`** —— 本机上它不可靠：改了代码不重载，
> 表现为新路由持续 404，但代码其实是好的。改完后端手动重启即可。

启动时会自动建表并创建默认账号。

- Web UI：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health
- 默认账号：`admin` / `admin123`

> 打开 Web UI 会先落到登录页。接口已做全站 JWT 校验，在 `/docs` 上调试要先点
> 右上角 **Authorize** 填入登录返回的 `access_token`，否则业务接口一律返回 401。
> 只有四类不校验：`/api/auth/login`、`/api/health`、`/api/demo/*`，以及报告 HTML
> 与报告里的截图 —— 后两者是浏览器直接导航打开的，带不了 `Authorization` 头。

> 🤖 AI 辅助（用例生成 / 失败分析）走 DeepSeek：把 `backend/.env` 里的
> `DEEPSEEK_API_KEY` 填上再重启后端。**没配也不影响其它功能** ——
> 点 AI 按钮会返回 400 并提示去配 key。AI 调用超时 60 秒、失败自动重试 1 次。

---

> 📦 **旧版桌面代码归档** —— 根目录下的 `app/`、`main.py`、`build.spec`、
> `接口自动化测试工具.spec`、`requirements.txt` 是**早期 PySide6 桌面版的源码归档**。
> Web 平台的执行引擎（断言、变量解析、Selenium 步骤执行）复用自该版本，
> **目前维护重心已完全转移至 `backend/` 与 `frontend/`；改引擎时两边都要看一眼。**

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 入口 + CORS + 建表
│   │   ├── config.py           # 配置（读 .env）
│   │   ├── database.py         # SQLAlchemy engine / session
│   │   ├── models/             # ORM 模型（11 张表）
│   │   ├── schemas/            # 请求 / 响应模型（Pydantic）
│   │   ├── api/                # 路由
│   │   ├── services/           # ★ 执行引擎（复用层）
│   │   └── static/demo/        # Web 测试的离线演示靶页
│   └── scripts/                # verify_all.py（一键验收）/ seed_demo.py（演示数据）
│                               # debug_new_ops.py（单独复跑新增操作用例）
├── frontend/                   # Vue3 前端
│   └── src/
│       ├── api/                # axios 封装
│       ├── components/         # 公共组件
│       │   ├── AppLayout.vue         # 侧栏 + 顶栏外壳
│       │   ├── ApiCaseForm.vue       # 接口用例表单区（请求/断言/提取）
│       │   ├── WebCaseForm.vue       # UI 用例表单区
│       │   ├── WebStepEditor.vue     # 步骤编排器（31 种操作）
│       │   ├── PagePagination.vue    # 统一分页条（6 个列表页共用）
│       │   └── ...                   # PageHeader / StatusTag / 各编辑抽屉与弹窗
│       ├── views/              # 页面
│       │   ├── LoginView.vue         # 登录页（在 AppLayout 之外，独立全屏）
│       │   ├── ApiCaseList.vue       # 接口测试列表
│       │   ├── WebCaseList.vue       # UI 测试列表
│       │   ├── CaseEditor.vue        # 用例全屏编辑页（两种类型共用）
│       │   └── ...                   # 项目/场景/计划/执行中心/报告/环境/缺陷
│       ├── router/
│       └── styles/             # 设计令牌（改配色只改这里）
├── app/                        # 已冻结的桌面版源码（引擎复用来源）
├── dev_logs/                   # 每日开发日志（取舍与踩坑都记在这）
├── time/CHANGELOG.md           # 版本功能清单
├── docker-compose.yml
└── docs/                       # 需求 / 技术 / 设计文档
```

---

## 数据模型

11 张表：`user` · `project` · `environment` · `test_case` · `scenario` ·
`scenario_step` · `test_plan` · `test_plan_case` · `execution` · `defect` · `ai_task`

用例的请求头、断言、步骤等子结构以 JSON 字段存储，避免多表 join。
唯一的例外是**用例与计划、用例与场景**这两处关联 —— 它们需要外键级联
（删掉用例时关联自动清理），所以用关联表而不是 JSON 数组。

---

## 开发状态

> 更新时间：2026-10-05（Day 12）。完整的功能清单见 [time/CHANGELOG.md](time/CHANGELOG.md)。

| 模块 | 状态 |
|---|---|
| 工程骨架 / 数据库 / 认证 | ✅ 完成（JWT 全站校验 + 登录页 + 路由守卫；报告与截图路由豁免，因为浏览器直接导航带不了 header） |
| 执行引擎（接口 + Web UI） | ✅ 完成 |
| 项目管理 / 环境变量 | ✅ 完成 |
| 用例管理（接口 / UI 两条独立线路） | ✅ 完成 |
| 场景串联 / 数据驱动 | ✅ 完成（仅接口用例） |
| 执行中心 / 测试报告 / 测试计划 | ✅ 完成 |
| 缺陷管理 | ✅ 完成（含失败记录一键转缺陷） |
| AI 辅助（用例生成 / 失败分析） | ✅ 完成（DeepSeek；AI 助手页 + 用例编辑页生成 + 执行详情分析失败，每次调用落 `ai_task`。需在 `backend/.env` 配 `DEEPSEEK_API_KEY`） |
| 设置 | ✅ 完成（修改密码 / 浏览器驱动检测 / 本机运行参数只读展示） |
| Web 登录态复用 | ✅ 完成（登录用例导出 cookie + localStorage；「需要登录态」的用例注入后再跑，每条用例仍各起各的浏览器） |
| 列表分页 | ✅ 完成（6 个列表接口返回 `{ items, total }`；项目 / 环境 / 数据集保持裸数组 —— 它们是下拉数据源） |
| Docker 部署（含前后端） | 📋 仅数据库跑了 compose |

### 验收

```bash
cd backend && venv/Scripts/python.exe scripts/verify_all.py   # 203 项，需后端已启动
```

前端改动后建议用浏览器过一遍 13 条业务路由（外加登录页），确认无 console 报错与失败请求。

