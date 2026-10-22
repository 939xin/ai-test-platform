"""项目管理接口。"""
import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Execution, Project
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

logger = logging.getLogger(__name__)

router = APIRouter()


def get_project_or_404(db: Session, project_id: int) -> Project:
    """给本模块和其它模块共用（环境、用例都要按 project_id 挂靠）。"""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return project


@router.get("", response_model=list[ProjectOut], summary="项目列表")
def list_projects(db: Session = Depends(get_db)):
    return db.execute(select(Project).order_by(Project.id.desc())).scalars().all()


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED, summary="新建项目")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut, summary="项目详情")
def get_project(project_id: int, db: Session = Depends(get_db)):
    return get_project_or_404(db, project_id)


@router.put("/{project_id}", response_model=ProjectOut, summary="更新项目")
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = get_project_or_404(db, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def _cleanup_project_files(project_id: int, execution_ids: list[int]) -> None:
    """删项目后清理磁盘上的孤儿文件：报告 HTML、截图目录、数据集目录。

    **失败只记 warning，绝不能让删项目本身失败** —— 数据库已经删干净了，
    此时抛 500，用户会以为「没删掉」，再点一次拿到 404，更困惑。
    """
    report_dir = Path(settings.report_dir)

    for path in report_dir.glob(f"*_p{project_id}_*.html"):
        try:
            path.unlink()
        except OSError:
            logger.warning("删除项目 %s 的报告失败：%s", project_id, path, exc_info=True)

    # 截图目录名是 execution_{id}，项目删掉后 execution 行已级联消失，
    # 所以必须在删库之前把 id 取出来（见调用处）
    shots_root = report_dir / "screenshots"
    for execution_id in execution_ids:
        try:
            shutil.rmtree(shots_root / f"execution_{execution_id}", ignore_errors=True)
        except OSError:
            logger.warning("删除执行 %s 的截图目录失败", execution_id, exc_info=True)

    try:
        shutil.rmtree(Path(settings.dataset_dir) / str(project_id), ignore_errors=True)
    except OSError:
        logger.warning("删除项目 %s 的数据集目录失败", project_id, exc_info=True)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除项目")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    # 先取执行 id：项目一删，execution 行就被外键级联清掉，
    # 截图目录名 execution_{id} 再也无从推导，只能留成永久孤儿
    execution_ids = list(db.execute(
        select(Execution.id).where(Execution.project_id == project_id)
    ).scalars().all())

    db.delete(db.get(Project, project_id))
    db.commit()

    _cleanup_project_files(project_id, execution_ids)
