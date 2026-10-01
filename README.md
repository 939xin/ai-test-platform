# AI 辅助软件测试平台

> 接口测试 + Web UI 测试 + AI 辅助 | FastAPI · Vue3 · MySQL

面向软件测试人员的 Web 测试管理平台，覆盖完整测试闭环：

**项目 → 环境 → 用例 → 执行 → 报告 → 缺陷 → AI 辅助**

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue3 + Element Plus + Vite + Pinia |
| 后端 | FastAPI + SQLAlchemy 2.0 |
| 数据库 | MySQL 8（Docker） |
| 接口测试 | requests + jsonpath-ng |
| Web UI 测试 | Selenium WebDriver |
| AI 辅助 | DeepSeek API |
| 部署 | Docker Compose |

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
复用自一套已经过 95 项自动化验证的既有引擎实现，剥离了原桌面框架的线程外壳后
改为无状态服务，供 FastAPI 直接调用。

---

## 快速开始

### 1. 数据库

```bash
docker compose up -d mysql
```

> MySQL 映射到 **3307** 端口（本机若已装 MySQL，3306 通常被占用）。

### 2. 后端

```bash
cd backend
cp .env.example .env                      # 首次，按需修改
python -m venv venv
venv/Scripts/pip install -r requirements.txt
venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

启动时会自动建表并创建默认账号。

- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health
- 默认账号：`admin` / `admin123`

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173 —— 首页会显示后端与数据库的连通状态。

---

## 项目结构

```
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── main.py             # 入口 + CORS + 建表
│   │   ├── config.py           # 配置（读 .env）
│   │   ├── database.py         # SQLAlchemy engine / session
│   │   ├── models/             # ORM 模型（10 张表）
│   │   ├── api/                # 路由
│   │   └── services/           # ★ 执行引擎（复用层）
│   └── scripts/verify_engine.py
├── frontend/                   # Vue3 前端
│   └── src/
│       ├── api/                # axios 封装
│       ├── components/         # 公共组件（AppLayout / PageHeader / StatusTag ...）
│       ├── views/              # 页面
│       ├── router/
│       └── styles/             # 设计令牌
├── app/                        # 既有桌面版源码（引擎复用来源）
├── docker-compose.yml
└── docs/                       # 需求 / 技术 / 设计文档
```

---

## 数据模型

10 张表：`user` · `project` · `environment` · `test_case` · `scenario` ·
`scenario_step` · `test_plan` · `execution` · `defect` · `ai_task`

用例的请求头、断言、步骤等子结构以 JSON 字段存储，避免多表 join。

---

## 开发状态

| 模块 | 状态 |
|---|---|
| 工程骨架 / 数据库 / 认证 | ✅ 完成 |
| 执行引擎（接口） | ✅ 完成 |
| 项目管理 / 用例管理 | 🚧 进行中 |
| 执行中心 / 报告 / 缺陷 | 📋 计划中 |
| AI 辅助（用例生成 / 失败分析） | 📋 计划中 |
| Selenium 集成 / Docker 部署 | 📋 计划中 |
