"""测试计划接口。

测试计划 = 一组互不依赖的用例 + 一个默认环境，一键批量执行。

和「场景」的区别：场景按顺序串联，上一步提取的变量传给下一步（走 scenario_runner）；
计划里的用例各跑各的，谁先谁后不影响结果，跑完统计通过情况。

每条用例落一条 execution 记录（带 plan_id），执行中心和测试报告里都能看到。
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.environments import get_environment_or_404
from app.api.executions import case_to_dict, env_to_dict, execution_out
from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.config import settings
from app.database import get_db
from app.models import Environment, Execution, TestCase, TestPlan, TestPlanCase
from app.schemas.common import Page
from app.schemas.execution import ExecutionOut
from app.schemas.plan import (
    PlanBrief,
    PlanCaseOut,
    PlanCreate,
    PlanOut,
    PlanRunResult,
    PlanUpdate,
    RunPlanRequest,
)
from app.services import web_executor
from app.services.api_executor import execute_case

router = APIRouter()


def get_plan_or_404(db: Session, plan_id: int) -> TestPlan:
    plan = db.get(TestPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试计划不存在")
    return plan


def _load_cases(db: Session, plan_id: int) -> list[TestPlanCase]:
    return list(
        db.execute(
            select(TestPlanCase)
            .where(TestPlanCase.plan_id == plan_id)
            .order_by(TestPlanCase.step_order)
        ).scalars().all()
    )


def _case_meta(db: Session, case_ids: set[int]) -> dict[int, TestCase]:
    """一次查出 id → 用例对象，避免逐行回查。"""
    if not case_ids:
        return {}
    rows = db.execute(select(TestCase).where(TestCase.id.in_(case_ids))).scalars().all()
    return {c.id: c for c in rows}


def _env_names(db: Session, env_ids: set[int]) -> dict[int, str]:
    if not env_ids:
        return {}
    return dict(
        db.execute(select(Environment.id, Environment.name).where(Environment.id.in_(env_ids))).all()
    )


def _to_out(db: Session, plan: TestPlan) -> PlanOut:
    links = _load_cases(db, plan.id)
    meta = _case_meta(db, {l.case_id for l in links})
    env_names = _env_names(db, {plan.env_id} if plan.env_id else set())
    return PlanOut(
        id=plan.id,
        project_id=plan.project_id,
        name=plan.name,
        description=plan.description,
        env_id=plan.env_id,
        env_name=env_names.get(plan.env_id),
        created_at=plan.created_at,
        cases=[
            PlanCaseOut(
                id=l.id,
                case_id=l.case_id,
                enabled=l.enabled,
                step_order=l.step_order,
                case_name=meta[l.case_id].name if l.case_id in meta else None,
                case_type=meta[l.case_id].type if l.case_id in meta else None,
                priority=meta[l.case_id].priority if l.case_id in meta else None,
            )
            for l in links
        ],
    )


def _replace_cases(db: Session, plan_id: int, cases: list) -> None:
    """整体替换用例清单：step_order 直接按提交顺序重排，前端不用自己维护序号。"""
    for old in _load_cases(db, plan_id):
        db.delete(old)
    db.flush()
    for index, item in enumerate(cases, start=1):
        db.add(TestPlanCase(
            plan_id=plan_id,
            case_id=item.case_id,
            step_order=index,
            enabled=item.enabled,
        ))


@router.get("/projects/{project_id}/plans", response_model=Page[PlanBrief],
            summary="计划列表（分页）")
def list_plans(project_id: int, page: PageParams = Depends(), db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    plans, total = paginate(
        db,
        select(TestPlan).where(TestPlan.project_id == project_id).order_by(TestPlan.id.desc()),
        page,
    )

    counts = dict(
        db.execute(
            select(TestPlanCase.plan_id, func.count(TestPlanCase.id))
            .where(TestPlanCase.plan_id.in_([p.id for p in plans] or [0]))
            .group_by(TestPlanCase.plan_id)
        ).all()
    ) if plans else {}
    env_names = _env_names(db, {p.env_id for p in plans if p.env_id})

    return Page(items=[
        PlanBrief(
            id=p.id, project_id=p.project_id, name=p.name, description=p.description,
            env_id=p.env_id, env_name=env_names.get(p.env_id),
            case_count=counts.get(p.id, 0), created_at=p.created_at,
        )
        for p in plans
    ], total=total)


@router.post("/projects/{project_id}/plans", response_model=PlanOut,
             status_code=status.HTTP_201_CREATED, summary="新建计划")
def create_plan(project_id: int, payload: PlanCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    if payload.env_id is not None:
        get_environment_or_404(db, payload.env_id)

    plan = TestPlan(
        project_id=project_id,
        name=payload.name,
        description=payload.description,
        env_id=payload.env_id,
    )
    db.add(plan)
    db.flush()
    _replace_cases(db, plan.id, payload.cases)
    db.commit()
    db.refresh(plan)
    return _to_out(db, plan)


@router.get("/plans/{plan_id}", response_model=PlanOut, summary="计划详情")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    return _to_out(db, get_plan_or_404(db, plan_id))


@router.put("/plans/{plan_id}", response_model=PlanOut, summary="更新计划")
def update_plan(plan_id: int, payload: PlanUpdate, db: Session = Depends(get_db)):
    plan = get_plan_or_404(db, plan_id)
    data = payload.model_dump(exclude_unset=True)

    if "name" in data:
        plan.name = data["name"]
    if "description" in data:
        plan.description = data["description"]
    if "env_id" in data:
        if data["env_id"] is not None:
            get_environment_or_404(db, data["env_id"])
        plan.env_id = data["env_id"]
    if "cases" in data:
        _replace_cases(db, plan.id, payload.cases or [])

    db.commit()
    db.refresh(plan)
    return _to_out(db, plan)


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除计划")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    db.delete(get_plan_or_404(db, plan_id))
    db.commit()


def _run_one(db: Session, case: TestCase, env_dict: dict, *, plan_id: int,
             payload: RunPlanRequest) -> Execution:
    """执行计划里的一条用例并落库，按用例类型分派到接口 / Web 引擎。

    和单条执行接口不同，这里**不因为某条用例自身的问题中止整批**：比如 Web 用例
    还没配好步骤，就记一条 error 继续跑下一条。计划是批量场景，一条没配好不该
    让其余用例都跑不成。
    """
    execution = Execution(
        project_id=case.project_id,
        case_id=case.id,
        plan_id=plan_id,
        status="running",
        start_time=datetime.now(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    if case.type == "web":
        steps = [s for s in (case.steps_json or []) if s.get("enabled", True)]
        if not steps:
            result = {
                "status": "error",
                "duration_ms": 0,
                "error_msg": "该 Web 用例还没有配置可执行的步骤",
                "steps": [],
            }
        else:
            # 截图按执行记录分目录，与单条执行保持同样的落盘结构
            shot_dir = Path(settings.report_dir) / "screenshots" / f"execution_{execution.id}"
            result = web_executor.execute_case(
                case_to_dict(case), env_dict,
                browser=payload.browser,
                headless=payload.headless,
                timeout=payload.web_timeout,
                screenshot_dir=str(shot_dir),
                screenshot_root=settings.report_dir,
            )
    else:
        result = execute_case(case_to_dict(case), env_dict, timeout=payload.timeout)

    execution.status = result["status"]
    execution.end_time = datetime.now()
    execution.duration_ms = result["duration_ms"]
    execution.result_json = result
    db.commit()
    db.refresh(execution)
    return execution


@router.post("/plans/{plan_id}/run", response_model=PlanRunResult, summary="执行计划")
def run_plan(plan_id: int, payload: RunPlanRequest | None = None, db: Session = Depends(get_db)):
    plan = get_plan_or_404(db, plan_id)
    payload = payload or RunPlanRequest()

    links = _load_cases(db, plan.id)
    if not links:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="计划里还没有用例")

    active = [l for l in links if l.enabled]
    skipped = len(links) - len(active)
    if not active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="计划里的用例都被停用了")

    cases = _case_meta(db, {l.case_id for l in active})
    missing = [l.case_id for l in active if l.case_id not in cases]
    if missing:
        # 外键级联正常情况下已经清掉了这类记录，这里只是兜底
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"计划里有已删除的用例：{missing}")

    # 请求里带 env_id 就用它，否则回落到计划绑定的默认环境
    env_id = payload.env_id if payload.env_id is not None else plan.env_id
    env_dict: dict = {}
    if env_id is not None:
        env_dict = env_to_dict(get_environment_or_404(db, env_id))

    results: list[ExecutionOut] = []
    for link in active:
        case = cases[link.case_id]
        execution = _run_one(db, case, env_dict, plan_id=plan.id, payload=payload)
        results.append(execution_out(execution, case.name, case.type))

    statuses = [r.status for r in results]
    if all(s == "pass" for s in statuses):
        overall = "pass"
    elif any(s == "error" for s in statuses):
        overall = "error"
    else:
        overall = "fail"

    return PlanRunResult(
        plan_id=plan.id,
        plan_name=plan.name,
        status=overall,
        total=len(results),
        passed=sum(1 for s in statuses if s == "pass"),
        failed=sum(1 for s in statuses if s != "pass"),
        skipped=skipped,
        total_duration_ms=sum(r.duration_ms for r in results),
        cases=results,
    )
