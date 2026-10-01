"""健康检查 — 同时探活数据库。"""
from fastapi import APIRouter
from sqlalchemy import text

from app.database import engine

router = APIRouter()


@router.get("/health")
def health() -> dict:
    db_ok = True
    db_error = ""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_ok = False
        db_error = str(e)[:200]

    return {
        "status": "ok",
        "service": "ai-test-platform",
        "database": "connected" if db_ok else "disconnected",
        "database_error": db_error,
    }
