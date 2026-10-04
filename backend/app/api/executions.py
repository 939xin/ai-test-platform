"""执行接口。

执行链路：取用例 → 取环境 → 调 services.api_executor.execute_case() → 结果落 execution 表。
执行引擎的断言与请求构造逻辑复用自既有项目，本身不依赖框架。
"""
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.cases import get_case_or_404
from app.api.environments import get_environment_or_404
from app.api.pagination import PageParams, paginate
from app.config import settings
from app.database import get_db
from app.models import Execution, TestCase
from app.schemas.common import Page
from app.schemas.execution import (
    DataDrivenRunResult,
    ExecutionBrief,
    ExecutionOut,
    ExecutionStats,
    RunCaseRequest,
    RunWebRequest,
)
from app.services import web_executor
from app.services.api_executor import execute_case
from app.services.dataset import load_rows

router = APIRouter()


def case_to_dict(case) -> dict:
    """把 ORM 用例转成执行引擎认识的字典。

    接口执行只读前 9 个键；type / steps_json 是给 Web 执行引擎用的，
    多带两个键对接口用例没有影响。

    公开函数：api/plans.py 批量执行计划时复用同一套转换。
    """
    return {
        "type": case.type,
        "method": case.method,
        "url": case.url,
        "headers_json": case.headers_json or {},
        "body_type": case.body_type,
        "body_content": case.body_content,
        "auth_type": case.auth_type,
        "auth_value": case.auth_value,
        "assertions_json": case.assertions_json or [],
        "extract_json": case.extract_json or [],
        "steps_json": case.steps_json or [],
    }


def env_to_dict(env) -> dict:
    """环境转成执行引擎认识的字典（公开函数，plans.py 复用）。"""
    return {
        "name": env.name,
        "base_url": env.base_url,
        "variables_json": env.variables_json or {},
    }


def _case_names(db: Session, case_ids: set[int]) -> dict[int, str]:
    """一次查出 id → 用例名，避免逐行回查（列表和详情共用）。"""
    if not case_ids:
        return {}
    return dict(db.execute(select(TestCase.id, TestCase.name).where(TestCase.id.in_(case_ids))).all())


def _case_types(db: Session, case_ids: set[int]) -> dict[int, str]:
    """一次查出 id → 用例类型（api / web）。列表页靠它区分两类执行。"""
    if not case_ids:
        return {}
    return dict(db.execute(select(TestCase.id, TestCase.type).where(TestCase.id.in_(case_ids))).all())


def execution_out(
    execution: Execution, case_name: str | None, case_type: str | None = None
) -> ExecutionOut:
    """执行记录转成响应模型（公开函数，api/plans.py 复用）。"""
    return ExecutionOut(
        id=execution.id,
        project_id=execution.project_id,
        plan_id=execution.plan_id,
        case_id=execution.case_id,
        case_name=case_name,
        case_type=case_type,
        status=execution.status,
        start_time=execution.start_time,
        end_time=execution.end_time,
        duration_ms=execution.duration_ms,
        result_json=execution.result_json or {},
        created_at=execution.created_at,
    )


@router.post(
    "/cases/{case_id}/run",
    response_model=ExecutionOut,
    summary="执行单条接口用例",
)
def run_case(
    case_id: int,
    payload: RunCaseRequest | None = None,
    db: Session = Depends(get_db),
):
    case = get_case_or_404(db, case_id)
    payload = payload or RunCaseRequest()

    env_dict: dict = {}
    if payload.env_id is not None:
        env_dict = env_to_dict(get_environment_or_404(db, payload.env_id))

    # 先落一条 running 记录，执行完再更新，保证异常时也有痕迹
    execution = Execution(
        project_id=case.project_id,
        case_id=case.id,
        status="running",
        start_time=datetime.now(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    result = execute_case(case_to_dict(case), env_dict, timeout=payload.timeout)

    execution.status = result["status"]
    execution.end_time = datetime.now()
    execution.duration_ms = result["duration_ms"]
    execution.result_json = result
    db.commit()
    db.refresh(execution)

    return execution


@router.post(
    "/cases/{case_id}/run-web",
    response_model=ExecutionOut,
    summary="执行单条 Web UI 用例",
)
def run_web_case(
    case_id: int,
    payload: RunWebRequest | None = None,
    db: Session = Depends(get_db),
):
    """执行 Web 用例：起浏览器 → 逐步执行 steps_json → 截图落盘 → 结果落库。

    浏览器起不来时**依然返回 200 并落一条 status=error 的执行记录**（错误原因写在
    result_json.error_msg），与接口侧「执行记录一定留有痕迹」的风格保持一致，
    也方便前端在执行详情里直接看到失败原因。
    """
    case = get_case_or_404(db, case_id)
    payload = payload or RunWebRequest()

    if case.type != "web":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该用例不是 Web UI 用例（type=api），请用 /run 执行")

    # 编辑阶段允许先存草稿，真正执行时才要求有步骤
    if not [s for s in (case.steps_json or []) if s.get("enabled", True)]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该用例还没有配置可执行的 Web 步骤")

    env_dict: dict = {}
    if payload.env_id is not None:
        env_dict = env_to_dict(get_environment_or_404(db, payload.env_id))

    execution = Execution(
        project_id=case.project_id,
        case_id=case.id,
        status="running",
        start_time=datetime.now(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # 截图按执行记录分目录，文件名全 ASCII，避开中文路径在驱动侧的各种坑
    shot_dir = Path(settings.report_dir) / "screenshots" / f"execution_{execution.id}"
    result = web_executor.execute_case(
        case_to_dict(case), env_dict,
        browser=payload.browser,
        headless=payload.headless,
        timeout=payload.timeout,
        screenshot_dir=str(shot_dir),
        screenshot_root=settings.report_dir,
    )

    execution.status = result["status"]
    execution.end_time = datetime.now()
    execution.duration_ms = result["duration_ms"]
    execution.result_json = result
    db.commit()
    db.refresh(execution)

    return execution


@router.post("/cases/{case_id}/run-data-driven", response_model=DataDrivenRunResult,
             summary="按数据文件逐行执行用例")
def run_case_data_driven(
    case_id: int,
    payload: RunCaseRequest | None = None,
    db: Session = Depends(get_db),
):
    """一条用例按数据文件的每一行各跑一次；每行的列名当作运行时变量注入。

    行数据走「运行时变量」通道，优先级高于环境的全局变量。
    """
    case = get_case_or_404(db, case_id)
    payload = payload or RunCaseRequest()

    if not case.data_file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该用例没有绑定数据文件")

    try:
        rows = load_rows(case.project_id, case.data_file)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="数据文件里没有可用的数据行（只有表头或内容为空）")

    env_dict: dict = {}
    if payload.env_id is not None:
        env_dict = env_to_dict(get_environment_or_404(db, payload.env_id))
    global_vars = env_dict.get("variables_json") or {}

    results: list[ExecutionOut] = []
    for index, row in enumerate(rows, start=1):
        execution = Execution(
            project_id=case.project_id,
            case_id=case.id,
            status="running",
            start_time=datetime.now(),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)

        # 行数据覆盖全局变量：{**全局, **当前行}
        merged_env = {**env_dict, "variables_json": {**global_vars, **row}}
        result = execute_case(case_to_dict(case), merged_env, timeout=payload.timeout)
        result["row_index"] = index
        result["row_data"] = row

        execution.status = result["status"]
        execution.end_time = datetime.now()
        execution.duration_ms = result["duration_ms"]
        execution.result_json = result
        db.commit()
        db.refresh(execution)

        results.append(execution_out(execution, case.name, case.type))

    return DataDrivenRunResult(
        case_id=case.id,
        case_name=case.name,
        data_file=case.data_file,
        total=len(results),
        passed=sum(1 for r in results if r.status == "pass"),
        failed=sum(1 for r in results if r.status != "pass"),
        rows=results,
    )


def _execution_filters(
    project_id: int | None, case_id: int | None, status_value: str | None
) -> list:
    """列表与统计接口共用的筛选条件。

    两处要是各写一份，早晚会出现「列表筛了、统计没筛」的口径不一致。
    """
    conds = []
    if project_id is not None:
        conds.append(Execution.project_id == project_id)
    if case_id is not None:
        conds.append(Execution.case_id == case_id)
    if status_value:
        conds.append(Execution.status == status_value)
    return conds


# ⚠️ 这条必须声明在 /executions/{execution_id} 之前：
# FastAPI 按声明顺序匹配，否则 "stats" 会被当成执行 id 去解析成整数，直接 422。
@router.get("/executions/stats", response_model=ExecutionStats, summary="执行统计（全量）")
def execution_stats(
    project_id: int | None = Query(None),
    case_id: int | None = Query(None),
    status: str | None = Query(None, description="按执行状态筛选：pass / fail / error / running"),
    db: Session = Depends(get_db),
):
    """统计**筛选后的全部**记录，不受分页影响。

    执行中心的统计卡原来拿加载到的那一页在算，分页之后会变成「翻一页数字就变」——
    所以统计口径必须落在这里，而不是前端对当前页 reduce。
    """
    conds = _execution_filters(project_id, case_id, status)
    stmt = select(Execution.status, func.count()).group_by(Execution.status)
    if conds:
        stmt = stmt.where(*conds)
    counts = dict(db.execute(stmt).all())

    # fail 与 error 合并成一个「失败」口径 —— 与执行中心那张卡一致
    return ExecutionStats(
        total=sum(counts.values()),
        passed=counts.get("pass", 0),
        failed=counts.get("fail", 0) + counts.get("error", 0),
    )


@router.get("/executions", response_model=Page[ExecutionBrief], summary="执行历史（分页）")
def list_executions(
    project_id: int | None = Query(None),
    case_id: int | None = Query(None),
    status: str | None = Query(None, description="按执行状态筛选：pass / fail / error / running"),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    stmt = select(Execution)
    conds = _execution_filters(project_id, case_id, status)
    if conds:
        stmt = stmt.where(*conds)

    rows, total = paginate(db, stmt.order_by(Execution.id.desc()), page)
    case_ids = {row.case_id for row in rows if row.case_id is not None}
    name_map = _case_names(db, case_ids)
    type_map = _case_types(db, case_ids)

    return Page(items=[
        ExecutionBrief(
            id=row.id,
            project_id=row.project_id,
            case_id=row.case_id,
            case_name=name_map.get(row.case_id),
            case_type=type_map.get(row.case_id),
            status=row.status,
            duration_ms=row.duration_ms,
            created_at=row.created_at,
        )
        for row in rows
    ], total=total)


@router.get("/executions/{execution_id}", response_model=ExecutionOut, summary="执行详情")
def get_execution(execution_id: int, db: Session = Depends(get_db)):
    execution = db.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")

    case_ids = {execution.case_id} if execution.case_id else set()
    name_map = _case_names(db, case_ids)
    type_map = _case_types(db, case_ids)
    return execution_out(execution, name_map.get(execution.case_id), type_map.get(execution.case_id))
