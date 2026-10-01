"""项目管理接口。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除项目")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    db.delete(get_project_or_404(db, project_id))
    db.commit()
