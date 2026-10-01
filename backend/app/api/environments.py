"""环境管理接口。

列表与创建挂在项目下（`/api/projects/{id}/environments`），
更新与删除用环境自身的 id（`/api/environments/{id}`）。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import Environment
from app.schemas.environment import EnvironmentCreate, EnvironmentOut, EnvironmentUpdate

router = APIRouter()


def get_environment_or_404(db: Session, env_id: int) -> Environment:
    """给本模块和其它模块共用（用例、执行都要按 env_id 取环境）。"""
    env = db.get(Environment, env_id)
    if env is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="环境不存在")
    return env


@router.get(
    "/projects/{project_id}/environments",
    response_model=list[EnvironmentOut],
    summary="环境列表",
)
def list_environments(project_id: int, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    return (
        db.execute(
            select(Environment)
            .where(Environment.project_id == project_id)
            .order_by(Environment.id)
        )
        .scalars()
        .all()
    )


@router.post(
    "/projects/{project_id}/environments",
    response_model=EnvironmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建环境",
)
def create_environment(project_id: int, payload: EnvironmentCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    env = Environment(project_id=project_id, **payload.model_dump())
    db.add(env)
    db.commit()
    db.refresh(env)
    return env


@router.get("/environments/{env_id}", response_model=EnvironmentOut, summary="环境详情")
def get_environment(env_id: int, db: Session = Depends(get_db)):
    return get_environment_or_404(db, env_id)


@router.put("/environments/{env_id}", response_model=EnvironmentOut, summary="更新环境")
def update_environment(env_id: int, payload: EnvironmentUpdate, db: Session = Depends(get_db)):
    env = get_environment_or_404(db, env_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(env, field, value)
    db.commit()
    db.refresh(env)
    return env


@router.delete(
    "/environments/{env_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除环境",
)
def delete_environment(env_id: int, db: Session = Depends(get_db)):
    db.delete(get_environment_or_404(db, env_id))
    db.commit()
