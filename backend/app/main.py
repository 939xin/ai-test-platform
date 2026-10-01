"""FastAPI 入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import auth, health, projects
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

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
