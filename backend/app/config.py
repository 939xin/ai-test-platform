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

    # ---------- 数据驱动 ----------
    # data/datasets/{项目id}/ —— 参数化用的 CSV / Excel，按项目分目录避免同名互踩
    dataset_dir: str = str(BASE_DIR.parent / "data" / "datasets")
    dataset_max_bytes: int = 5 * 1024 * 1024  # 上传上限 5MB

    # ---------- Web UI 测试 ----------
    # drivers/ —— webdriver-manager 的驱动缓存目录。
    # 它的默认值是 C:\Users\<用户>\.wdm，而项目约束禁止在 C 盘产生大文件，
    # 所以必须显式重定向（见 services/browser_manager.py）。已在 .gitignore 中。
    driver_cache_dir: str = str(BASE_DIR.parent / "drivers")

    # reports/platform/screenshots/execution_{id}/ —— Web 用例的步骤截图。
    # 刻意放在 report_dir 之下，报告 HTML 里才能用相对路径引用
    # （经接口打开和双击本地文件打开两种方式都显示得出来）。
    screenshot_dir: str = str(BASE_DIR.parent / "reports" / "platform" / "screenshots")

    # app/static/demo/ —— 离线演示页，给验收脚本当靶页（httpbin 没有 UI，无法测 Web）
    demo_dir: str = str(BASE_DIR / "app" / "static" / "demo")

    # ---------- 响应体入库上限 ----------
    # JSON 与非 JSON 用同一个口径。调一个返回几十 MB JSON 的接口时，
    # 整份响应体会把 MySQL 的 JSON 列撑爆，报告与 AI 分析也会拖着它。
    response_body_max_chars: int = 200_000

    # ---------- Web UI 执行并发 ----------
    # 同时最多拉起几个浏览器实例。两个人同时点执行就是两个 Chrome，
    # 不设上限时机器资源完全不受控。超出的请求先排队等一小会儿，
    # 等不到就返回一条 error 结果（不无限挂起请求线程）。
    web_max_concurrent_sessions: int = 2
    web_browser_wait_seconds: int = 30

    # ---------- 执行记录清扫 ----------
    # 启动时把「开始至今超过这么久、还停在 running」的记录标成 error。
    # 功能执行没有心跳，只能按开始时间判断；阈值给得宽松是为避免误伤长用例。
    execution_stale_minutes: int = 60

    # ---------- 性能测试（接口压测） ----------
    # 这些是「防呆上限」，不是性能承诺：压测机、网络、被测系统都会影响结果。
    # 前端通过 GET /api/perf-limits 读取，避免前后端各写一份上限。
    perf_max_concurrency: int = 50
    perf_max_total_requests: int = 200_000
    perf_max_duration_seconds: int = 600
    perf_max_rps: int = 2000
    perf_max_warmup_seconds: int = 10
    perf_max_request_timeout: int = 120
    perf_hard_wall_seconds: int = 900
    perf_max_active_runs: int = 1
    perf_stale_seconds: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
