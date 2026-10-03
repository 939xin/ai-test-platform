"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import (
    auth, cases, datasets, defects, environments, executions, health, plans, projects, reports,
    scenarios, web,
)
from app.api.deps import get_current_user
from app.config import settings


def init_database() -> None:
    """建表 + 确保存在默认账号。Day 1 用 create_all，表结构稳定后换 Alembic。"""
    from app import models  # noqa: F401  必须导入，否则元数据里没有表
    from app.api.auth import hash_password
    from app.database import Base, SessionLocal, engine
    from app.models import User

    Base.metadata.create_all(bind=engine)

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
    yield


app = FastAPI(title="AI 辅助软件测试平台", version="0.1.0", lifespan=lifespan)

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

# Web UI 测试的离线演示页。挂在 /api 之下，前端 vite proxy 和验收脚本的 BASE
# 都不需要额外配置；StaticFiles 自带路径穿越防护，且演示页只读。
app.mount("/api/demo", StaticFiles(directory=settings.demo_dir, html=True), name="demo")
