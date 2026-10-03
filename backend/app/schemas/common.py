"""跨模块共用的响应模型。

分页响应统一走 Page[T]。注意**不是所有列表接口都用它**：
项目 / 环境 / 数据集三个接口维持裸数组，因为它们同时是下拉数据源
（分别是 8 / 4 / 1 处选择器），分页会让选择器静默只显示头一页的选项 ——
这种缺陷比列表卡更隐蔽。详见 CLAUDE.md 的「列表分页」一节。
"""
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """一页数据 + 总数。

    total 是「满足筛选条件的全部条数」，与 limit / offset 无关 ——
    前端分页器靠它算总页数，不能拿 len(items) 顶替。
    """

    items: list[T]
    total: int
