"""测试报告接口。

报告是「勾选若干执行记录 → 生成一份 HTML」的粒度，对应旧项目的
report_generator.generate_from_results(result_ids)。文件落在 settings.report_dir。
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.config import settings
from app.database import get_db
from app.models import Execution
from app.services.report_generator import build_report

router = APIRouter()


class ReportCreate(BaseModel):
    """生成报告的入参。execution_ids 就是报告要包含的执行记录。"""

    execution_ids: list[int] = Field(..., min_length=1, description="要纳入报告的执行记录 id")
    # 不传就按执行记录自动判断（前端列表接口拿不到用例类型，见 _infer_test_type）
    test_type: str | None = Field(None, pattern="^(api|web)$",
                                  description="不传则按执行记录自动判断")


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


def _infer_test_type(db: Session, execution_ids: list[int]) -> str:
    """按执行记录推断报告类型。

    判据是 result_json 里有没有 steps（Web 执行器写进去的步骤明细）。
    只有「全部都是 Web 记录」才算 Web 报告，混合勾选时按接口报告出，
    免得一份混着两种用例的报告被贴上 Web 标签。
    """
    rows = db.execute(
        select(Execution.result_json).where(Execution.id.in_(execution_ids))
    ).scalars().all()
    if rows and all((row or {}).get("steps") for row in rows):
        return "web"
    return "api"


@router.post("/projects/{project_id}/reports", summary="按执行记录生成测试报告")
def create_report(project_id: int, payload: ReportCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    # 前端勾选执行记录时拿不到用例类型（列表接口不返回 result_json），所以由后端推断
    test_type = payload.test_type or _infer_test_type(db, payload.execution_ids)
    try:
        return build_report(db, payload.execution_ids, test_type=test_type)
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


_SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg"}


def _safe_screenshot_path(asset_path: str) -> Path:
    """把截图相对路径解析到 report_dir/screenshots 之下，挡住 ../ 之类的越界访问。

    与 _safe_report_path 同一套思路，只把白名单从 .html 换成图片后缀。

    注意根目录是 report_dir/screenshots（而不是 report_dir）：URL 里的
    /reports/screenshots/ 那一段已经被路由吃掉，传进来的 asset_path 形如
    "execution_12/step_03_xxx.png"，正好对应截图落盘时的子目录结构。
    """
    root = (_report_dir() / "screenshots").resolve()
    if Path(asset_path).suffix.lower() not in _SCREENSHOT_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="仅支持查看截图文件（png / jpg / jpeg）")
    path = (root / asset_path).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的截图路径")
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="截图不存在")
    return path


@router.get("/reports/screenshots/{asset_path:path}", response_class=FileResponse,
            summary="查看 Web 用例的步骤截图")
def get_screenshot(asset_path: str):
    """截图存在 report_dir/screenshots/ 下，报告 HTML 里用相对路径引用，
    所以经接口打开报告时，浏览器正好会请求到这个路由。
    """
    return FileResponse(_safe_screenshot_path(asset_path))
