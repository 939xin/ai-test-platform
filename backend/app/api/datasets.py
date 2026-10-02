"""数据文件接口：上传 / 列表 / 预览 / 删除。

文件落在 data/datasets/{项目id}/ 下，用例的 data_file 字段只存文件名。
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.config import settings
from app.database import get_db
from app.schemas.dataset import DatasetInfo, DatasetPreview
from app.services.dataset import dataset_dir, describe, load_rows, resolve_path

router = APIRouter()

PREVIEW_ROWS = 5


@router.post("/projects/{project_id}/datasets", response_model=DatasetInfo,
             status_code=status.HTTP_201_CREATED, summary="上传数据文件")
async def upload_dataset(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)

    raw_name = (file.filename or "").strip()
    if not raw_name or "/" in raw_name or "\\" in raw_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的文件名")
    try:
        path = resolve_path(project_id, raw_name)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空")
    if len(content) > settings.dataset_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件超过 {settings.dataset_max_bytes // 1024 // 1024}MB 上限",
        )

    dataset_dir(project_id).mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    # 落盘后立刻解析一次：格式不对、只有表头这类问题要当场报错，不能等到执行时才炸
    try:
        rows = load_rows(project_id, path.name)
    except ValueError as e:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not rows:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="文件里没有数据行（只有表头或内容为空）")

    info = describe(project_id, path.name)
    return DatasetInfo(**info, uploaded_at=datetime.fromtimestamp(path.stat().st_mtime))


@router.get("/projects/{project_id}/datasets", response_model=list[DatasetInfo],
            summary="数据文件列表")
def list_datasets(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    items = []
    for path in sorted(dataset_dir(project_id).glob("*")):
        if path.suffix.lower() not in {".csv", ".xlsx", ".xlsm"} or not path.is_file():
            continue
        try:
            info = describe(project_id, path.name)
        except (ValueError, FileNotFoundError):
            # 解析不了的文件也列出来，只是行数记 0，方便用户自己发现并删掉
            info = {"filename": path.name, "size": path.stat().st_size, "rows": 0, "columns": []}
        items.append(DatasetInfo(**info, uploaded_at=datetime.fromtimestamp(path.stat().st_mtime)))
    items.sort(key=lambda i: i.uploaded_at, reverse=True)
    return items


@router.get("/projects/{project_id}/datasets/{filename}/preview", response_model=DatasetPreview,
            summary="预览数据文件")
def preview_dataset(
    project_id: int,
    filename: str,
    limit: int = Query(PREVIEW_ROWS, ge=1, le=50),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    try:
        rows = load_rows(project_id, filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    columns: list[str] = []
    for r in rows:
        for key in r:
            if key not in columns:
                columns.append(key)
    return DatasetPreview(filename=Path(filename).name, rows=len(rows),
                          columns=columns, sample=rows[:limit])


@router.delete("/projects/{project_id}/datasets/{filename}",
               status_code=status.HTTP_204_NO_CONTENT, summary="删除数据文件")
def delete_dataset(project_id: int, filename: str, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    try:
        path = resolve_path(project_id, filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="数据文件不存在")
    path.unlink()
