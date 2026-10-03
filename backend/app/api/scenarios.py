"""场景接口。

场景 = 一组按顺序执行的用例。每一步执行完会把提取到的变量传给下一步
（`services/scenario_runner.run_scenario`），用来串起「先登录拿 token → 再带着 token 请求」这类链路。

每一步都会落一条 execution 记录，执行中心和测试报告里都能看到。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.environments import get_environment_or_404
from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import Execution, Scenario, ScenarioStep, TestCase
from app.schemas.common import Page
from app.schemas.scenario import (
    RunScenarioRequest,
    ScenarioBrief,
    ScenarioCreate,
    ScenarioOut,
    ScenarioStepOut,
    ScenarioUpdate,
)
from app.services.scenario_runner import run_scenario

router = APIRouter()


def get_scenario_or_404(db: Session, scenario_id: int) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="场景不存在")
    return scenario


def _case_names(db: Session, case_ids: set[int]) -> dict[int, str]:
    if not case_ids:
        return {}
    return dict(
        db.execute(select(TestCase.id, TestCase.name).where(TestCase.id.in_(case_ids))).all()
    )


def _load_steps(db: Session, scenario_id: int) -> list[ScenarioStep]:
    return list(
        db.execute(
            select(ScenarioStep)
            .where(ScenarioStep.scenario_id == scenario_id)
            .order_by(ScenarioStep.step_order)
        ).scalars().all()
    )


def _to_out(db: Session, scenario: Scenario) -> ScenarioOut:
    steps = _load_steps(db, scenario.id)
    name_map = _case_names(db, {s.case_id for s in steps})
    return ScenarioOut(
        id=scenario.id,
        project_id=scenario.project_id,
        name=scenario.name,
        description=scenario.description,
        created_at=scenario.created_at,
        steps=[
            ScenarioStepOut(
                id=s.id,
                case_id=s.case_id,
                case_name=name_map.get(s.case_id),
                step_order=s.step_order,
                enabled=s.enabled,
                fail_strategy=s.fail_strategy,
            )
            for s in steps
        ],
    )


def _replace_steps(db: Session, scenario_id: int, steps: list) -> None:
    """整体替换步骤：step_order 直接按提交顺序重排，前端不用自己维护序号。"""
    for old in _load_steps(db, scenario_id):
        db.delete(old)
    db.flush()
    for index, item in enumerate(steps, start=1):
        db.add(ScenarioStep(
            scenario_id=scenario_id,
            case_id=item.case_id,
            step_order=index,
            enabled=item.enabled,
            fail_strategy=item.fail_strategy,
        ))


@router.get("/projects/{project_id}/scenarios", response_model=Page[ScenarioBrief],
            summary="场景列表（分页）")
def list_scenarios(project_id: int, page: PageParams = Depends(), db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    scenarios, total = paginate(
        db,
        select(Scenario).where(Scenario.project_id == project_id).order_by(Scenario.id.desc()),
        page,
    )

    counts = dict(
        db.execute(
            select(ScenarioStep.scenario_id, func.count(ScenarioStep.id))
            .where(ScenarioStep.scenario_id.in_([s.id for s in scenarios] or [0]))
            .group_by(ScenarioStep.scenario_id)
        ).all()
    ) if scenarios else {}

    return Page(items=[
        ScenarioBrief(
            id=s.id, project_id=s.project_id, name=s.name, description=s.description,
            step_count=counts.get(s.id, 0), created_at=s.created_at,
        )
        for s in scenarios
    ], total=total)


@router.post("/projects/{project_id}/scenarios", response_model=ScenarioOut,
             status_code=status.HTTP_201_CREATED, summary="新建场景")
def create_scenario(project_id: int, payload: ScenarioCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    scenario = Scenario(project_id=project_id, name=payload.name, description=payload.description)
    db.add(scenario)
    db.flush()
    _replace_steps(db, scenario.id, payload.steps)
    db.commit()
    db.refresh(scenario)
    return _to_out(db, scenario)


@router.get("/scenarios/{scenario_id}", response_model=ScenarioOut, summary="场景详情")
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    return _to_out(db, get_scenario_or_404(db, scenario_id))


@router.put("/scenarios/{scenario_id}", response_model=ScenarioOut, summary="更新场景")
def update_scenario(scenario_id: int, payload: ScenarioUpdate, db: Session = Depends(get_db)):
    scenario = get_scenario_or_404(db, scenario_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        scenario.name = data["name"]
    if "description" in data:
        scenario.description = data["description"]
    if "steps" in data:
        _replace_steps(db, scenario.id, payload.steps or [])

    db.commit()
    db.refresh(scenario)
    return _to_out(db, scenario)


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除场景")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    db.delete(get_scenario_or_404(db, scenario_id))
    db.commit()


@router.post("/scenarios/{scenario_id}/run", summary="执行场景")
def run_scenario_endpoint(
    scenario_id: int,
    payload: RunScenarioRequest | None = None,
    db: Session = Depends(get_db),
):
    scenario = get_scenario_or_404(db, scenario_id)
    payload = payload or RunScenarioRequest()

    steps = [s for s in _load_steps(db, scenario.id) if s.enabled]
    if not steps:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="场景里没有启用中的步骤")

    cases = {
        c.id: c
        for c in db.execute(
            select(TestCase).where(TestCase.id.in_([s.case_id for s in steps]))
        ).scalars().all()
    }
    missing = [s.case_id for s in steps if s.case_id not in cases]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"场景里有已删除的用例：{missing}")

    env_dict: dict = {}
    if payload.env_id is not None:
        env = get_environment_or_404(db, payload.env_id)
        env_dict = {
            "name": env.name,
            "base_url": env.base_url,
            "variables_json": env.variables_json or {},
        }

    runner_steps = [
        {
            "case_id": s.case_id,
            "case_name": cases[s.case_id].name,
            "fail_strategy": s.fail_strategy,
            "case": {
                "method": cases[s.case_id].method,
                "url": cases[s.case_id].url,
                "headers_json": cases[s.case_id].headers_json or {},
                "body_type": cases[s.case_id].body_type,
                "body_content": cases[s.case_id].body_content,
                "auth_type": cases[s.case_id].auth_type,
                "auth_value": cases[s.case_id].auth_value,
                "assertions_json": cases[s.case_id].assertions_json or [],
                "extract_json": cases[s.case_id].extract_json or [],
            },
        }
        for s in steps
    ]

    result = run_scenario(runner_steps, env_dict, timeout=payload.timeout)

    # 每一步落一条 execution，便于在「执行中心」和报告里回溯
    for step in result["steps"]:
        if step["status"] == "skip":
            continue
        detail = dict(step.get("result") or {})
        detail["scenario"] = {
            "id": scenario.id,
            "name": scenario.name,
            "step_order": step["step_order"],
        }
        db.add(Execution(
            project_id=scenario.project_id,
            case_id=step["case_id"],
            status=step["status"],
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_ms=step["duration_ms"],
            result_json=detail,
        ))
    db.commit()

    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "status": result["status"],
        "total_duration_ms": result["total_duration_ms"],
        "variables": result["variables"],
        "steps": [
            {
                "step_order": s["step_order"],
                "case_id": s["case_id"],
                "case_name": s["case_name"],
                "status": s["status"],
                "duration_ms": s["duration_ms"],
                "extracted": s.get("extracted", {}),
                "note": s.get("note", ""),
                "result": s.get("result"),
            }
            for s in result["steps"]
        ],
    }
