"""列表接口的分页参数与查询助手。

抽出来是为了让 6 个列表接口共享同一套默认值与校验规则 ——
否则每个路由各写一遍 Query(...)，改上限时总有一个漏掉。

约定用 limit / offset 而不是 page / page_size：executions 接口本来就带 limit 参数，
不引入第二套风格。前端算 offset = (页码 - 1) * limit。
"""
from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 200


class PageParams:
    """分页查询参数。越界（limit<1、limit>200、offset<0）一律 422。"""

    def __init__(
        self,
        limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="每页条数"),
        offset: int = Query(0, ge=0, description="偏移量，(页码 - 1) × limit"),
    ):
        self.limit = limit
        self.offset = offset


def paginate(db: Session, stmt, params: PageParams) -> tuple[list, int]:
    """按分页参数取一页，返回 (rows, total)。

    total 单独 count 一遍，不能拿 len(rows) 代替 —— 后者只是本页条数。
    传进来的 stmt 必须只带 where（不要先 order_by 也行，带了也没关系，
    排序在子查询里不影响 count）。
    """
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.limit(params.limit).offset(params.offset)).scalars().all()
    return list(rows), total
