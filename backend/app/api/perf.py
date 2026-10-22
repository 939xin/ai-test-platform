"""性能测试（接口压测）接口。

任务列表与创建挂在项目下；详情/更新/删除用任务自身 id。
运行接口只负责创建记录并启动后台线程，**不在请求内跑压测** ——
压测可能持续几分钟，同步路由会被前端 axios 超时和 uvicorn worker 一起卡住。

⚠️ 本模块在 main.py 里挂 guard；新增路由不要忘记这一点。
"""
from datetime import datetime
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.cases import get_case_or_404
from app.api.deps import get_current_user
from app.api.environments import get_environment_or_404
from app.api.executions import case_to_dict, env_to_dict
from app.api.pagination import PageParams, paginate
from app.api.projects import get_project_or_404
from app.config import settings
from app.database import get_db
from app.models import Environment, PerfRun, PerfTask, TestCase, User
from app.schemas.common import Page
from app.schemas.perf import (
    PerfLimits,
    PerfRunAccepted,
    PerfRunBrief,
    PerfRunOut,
    PerfRunProgress,
    PerfStopResult,
    PerfTaskBrief,
    PerfTaskCreate,
    PerfTaskOut,
    PerfTaskUpdate,
    RunPerfRequest,
)
from app.services.perf_run_manager import perf_run_manager
from app.services.perf_runner import (
    LoadShape,
    build_request_spec,
    redact_request_spec,
)

router = APIRouter()

ACTIVE_STATUSES = ("queued", "running", "stopping")
TERMINAL_STATUSES = ("completed", "stopped", "aborted", "failed")


# ---------------------------------------------------------------------------
# 查询与转换助手
# ---------------------------------------------------------------------------


def get_task_or_404(db: Session, task_id: int) -> PerfTask:
    task = db.get(PerfTask, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="压测任务不存在")
    return task


def get_run_or_404(db: Session, run_id: int) -> PerfRun:
    run = db.get(PerfRun, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="压测运行不存在")
    return run


def _case_info_map(db: Session, case_ids: set[int]) -> dict[int, tuple]:
    """一次查回 id → (name, type, method, url)，列表页避免逐行回查。"""
    if not case_ids:
        return {}
    rows = db.execute(
        select(TestCase.id, TestCase.name, TestCase.type, TestCase.method, TestCase.url)
        .where(TestCase.id.in_(case_ids))
    ).all()
    return {row[0]: (row[1], row[2], row[3], row[4]) for row in rows}


def _env_name_map(db: Session, env_ids: set[int]) -> dict[int, str]:
    if not env_ids:
        return {}
    rows = db.execute(
        select(Environment.id, Environment.name).where(Environment.id.in_(env_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


def _task_brief(task: PerfTask, case: tuple | None, env_name: str | None) -> PerfTaskBrief:
    return PerfTaskBrief(
        id=task.id,
        project_id=task.project_id,
        name=task.name,
        description=task.description,
        case_id=task.case_id,
        case_name=case[0] if case else None,
        case_type=case[1] if case else None,
        method=case[2] if case else "",
        url=case[3] if case else "",
        env_id=task.env_id,
        env_name=env_name,
        load_mode=task.load_mode,
        total_requests=task.total_requests,
        duration_seconds=task.duration_seconds,
        concurrency=task.concurrency,
        target_rps=task.target_rps,
        updated_at=task.updated_at,
    )


def _task_out(task: PerfTask, case: tuple | None, env_name: str | None) -> PerfTaskOut:
    brief = _task_brief(task, case, env_name)
    return PerfTaskOut(
        **brief.model_dump(),
        warmup_seconds=task.warmup_seconds,
        request_timeout=task.request_timeout,
        verify_ssl=task.verify_ssl,
        error_rate_threshold=task.error_rate_threshold,
        min_requests_before_abort=task.min_requests_before_abort,
        created_at=task.created_at,
    )


def _run_brief(run: PerfRun) -> PerfRunBrief:
    metrics = run.metrics_json or {}
    counts = metrics.get("counts") or {}
    latency = metrics.get("latency_ms") or {}
    return PerfRunBrief(
        id=run.id,
        project_id=run.project_id,
        task_id=run.task_id,
        task_name=run.task_name,
        case_id=run.case_id,
        case_name=run.case_name,
        env_name=run.env_name,
        status=run.status,
        load_mode=run.load_mode,
        concurrency=run.concurrency,
        total_requests=run.total_requests,
        duration_seconds=run.duration_seconds,
        requests_done=run.requests_done,
        requests_failed=run.requests_failed,
        success_rate=counts.get("success_rate"),
        tps_avg=(metrics.get("tps") or {}).get("avg"),
        p95_ms=latency.get("p95"),
        duration_ms=run.duration_ms,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _run_out(run: PerfRun) -> PerfRunOut:
    brief = _run_brief(run)
    return PerfRunOut(
        **brief.model_dump(),
        target_rps=run.target_rps,
        warmup_seconds=run.warmup_seconds,
        request_timeout=run.request_timeout,
        verify_ssl=run.verify_ssl,
        request_json=run.request_json or {},
        metrics_json=run.metrics_json or {},
        stop_reason=run.stop_reason,
        error_msg=run.error_msg,
        authorized_by=run.authorized_by,
        authorized_at=run.authorized_at,
        last_heartbeat_at=run.last_heartbeat_at,
    )


def _check_case(db: Session, project_id: int, case_id: int) -> TestCase:
    """压测目标必须是本项目的接口用例。"""
    case = get_case_or_404(db, case_id)
    if case.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="用例不属于该项目")
    if case.type != "api":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="性能测试只支持接口用例（type=api）")
    return case


def _check_env(db: Session, project_id: int, env_id: int) -> Environment:
    env = get_environment_or_404(db, env_id)
    if env.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="环境不属于该项目")
    return env


def _check_mode_fields(data: dict) -> None:
    """模式相关的跨字段校验。字段范围本身由 Pydantic 负责（越界 422）。"""
    mode = data.get("load_mode") or "count"
    if mode == "duration":
        if int(data.get("warmup_seconds") or 0) >= int(data.get("duration_seconds") or 1):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="预热时长必须小于压测持续时长")
    if mode == "count":
        rps = data.get("target_rps")
        total = int(data.get("total_requests") or 0)
        if rps and total / float(rps) > settings.perf_max_duration_seconds:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"按目标 RPS={rps} 跑 {total} 个请求预计超过 "
                    f"{settings.perf_max_duration_seconds} 秒上限"
                ),
            )


# ---------------------------------------------------------------------------
# 任务 CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/perf-tasks",
    response_model=Page[PerfTaskBrief],
    summary="压测任务列表（分页）",
)
def list_perf_tasks(
    project_id: int,
    page: PageParams = Depends(),
    keyword: str | None = Query(None, description="按任务名模糊匹配"),
    db: Session = Depends(get_db),
):
    get_project_or_404(db, project_id)
    stmt = select(PerfTask).where(PerfTask.project_id == project_id)
    if keyword:
        stmt = stmt.where(PerfTask.name.contains(keyword))

    rows, total = paginate(db, stmt.order_by(PerfTask.id.desc()), page)
    case_map = _case_info_map(db, {row.case_id for row in rows if row.case_id})
    env_map = _env_name_map(db, {row.env_id for row in rows if row.env_id})
    return Page(
        items=[_task_brief(row, case_map.get(row.case_id), env_map.get(row.env_id)) for row in rows],
        total=total,
    )


@router.post(
    "/projects/{project_id}/perf-tasks",
    response_model=PerfTaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="新建压测任务",
)
def create_perf_task(project_id: int, payload: PerfTaskCreate, db: Session = Depends(get_db)):
    get_project_or_404(db, project_id)
    case = _check_case(db, project_id, payload.case_id)
    env = _check_env(db, project_id, payload.env_id) if payload.env_id is not None else None

    data = payload.model_dump()
    _check_mode_fields(data)
    task = PerfTask(project_id=project_id, **data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_out(task, (case.name, case.type, case.method, case.url), env.name if env else None)


@router.get("/perf-tasks/{task_id}", response_model=PerfTaskOut, summary="压测任务详情")
def get_perf_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    case_map = _case_info_map(db, {task.case_id} if task.case_id else set())
    env_map = _env_name_map(db, {task.env_id} if task.env_id else set())
    return _task_out(task, case_map.get(task.case_id), env_map.get(task.env_id))


@router.put("/perf-tasks/{task_id}", response_model=PerfTaskOut, summary="更新压测任务")
def update_perf_task(task_id: int, payload: PerfTaskUpdate, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    data = payload.model_dump(exclude_unset=True)

    if "case_id" in data:
        if data["case_id"] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="压测任务必须绑定一条接口用例")
        _check_case(db, task.project_id, data["case_id"])
    if "env_id" in data and data["env_id"] is not None:
        _check_env(db, task.project_id, data["env_id"])

    # 未传的字段用库里现值补上，再做跨字段校验
    merged = {
        "load_mode": task.load_mode,
        "total_requests": task.total_requests,
        "duration_seconds": task.duration_seconds,
        "warmup_seconds": task.warmup_seconds,
        "target_rps": task.target_rps,
        **data,
    }
    _check_mode_fields(merged)

    for field, value in data.items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)

    case_map = _case_info_map(db, {task.case_id} if task.case_id else set())
    env_map = _env_name_map(db, {task.env_id} if task.env_id else set())
    return _task_out(task, case_map.get(task.case_id), env_map.get(task.env_id))


@router.delete("/perf-tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="删除压测任务")
def delete_perf_task(task_id: int, db: Session = Depends(get_db)):
    task = get_task_or_404(db, task_id)
    active = db.execute(
        select(PerfRun.id).where(
            PerfRun.task_id == task_id, PerfRun.status.in_(ACTIVE_STATUSES)
        )
    ).first()
    if active is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="该任务还有运行中的压测，请先停止")
    db.delete(task)
    db.commit()


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------


@router.post(
    "/perf-tasks/{task_id}/run",
    response_model=PerfRunAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="启动压测（后台执行，立即返回 run_id）",
)
def run_perf_task(
    task_id: int,
    payload: RunPerfRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    payload = payload or RunPerfRequest()
    task = get_task_or_404(db, task_id)

    if not payload.authorization_confirmed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="请先确认已获得对该系统的压测授权")

    if task.case_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该任务没有绑定接口用例")
    case = _check_case(db, task.project_id, task.case_id)

    env = None
    env_id = payload.env_id if payload.env_id is not None else task.env_id
    if env_id is not None:
        env = _check_env(db, task.project_id, env_id)

    if perf_run_manager.active_count() >= settings.perf_max_active_runs:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="已有压测正在运行，请先停止或等待完成")

    case_dict = {**case_to_dict(case), "name": case.name}
    env_dict = env_to_dict(env) if env else {}
    spec = build_request_spec(
        case_dict,
        env_dict,
        timeout=task.request_timeout,
        verify_ssl=task.verify_ssl,
    )

    parsed = urlsplit(spec.url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="目标 URL 必须是 http/https 地址（请检查用例与环境变量）")

    _check_mode_fields({
        "load_mode": task.load_mode,
        "total_requests": task.total_requests,
        "duration_seconds": task.duration_seconds,
        "warmup_seconds": task.warmup_seconds,
        "target_rps": task.target_rps,
    })

    run = PerfRun(
        project_id=task.project_id,
        task_id=task.id,
        task_name=task.name,
        case_id=case.id,
        case_name=case.name,
        env_id=env.id if env else None,
        env_name=env.name if env else "",
        status="queued",
        load_mode=task.load_mode,
        total_requests=task.total_requests,
        duration_seconds=task.duration_seconds,
        concurrency=task.concurrency,
        target_rps=task.target_rps,
        warmup_seconds=task.warmup_seconds,
        request_timeout=task.request_timeout,
        verify_ssl=task.verify_ssl,
        request_json=redact_request_spec(spec),
        authorized_by=user.username,
        authorized_at=datetime.now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    shape = LoadShape(
        mode=task.load_mode,
        concurrency=task.concurrency,
        request_timeout=float(task.request_timeout),
        total_requests=task.total_requests,
        duration_seconds=task.duration_seconds,
        target_rps=float(task.target_rps) if task.target_rps else None,
        warmup_seconds=task.warmup_seconds,
        # 任务表存百分比 0–100，引擎统一用 0–1
        error_rate_threshold=(
            task.error_rate_threshold / 100.0
            if task.error_rate_threshold is not None else None
        ),
        min_requests_before_abort=task.min_requests_before_abort,
        hard_wall_seconds=settings.perf_hard_wall_seconds,
        max_total_requests=settings.perf_max_total_requests,
    )

    if not perf_run_manager.start(run.id, spec, shape):
        # 竞态：另一个请求刚刚占用了活跃名额。删掉这条 queued 记录，保持库干净。
        db.delete(run)
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="已有压测正在运行，请先停止或等待完成")

    return PerfRunAccepted(run_id=run.id, status="queued")


# ⚠️ 列表必须声明在 /perf-runs/{run_id} 之前，FastAPI 按声明顺序匹配。
@router.get("/perf-runs", response_model=Page[PerfRunBrief], summary="压测运行记录（分页）")
def list_perf_runs(
    project_id: int | None = Query(None),
    task_id: int | None = Query(None),
    status_value: str | None = Query(None, alias="status"),
    page: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    stmt = select(PerfRun)
    if project_id is not None:
        stmt = stmt.where(PerfRun.project_id == project_id)
    if task_id is not None:
        stmt = stmt.where(PerfRun.task_id == task_id)
    if status_value:
        stmt = stmt.where(PerfRun.status == status_value)

    rows, total = paginate(db, stmt.order_by(PerfRun.id.desc()), page)
    return Page(items=[_run_brief(row) for row in rows], total=total)


@router.get("/perf-runs/{run_id}", response_model=PerfRunOut, summary="压测运行详情")
def get_perf_run(run_id: int, db: Session = Depends(get_db)):
    return _run_out(get_run_or_404(db, run_id))


@router.get("/perf-runs/{run_id}/progress", response_model=PerfRunProgress,
            summary="压测实时进度")
def get_perf_run_progress(run_id: int, db: Session = Depends(get_db)):
    run = get_run_or_404(db, run_id)

    # 进程内注册表有实时快照时优先用它；终态或进程重启后回退读数据库
    snapshot = perf_run_manager.live_snapshot(run_id)
    if snapshot and snapshot.get("status") != "finished":
        return PerfRunProgress(**snapshot)

    metrics = run.metrics_json or {}
    counts = metrics.get("counts") or {}
    latency = metrics.get("latency_ms") or {}
    total = counts.get("total", run.requests_done or 0)
    failed = counts.get("failed", run.requests_failed or 0)

    stale = False
    if run.status in ACTIVE_STATUSES:
        heartbeat = run.last_heartbeat_at or run.created_at
        stale = (
            heartbeat is None
            or (datetime.now() - heartbeat).total_seconds() > settings.perf_stale_seconds
        )

    if run.load_mode == "count" and run.total_requests:
        progress_pct = min(100.0, total / run.total_requests * 100)
    elif run.load_mode == "duration" and run.duration_seconds:
        progress_pct = min(100.0, run.duration_ms / 1000 / run.duration_seconds * 100)
    else:
        progress_pct = 100.0 if run.status in TERMINAL_STATUSES else 0.0

    return PerfRunProgress(
        run_id=run.id,
        status=run.status,
        phase="finished" if run.status in TERMINAL_STATUSES else "load",
        elapsed_ms=run.duration_ms,
        requests_done=total,
        requests_failed=failed,
        progress_pct=round(progress_pct, 1),
        current_tps=run.current_tps or 0,
        error_rate=round(failed / total, 4) if total else 0,
        eta_seconds=None,
        metrics_preview={
            "avg_ms": latency.get("avg"),
            "p50": latency.get("p50"),
            "p90": latency.get("p90"),
            "p95": latency.get("p95"),
            "p99": latency.get("p99"),
            "success_rate": counts.get("success_rate"),
        },
        stale=stale,
        stop_requested=run.status == "stopping",
    )


@router.post("/perf-runs/{run_id}/stop", response_model=PerfStopResult, summary="停止压测（幂等）")
def stop_perf_run(run_id: int, db: Session = Depends(get_db)):
    run = get_run_or_404(db, run_id)

    if run.status in TERMINAL_STATUSES:
        return PerfStopResult(run_id=run.id, status=run.status, changed=False)

    changed = perf_run_manager.stop(run_id)
    if not changed and run.status in ACTIVE_STATUSES:
        # 数据库里还显示活跃，但本进程没有对应句柄：进程重启或多 worker 部署
        run.status = "failed"
        run.finished_at = datetime.now()
        run.stop_reason = "stale"
        run.error_msg = "运行进程已失联，已标记失败"
        db.commit()
        return PerfStopResult(run_id=run.id, status="failed", changed=True)

    # manager.stop 用的是它自己的 Session；当前请求的 Session 还停在旧快照上，
    # 先结束事务再 refresh，否则返回体里 status 仍是 running（前端会多转一圈）。
    db.commit()
    db.refresh(run)
    return PerfStopResult(run_id=run.id, status=run.status, changed=True)


@router.delete("/perf-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="删除运行记录（仅终态）")
def delete_perf_run(run_id: int, db: Session = Depends(get_db)):
    run = get_run_or_404(db, run_id)
    if run.status in ACTIVE_STATUSES or perf_run_manager.is_active(run_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="运行中的压测不能删除，请先停止")
    db.delete(run)
    db.commit()


@router.get("/perf-limits", response_model=PerfLimits, summary="本机压测上限")
def get_perf_limits():
    return PerfLimits(
        max_concurrency=settings.perf_max_concurrency,
        max_total_requests=settings.perf_max_total_requests,
        max_duration_seconds=settings.perf_max_duration_seconds,
        max_rps=settings.perf_max_rps,
        max_warmup_seconds=settings.perf_max_warmup_seconds,
        max_request_timeout=settings.perf_max_request_timeout,
        max_active_runs=settings.perf_max_active_runs,
        hard_wall_seconds=settings.perf_hard_wall_seconds,
    )
