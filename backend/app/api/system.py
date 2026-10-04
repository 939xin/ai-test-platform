"""系统信息接口 —— 「设置」页那块只读面板的供数方。

只有一条 GET /system/info。改密码这种有写入语义的路由在 auth.py，不在这儿。
返回里的每一个字段都在设置页上看得见，所以**凡是敏感值都要先脱敏再出去**。
"""
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User
from app.services.browser_manager import check_browser

router = APIRouter()

SUPPORTED_BROWSERS = ("chrome", "edge")


def _database_summary() -> dict:
    """把 DATABASE_URL 拆开给前端看。

    ⚠️ **密码不回显**：这段 URL 会被渲染到页面上，等于把库密码贴在设置页
    （还会进浏览器历史、进截图、进验收日志）。所以这里只回用户名和地址，
    连 `***` 都不占位 —— 页面直接拼 `mysql://root@127.0.0.1:3307/test_platform`。
    """
    url = urlsplit(settings.database_url)
    scheme, _, driver = (url.scheme or "").partition("+")
    return {
        "scheme": scheme,                                  # mysql
        "driver": driver,                                  # pymysql
        "host": url.hostname or "",
        "port": url.port,
        "database": (url.path or "").lstrip("/"),
        "user": url.username or "",
    }


@router.get("/system/info", summary="系统信息（设置页只读面板）")
def system_info(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """一次把设置页要的全给出去：版本 / 数据库 / 目录 / 驱动 / AI 配置状态。

    合并成一个接口是有意的：这些都是「本机状态」，分开请求意味着几条信息
    之间可能不是同一时刻的（比如数据库刚断），页面上会出现自相矛盾的组合。

    版本号取 FastAPI 的 app.version，不在前端再写一份 —— 两边各写一份必然漂移。
    """
    try:
        db.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        # 连不上就如实说是 False。注意回滚：连接失败时 session 处于作废状态，
        # 不 rollback 的话后面 close() 还会再抛一次，把整个请求变成 500
        db.rollback()
        database_ok = False

    drivers = {}
    for name in SUPPORTED_BROWSERS:
        available, detail = check_browser(name)
        # detail 可用时是浏览器可执行文件路径，不可用时是原因 —— 两种情况都直接给前端看，
        # 用户排障时就靠这行字。「未检测到 chrome 浏览器，请先安装」比一个红点有用得多
        drivers[name] = {"available": available, "detail": detail}

    return {
        "version": request.app.version,
        # 当前登录用户由后端回，而不是让前端读 localStorage ——
        # localStorage 里的值可能是上一个账号留下的，改密码时显示错了人是会误导的
        "user": {"username": user.username, "role": user.role},
        # 只回布尔值，**不回 key 本身**：设置页只需要提示「配没配」，
        # 把 key 送进浏览器纯属自找麻烦
        "ai_configured": bool(settings.deepseek_api_key.strip()),
        "database_ok": database_ok,
        "database": _database_summary(),
        "paths": {
            "report_dir": settings.report_dir,
            "dataset_dir": settings.dataset_dir,
            "driver_cache_dir": settings.driver_cache_dir,
        },
        "drivers": drivers,
    }
