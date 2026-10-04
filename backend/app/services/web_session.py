"""Web 登录态：从浏览器导出 / 注入。

登录用例跑完把 cookie 与 local/sessionStorage 存下来，「需要登录态」的用例起完
driver 后先注入再执行。**隔离模型没有变** —— 每条用例仍然各起各的浏览器、各关各的，
共享的只是状态数据本身。

⚠️ 库里的 cookie 等价于会话令牌，是明文。测试工具场景可接受，生产环境必须加密。
详见 CLAUDE.md 的能力边界一节。
"""
import json
import logging
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WebSession

logger = logging.getLogger(__name__)

# Selenium 的 add_cookie 对 sameSite 只认这三个值，且用的是 assert（直接抛异常，
# 不是返回错误）。Chrome 对「没显式声明」的 cookie 会给出 'unspecified'，
# 原样喂回去必炸 —— 所以下面要过滤。
_SAMESITE_ALLOWED = {"Strict", "Lax", "None"}

# 读两个 storage。用 JSON.stringify 而不是直接 return window.localStorage：
# 后者依赖驱动把 Storage 对象转成字典，各家实现不一致。
_READ_LOCAL_STORAGE = "return JSON.stringify(window.localStorage);"
_READ_SESSION_STORAGE = "return JSON.stringify(window.sessionStorage);"

# 写两个 storage。写成两条独立常量而不是一条带占位符的模板 ——
# JS 里的花括号会把 str.format / f-string 搅乱，可读性换不来那点复用。
_WRITE_LOCAL_STORAGE = """
var data = arguments[0];
for (var k in data) {
  if (Object.prototype.hasOwnProperty.call(data, k)) {
    window.localStorage.setItem(k, data[k]);
  }
}
"""
_WRITE_SESSION_STORAGE = """
var data = arguments[0];
for (var k in data) {
  if (Object.prototype.hasOwnProperty.call(data, k)) {
    window.sessionStorage.setItem(k, data[k]);
  }
}
"""


def origin_of(url: str) -> str:
    """取 URL 的 scheme://host:port。注入登录态前必须先访问这个地址。"""
    parts = urlsplit(url or "")
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _clean_cookie(cookie: dict) -> dict:
    """把 Chrome 导出的 cookie 收拾成 add_cookie 能接受的样子。

    两处必踩的坑：
      1. sameSite —— 只认 Strict / Lax / None，'unspecified' 会让断言崩掉；
      2. expiry   —— 必须是整数秒，浮点数会被拒。
    'domain' 不属于当前域的 cookie 注入时会被浏览器**静默丢弃**（不报错、也不生效），
    那是浏览器的规则，这里处理不了，只能靠 apply_state 返回的条数差体现出来。
    """
    cleaned = {
        "name": cookie.get("name", ""),
        "value": cookie.get("value", ""),
        "path": cookie.get("path") or "/",
        "secure": bool(cookie.get("secure", False)),
        "httpOnly": bool(cookie.get("httpOnly", False)),
    }
    if cookie.get("domain"):
        cleaned["domain"] = cookie["domain"]

    expiry = cookie.get("expiry")
    if expiry is not None:
        try:
            cleaned["expiry"] = int(expiry)
        except (TypeError, ValueError):
            logger.warning("cookie %s 的 expiry 不是数字：%r", cookie.get("name"), expiry)

    if cookie.get("sameSite") in _SAMESITE_ALLOWED:
        cleaned["sameSite"] = cookie["sameSite"]

    return cleaned


def _read_storage(driver, script: str) -> dict:
    """读一个 storage。读不到就返回空字典 —— 空白页上访问 storage 会抛
    SecurityError，那属于正常情况（还没跳到目标域），不该让整条用例翻车。"""
    try:
        raw = driver.execute_script(script)
    except Exception:
        logger.debug("读取 storage 失败（多为当前页没有同源 storage）", exc_info=True)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_storage(driver, script: str, data: dict) -> None:
    try:
        driver.execute_script(script, data)
    except Exception:
        logger.warning("写入 storage 失败", exc_info=True)


def _earliest_expiry(cookies: list[dict]) -> datetime | None:
    """取所有 cookie 里最早的那个到期时间。

    只能覆盖 cookie 那一半：localStorage 里的 token 何时失效，前端不暴露任何信号。
    """
    stamps = [c["expiry"] for c in cookies if isinstance(c.get("expiry"), int)]
    return datetime.fromtimestamp(min(stamps)) if stamps else None


def capture_state(driver) -> dict:
    """把当前浏览器的登录态整体导出成一个可 JSON 化的字典。"""
    try:
        cookies = [_clean_cookie(c) for c in driver.get_cookies()]
    except Exception:
        logger.warning("导出 cookie 失败", exc_info=True)
        cookies = []

    try:
        current_url = driver.current_url or ""
    except Exception:
        logger.warning("读取 current_url 失败", exc_info=True)
        current_url = ""

    return {
        "origin": origin_of(current_url),
        "cookies": cookies,
        "local_storage": _read_storage(driver, _READ_LOCAL_STORAGE),
        "session_storage": _read_storage(driver, _READ_SESSION_STORAGE),
        "expires_at": _earliest_expiry(cookies),
    }


def apply_state(driver, state: dict) -> dict:
    """把导出的登录态注入到刚起的 driver 里。

    ⚠️ 四步的顺序是有硬性原因的，不能调换：
        1. 先 driver.get(origin) —— 浏览器只允许在**目标域**上写 cookie 与 storage。
           在空白页或别的域上 add_cookie 会被静默丢弃：不抛异常、也不生效，
           是最难查的那类失败；
        2. 再 add_cookie；
        3. 再写 localStorage / sessionStorage；
        4. 之后才轮到用例自己的第一步（通常是 open_url）跳到实际页面。

    同源的前提下，第 4 步的导航不会把第 2、3 步写进去的东西弄丢 —— 这正是本方案
    能成立的原因。**但如果用例第一步跳去别的域，注入必然失效**，这是浏览器规则。
    """
    info = {
        "origin": "", "cookies_added": 0, "cookies_total": 0,
        "local_storage": 0, "session_storage": 0, "error": "",
    }

    origin = (state.get("origin") or "").strip()
    if not origin:
        info["error"] = "登录态里没有记录 origin，无法确定注入的目标域"
        return info
    info["origin"] = origin

    driver.get(origin)  # 跳板

    cookies = state.get("cookies") or []
    info["cookies_total"] = len(cookies)
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            info["cookies_added"] += 1
        except Exception as e:  # 单条失败不连累其余
            logger.warning("注入 cookie 失败：%s（%s）", cookie.get("name"), e)

    local = state.get("local_storage") or {}
    if local:
        _write_storage(driver, _WRITE_LOCAL_STORAGE, local)
        info["local_storage"] = len(local)

    session = state.get("session_storage") or {}
    if session:
        _write_storage(driver, _WRITE_SESSION_STORAGE, session)
        info["session_storage"] = len(session)

    return info


# ---------- 落库 ----------


def load_latest(db: Session, project_id: int) -> WebSession | None:
    """取本项目最近更新的那条登录态。

    「需要登录态」是个开关而不是一个下拉，所以只能取最新的一条 ——
    一个项目因此等价于「一套当前登录态」。
    """
    stmt = (
        select(WebSession)
        .where(WebSession.project_id == project_id)
        .order_by(WebSession.updated_at.desc(), WebSession.id.desc())
    )
    return db.scalars(stmt).first()


def save_state(db: Session, project_id: int, case_id: int | None, state: dict) -> WebSession:
    """写入登录态。

    **同一条登录用例重复执行时更新原来那条**，而不是每次插一条 ——
    否则跑二十次就攒二十份几乎一样的快照，还会把「最新一条」淹掉。
    """
    row = db.scalars(
        select(WebSession).where(
            WebSession.project_id == project_id,
            WebSession.source_case_id == case_id,
        )
    ).first()
    if row is None:
        row = WebSession(project_id=project_id, source_case_id=case_id)
        db.add(row)

    row.origin = state.get("origin") or ""
    row.cookies_json = state.get("cookies") or []
    row.local_storage_json = state.get("local_storage") or {}
    row.session_storage_json = state.get("session_storage") or {}
    row.expires_at = state.get("expires_at")
    db.commit()
    db.refresh(row)
    return row


def state_of(session: WebSession) -> dict:
    """库里的记录 → apply_state 认识的字典。"""
    return {
        "origin": session.origin,
        "cookies": session.cookies_json or [],
        "local_storage": session.local_storage_json or {},
        "session_storage": session.session_storage_json or {},
    }


def is_expired(session: WebSession | None) -> bool:
    """只看 cookie 的到期时间。

    这**不是**「登录态还能不能用」的判断 —— localStorage 里的 token 失效时间
    我们完全看不到。它只用来在界面上给个提醒，不参与任何执行决策。
    """
    if session is None or session.expires_at is None:
        return False
    return datetime.now() > session.expires_at


def summary(session: WebSession | None) -> dict | None:
    """给接口用的脱敏摘要。

    **只回 storage 的 key、不回 value** —— 那些 value 就是 token。
    和设置页的数据库密码同一个口径：页面要展示的信息，先想清楚该不该下发。
    """
    if session is None:
        return None
    return {
        "id": session.id,
        "origin": session.origin,
        "source_case_id": session.source_case_id,
        "cookie_count": len(session.cookies_json or []),
        "local_storage_keys": sorted((session.local_storage_json or {}).keys()),
        "session_storage_keys": sorted((session.session_storage_json or {}).keys()),
        "expires_at": session.expires_at,
        "expired": is_expired(session),
        "updated_at": session.updated_at,
    }


def clear_project(db: Session, project_id: int) -> int:
    """清掉本项目的全部登录态，返回删掉的条数。"""
    rows = db.scalars(select(WebSession).where(WebSession.project_id == project_id)).all()
    for row in rows:
        db.delete(row)
    db.commit()
    return len(rows)


# ---------- 执行链路的两个挂钩 ----------


def empty_session_info() -> dict:
    """执行结果里 session 那一段的初始形状。

    网页端只认一种形状，缺键就要到处写 if —— 所以连「压根没跑起来」的情况
    （比如 Web 用例一个步骤都没有）也给它同一副骨架。
    """
    return {
        "used": False, "captured": False, "missing": False, "expired": False,
        "origin": "", "cookies_added": 0, "cookies_total": 0,
        "local_storage": 0, "session_storage": 0, "error": "",
    }


def prepare_for_case(db: Session, case) -> tuple[dict | None, WebSession | None]:
    """执行**前**调用：该注入就把登录态取出来。

    返回 (要注入的状态, 命中的那行) —— 两个都返回是因为执行完还要拿那行判断过期。
    用例没勾「需要登录态」时直接返回空，走原路径，行为与改造前完全一致。
    """
    if not getattr(case, "needs_login", False):
        return None, None
    row = load_latest(db, case.project_id)
    return (state_of(row) if row is not None else None), row


def finish_case(db: Session, case, result: dict, row: WebSession | None) -> None:
    """执行**后**调用：导出登录态落库，并补上 missing / expired 两个标记。

    ⚠️ 必须先 pop 掉 `_captured_session` 再落库 —— 那里面是等价于会话令牌的东西，
    混进 execution.result_json 会永久留在执行历史里。

    单条执行与计划批量两条路径都走这里，免得两处各写一份、日后口径漂移。
    """
    captured = result.pop("_captured_session", None)
    if captured is not None:
        save_state(db, case.project_id, case.id, captured)

    info = result.setdefault("session", empty_session_info())
    info["missing"] = bool(getattr(case, "needs_login", False) and row is None)
    info["expired"] = bool(row is not None and is_expired(row))
