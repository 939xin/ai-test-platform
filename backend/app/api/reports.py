"""测试报告接口。

报告是「勾选若干执行记录 → 生成一份 HTML」的粒度，对应旧项目的
report_generator.generate_from_results(result_ids)。文件落在 settings.report_dir。
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.config import settings
from app.database import get_db
from app.services.report_generator import build_report

router = APIRouter()


class ReportCreate(BaseModel):
    """生成报告的入参。execution_ids 就是报告要包含的执行记录。"""

    execution_ids: list[int] = Field(..., min_length=1, description="要纳入报告的执行记录 id")
    test_type: str = Field("api", pattern="^(api|web)$")


def _report_dir() -> Path:
    path = Path(settings.report_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_report_path(filename: str) -> Path:
    """把文件名解析成报告目录下的路径，挡住 ../ 之类的越界访问。"""
    if Path(filename).name != filename or not filename.endswith(".html"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的报告文件名")
    path = (_report_dir() / filename).resolve()
    if path.parent != _report_dir().resolve():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的报告文件名")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    return path


@router.post("/projects/{project_id}/reports", summary="按执行记录生成测试报告")
def create_report(project_id: int, payload: ReportCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    try:
        return build_report(db, payload.execution_ids, test_type=payload.test_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/reports", summary="已生成的报告列表")
def list_reports():
    files = []
    for path in _report_dir().glob("*.html"):
        stat = path.stat()
        files.append({
            "filename": path.name,
            "size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    # 新的排前面
    files.sort(key=lambda f: f["created_at"], reverse=True)
    return files


@router.get("/reports/{filename}", response_class=HTMLResponse, summary="查看报告内容")
def get_report(filename: str):
    return _safe_report_path(filename).read_text(encoding="utf-8")
