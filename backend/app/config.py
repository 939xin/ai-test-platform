"""应用配置 — 从 backend/.env 读取，真实密钥不进代码库。"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（config.py 的上上级），保证从任意工作目录启动都能找到 .env
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------- 数据库 ----------
    database_url: str = (
        "mysql+pymysql://root:test123456@127.0.0.1:3307/test_platform?charset=utf8mb4"
    )

    # ---------- JWT ----------
    jwt_secret: str = "dev-secret-please-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # ---------- AI ----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:5173"

    # ---------- 测试报告 ----------
    # reports/platform/ —— 刻意与旧桌面版输出隔开：reports/ 根目录下还留着
    # 旧 PySide6 工具生成的几十份报告，混在一起列表页会很乱。已在 .gitignore 中。
    report_dir: str = str(BASE_DIR.parent / "reports" / "platform")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
