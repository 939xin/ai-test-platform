"""数据库连接 — SQLAlchemy 2.0 风格。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,   # 取连接前先探活，避免用到已被 MySQL 断掉的连接
    pool_recycle=3600,    # MySQL 默认 8h 断空闲连接，提前回收
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db():
    """FastAPI 依赖注入：每个请求一个 session，用完自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
