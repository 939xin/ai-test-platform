"""登录鉴权 — Day 1 最小实现（bcrypt 校验 + JWT 签发）。

不用 passlib：它读取 bcrypt.__about__ 在新版 bcrypt 上会抛异常。
"""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import User

router = APIRouter()

# 新密码长度下限。定 6 是因为默认账号就是 6 位（admin123），
# 再严就会让「改密码」这件事本身先把默认账号卡住。
MIN_PASSWORD_LENGTH = 6


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(min_length=1, description="原密码，用于确认是本人操作")
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128,
                              description="新密码")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return LoginResponse(access_token=create_token(user.username), username=user.username)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="修改当前用户密码")
def change_password(
    req: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """改当前登录用户的密码。

    ⚠️ 这个 router 在 main.py 里是**没挂 guard** 的 —— 它对全站豁免，
    因为 /login 必须免登录才能调。所以这条路由得自己声明 get_current_user，
    否则就是裸奔的：任何人都能拿别人用户名去改密码。
    （验收脚本里有一条断言专门钉这个。）

    要旧密码是为了挡住「token 被人捡走就能直接改密码」这一种。
    """
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码不正确")
    if req.old_password == req.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码不能与原密码相同")

    user.password_hash = hash_password(req.new_password)
    db.commit()
    # 刻意不吊销已签发的 token：改密码把正在干活的人踢下线，体验上更糟。
    # 旧 token 到期自然失效（默认 1440 分钟）。
