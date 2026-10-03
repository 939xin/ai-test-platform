"""通用依赖 —— 目前只有全站 JWT 校验。

这个依赖不挂在各个路由函数上，而是由 main.py 在 include_router 时统一挂到
业务路由上（`dependencies=[Depends(get_current_user)]`），这样 11 个路由模块
一行都不用改，豁免清单也集中在 main.py 一处看得见。
"""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# auto_error=False：缺 Authorization 头时不让 HTTPBearer 自己抛 403，
# 改由下面统一抛 401 —— 语义上「没登录」就该是 401，且要带 WWW-Authenticate 头。
# 用 HTTPBearer 而不是手解析 header，是为了让 /docs 上出现 Authorize 按钮。
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "登录状态已失效，请重新登录") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """校验 Bearer token，返回当前用户。

    四种情况都归 401，前端拿到 401 统一清 token 跳登录页：
    没带 token / 伪造或过期 / 解不出 sub / 用户已被删除。
    """
    if credentials is None:
        raise _unauthorized("未登录或缺少访问令牌")

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        raise _unauthorized() from None

    username = payload.get("sub")
    if not username:
        raise _unauthorized()

    # 光验签不够：用户被删掉后旧 token 在过期前仍然验得过，这里再确认一次。
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise _unauthorized()

    return user
