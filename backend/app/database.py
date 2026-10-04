"""数据库连接 — SQLAlchemy 2.0 风格。"""
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

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


# ---------- 建表 + 增量补列 ----------

# create_all 只建**缺失的表**，对已有表新增的**列**完全视而不见。本项目的库是
# 带着数据长期存在的，模型里加了字段而库里没有，症状是运行时突然报 Unknown column，
# 而且报错点离原因很远。所以建表之后还得补一次列。
#
# 以后往已有表加字段，把 DDL 登记到这里即可；重复启动是幂等的（先查信息模式）。
# 只写「追加到表尾、带默认值」的形式 —— MySQL 8 对这种 ALTER 走 INSTANT 算法，
# 只改元数据，不重建表也不锁表。
#
# ⚠️ 这仍是过渡手段：表结构再稳定一些就该换 Alembic，届时本段整体删掉。
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "test_case": {
        "login_case": "TINYINT(1) NOT NULL DEFAULT 0",
        "needs_login": "TINYINT(1) NOT NULL DEFAULT 0",
    },
}


def _ensure_columns() -> None:
    """把 _ADDED_COLUMNS 里登记、但库里还没有的列补上。已存在的跳过。"""
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                # 表还没建出来 —— 不可能：create_all 在前。真出现就交给下一轮启动
                logger.warning("补列跳过：表 %s 不存在", table)
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name in existing:
                    continue
                conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {ddl}"))
                logger.info("补列：%s.%s", table, name)


def ensure_schema() -> None:
    """建表 + 补列。启动时调用，**必须幂等**。"""
    from app import models  # noqa: F401  必须导入，否则元数据里没有表

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
