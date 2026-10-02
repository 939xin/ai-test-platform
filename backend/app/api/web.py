"""Web UI 测试的辅助接口。

目前只有环境探测：前端在驱动不可用时给出提示，验收脚本先用它预检，
没有 Chrome/Edge 的机器上就跳过 Web 用例，而不是抛一堆连接错误。
"""
from fastapi import APIRouter

from app.config import settings
from app.services.browser_manager import check_browser
from app.services.web_executor import ACTION_LABELS, LOCATOR_ACTIONS, LOCATOR_LABELS, LOCATOR_MAP

router = APIRouter()

SUPPORTED_BROWSERS = ("chrome", "edge")


@router.get("/web/status", summary="Web 测试环境可用性")
def web_status():
    """探测浏览器是否可用，并下发步骤编排所需的枚举。

    浏览器检测刻意只做廉价检测（可执行文件在不在、驱动缓存目录能不能写），
    **不触发驱动下载** —— 否则首次调用会卡几十秒。

    actions / locators 顺带返回：操作与定位方式的定义在 services/web_executor.py，
    前端编辑器直接用它渲染下拉，不各自维护一份枚举（会漂移）。
    """
    browsers = {}
    problems = []
    for name in SUPPORTED_BROWSERS:
        available, detail = check_browser(name)
        browsers[name] = {"available": available, "detail": detail}
        if not available:
            problems.append(detail)

    return {
        "available": any(b["available"] for b in browsers.values()),
        "browsers": browsers,
        "cache_dir": settings.driver_cache_dir,
        "error": "；".join(problems),
        # needs_locator 让前端知道这个操作要不要显示「定位方式 / 定位值」两个输入框
        "actions": [
            {"value": value, "label": label, "needs_locator": value in LOCATOR_ACTIONS}
            for value, label in ACTION_LABELS.items()
        ],
        "locators": [
            {"value": value, "label": LOCATOR_LABELS.get(value, value)}
            for value in LOCATOR_MAP
        ],
    }
