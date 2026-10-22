"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import (
    ai, auth, cases, datasets, defects, environments, executions, health, perf, perf_target,
    plans, projects, reports, scenarios, system, web, web_sessions,
)
from app.api.deps import get_current_user
from app.config import settings
from app.services.execution_reaper import reap_stale_executions
from app.services.perf_run_manager import perf_run_manager


def init_database() -> None:
    """建表 + 补列 + 确保存在默认账号。

    建表走 database.ensure_schema()：create_all 只建缺失的表，**不会给已有表加列**，
    所以那里补了一层幂等的列检查。表结构再稳定些应整体换成 Alembic。
    """
    from app.api.auth import hash_password
    from app.database import SessionLocal, ensure_schema
    from app.models import User

    ensure_schema()

    db = SessionLocal()
    try:
        if db.execute(select(User).limit(1)).scalar_one_or_none() is None:
            db.add(User(username="admin", password_hash=hash_password("admin123"), role="admin"))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    # 进程重启后，上一进程遗留的 queued/running/stopping 永远等不到结果，
    # 启动时统一标成 failed（并把已落库的计数保留成 partial 指标）。
    perf_run_manager.reap_stale_runs()
    # 功能执行同理：上一个进程留下的 running 永远等不到终态，启动时按开始时间清扫
    reap_stale_executions()
    yield
    # 优雅关闭：停止所有活跃压测，最多等每个 worker 排空 3 秒
    perf_run_manager.shutdown()


# version 会被「设置」页的只读面板读出来展示（GET /system/info），
# 所以这里要与 time/CHANGELOG.md 的版本号保持一致，别让它俩漂移。
app = FastAPI(title="AI 辅助软件测试平台", version="2.1.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全站鉴权：业务路由统一挂这道依赖，11 个路由模块本身一行都不用改。
# 豁免的四类，都是有理由的，不是图省事：
#   /api/auth/login  —— 还没登录，此时必然没有 token
#   /api/health      —— start.bat 与前端 AppLayout 在登录前就要探活
#   /api/demo/*      —— 静态演示页，由 Selenium 浏览器直接打开（下面单独 mount）
#   /api/reports/{filename} 与 /api/reports/screenshots/{path} ——
#                      浏览器 window.open / <img src> 直接导航，带不了 Authorization 头，
#                      故拆到 reports.public_router
guard = [Depends(get_current_user)]

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"], dependencies=guard)
app.include_router(environments.router, prefix="/api", tags=["environments"], dependencies=guard)
app.include_router(cases.router, prefix="/api", tags=["cases"], dependencies=guard)
app.include_router(executions.router, prefix="/api", tags=["executions"], dependencies=guard)
app.include_router(reports.router, prefix="/api", tags=["reports"], dependencies=guard)
app.include_router(reports.public_router, prefix="/api", tags=["reports"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"], dependencies=guard)
app.include_router(plans.router, prefix="/api", tags=["plans"], dependencies=guard)
app.include_router(datasets.router, prefix="/api", tags=["datasets"], dependencies=guard)
app.include_router(defects.router, prefix="/api", tags=["defects"], dependencies=guard)
app.include_router(web.router, prefix="/api", tags=["web"], dependencies=guard)
app.include_router(web_sessions.router, prefix="/api", tags=["web-sessions"], dependencies=guard)
app.include_router(ai.router, prefix="/api", tags=["ai"], dependencies=guard)
app.include_router(system.router, prefix="/api", tags=["system"], dependencies=guard)
app.include_router(perf.router, prefix="/api", tags=["perf"], dependencies=guard)
# 压测验收靶子也挂 guard：它能让目标 sleep / 返回大响应，不登录不能用
app.include_router(perf_target.router, prefix="/api", tags=["perf-target"], dependencies=guard)

# Web UI 测试的离线演示页。挂在 /api 之下，前端 vite proxy 和验收脚本的 BASE
# 都不需要额外配置；StaticFiles 自带路径穿越防护，且演示页只读。
app.mount("/api/demo", StaticFiles(directory=settings.demo_dir, html=True), name="demo")
