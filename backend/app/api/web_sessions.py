"""Web 登录态接口：查看 / 清除。

登录态的**写入不在这里** —— 它是「登录用例」执行成功时的副产品，
由 api/executions.py 与 api/plans.py 落库。这两个接口只管「看一眼」和「清掉重来」。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import TestCase
from app.schemas.websession import WebSessionClearResult, WebSessionSummary
from app.services import web_session

router = APIRouter()


@router.get(
    "/projects/{project_id}/web-session",
    response_model=WebSessionSummary | None,
    summary="查看项目当前的 Web 登录态",
)
def get_web_session(project_id: int, db: Session = Depends(get_db)):
    """没有登录态时返回 **null**，而不是 404。

    「还没登录过」是这个资源的一种正常状态（新项目就是这样），不是错误。
    用 404 会逼着前端把「没配」和「接口挂了」写成同一段处理，反而更容易出错。
    """
    get_project_or_404(db, project_id)

    session = web_session.load_latest(db, project_id)
    if session is None:
        return None

    data = web_session.summary(session)
    if session.source_case_id is not None:
        data["source_case_name"] = db.execute(
            select(TestCase.name).where(TestCase.id == session.source_case_id)
        ).scalar_one_or_none()
    return data


@router.delete(
    "/projects/{project_id}/web-session",
    response_model=WebSessionClearResult,
    summary="清除项目当前的 Web 登录态",
)
def clear_web_session(project_id: int, db: Session = Depends(get_db)):
    """清掉本项目全部登录态。

    典型用途是「我怀疑这个登录态已经失效了」—— 清掉之后重跑一次登录用例即可。
    登录态是**旁路缓存**，清掉不会影响任何用例的定义或历史执行记录。
    """
    get_project_or_404(db, project_id)
    return WebSessionClearResult(deleted=web_session.clear_project(db, project_id))
