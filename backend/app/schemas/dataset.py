"""数据文件（参数化）相关的响应模型。"""
from datetime import datetime

from pydantic import BaseModel


class DatasetInfo(BaseModel):
    """一个数据文件的概况。"""

    filename: str
    size: int
    rows: int
    columns: list[str]
    uploaded_at: datetime


class DatasetPreview(BaseModel):
    """预览：表头 + 前若干行。"""

    filename: str
    rows: int
    columns: list[str]
    sample: list[dict]
