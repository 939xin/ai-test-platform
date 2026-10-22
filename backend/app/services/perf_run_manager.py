"""压测运行管理器。

职责：
- 维护进程内活跃运行注册表（单 uvicorn worker 前提）；
- 启动后台协调线程，**后台线程绝不复用请求内的 SQLAlchemy Session**；
- 每秒心跳写进度，结束时条件更新最终状态；
- 启动时把进程重启遗留的 queued/running/stopping 标记为 failed。

为什么不用 FastAPI BackgroundTasks：它依附请求生命周期，无法按 run_id 取消，
也无法跨请求读取实时指标。
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update

from app.config import settings
from app.database import SessionLocal
from app.models import PerfRun
from app.services.perf_runner import LoadShape, PerfRunner, RequestSpec

logger = logging.getLogger(__name__)

# 本进程标识。当前单 worker 下固定一个值；写进 perf_run 是为将来多进程留的区分位。
RUNNER_ID = uuid.uuid4().hex


@dataclass
class _Handle:
    runner: PerfRunner


def final_status(stop_reason: str) -> str:
    """把停止原因映射成运行终态。"""
    if stop_reason == "completed":
        return "completed"
    if stop_reason == "user":
        return "stopped"
    if stop_reason in ("error_rate", "wall_timeout", "request_cap"):
        return "aborted"
    if stop_reason in ("shutdown", "exception"):
        return "failed"
    return "completed"


class PerfRunManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handles: dict[int, _Handle] = {}

    # ---------- 对外 ----------

    def active_count(self) -> int:
        with self._lock:
            return len(self._handles)

    def is_active(self, run_id: int) -> bool:
        with self._lock:
            return run_id in self._handles

    def start(
        self,
        run_id: int,
        spec: RequestSpec,
        shape: LoadShape,
    ) -> bool:
        """注册并启动。超过活跃上限返回 False（API 转成 409）。"""
        with self._lock:
            if len(self._handles) >= settings.perf_max_active_runs:
                return False
            if run_id in self._handles:
                return False
            runner = PerfRunner(
                run_id,
                spec,
                shape,
                on_heartbeat=lambda snapshot: self._on_heartbeat(run_id, snapshot),
                on_finish=lambda metrics: self._on_finish(run_id, metrics),
            )
            self._handles[run_id] = _Handle(runner=runner)

        # 先把句柄放进注册表再启动线程：否则线程跑完立刻回调 on_finish 时找不到自己
        self._mark_running(run_id)
        runner.start()
        return True

    def stop(self, run_id: int, reason: str = "user") -> bool:
        """请求停止。不在这里等待 worker 排空 —— 前端继续轮询到终态。"""
        with self._lock:
            handle = self._handles.get(run_id)
        if handle is None:
            return False

        handle.runner.stop(reason)
        db = SessionLocal()
        try:
            db.execute(
                update(PerfRun)
                .where(PerfRun.id == run_id, PerfRun.status.in_(["queued", "running"]))
                .values(status="stopping")
            )
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("压测运行 #%s 标记 stopping 失败", run_id)
            db.rollback()
        finally:
            db.close()
        return True

    def live_snapshot(self, run_id: int) -> dict | None:
        with self._lock:
            handle = self._handles.get(run_id)
        return handle.runner.live_snapshot() if handle else None

    def shutdown(self) -> None:
        with self._lock:
            handles = list(self._handles.values())
        for handle in handles:
            handle.runner.stop("shutdown")
        for handle in handles:
            handle.runner.join(timeout=3)

    def reap_stale_runs(self, db=None) -> int:
        """把进程重启 / 心跳中断的运行标记为 failed。

        启动时调用。本进程注册表里正在跑的一律跳过（避免误杀）。
        """
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            cutoff = datetime.now() - timedelta(seconds=settings.perf_stale_seconds)
            rows = db.execute(
                select(PerfRun).where(PerfRun.status.in_(["queued", "running", "stopping"]))
            ).scalars().all()

            reaped = 0
            for row in rows:
                if self.is_active(row.id):
                    continue
                heartbeat = row.last_heartbeat_at or row.created_at
                if heartbeat is not None and heartbeat > cutoff:
                    continue

                total = row.requests_done or 0
                failed = row.requests_failed or 0
                row.status = "failed"
                row.finished_at = datetime.now()
                row.stop_reason = "stale"
                row.error_msg = "服务重启或心跳中断，运行已终止"
                row.metrics_json = {
                    "schema_version": 1,
                    "partial": True,
                    "stop_reason": "stale",
                    "counts": {
                        "total": total,
                        "success": max(0, total - failed),
                        "failed": failed,
                        "success_rate": round((total - failed) / total, 4) if total else 0,
                        "error_rate": round(failed / total, 4) if total else 0,
                    },
                }
                reaped += 1

            if reaped:
                db.commit()
            return reaped
        except Exception:  # noqa: BLE001
            logger.exception("清理遗留压测运行失败")
            db.rollback()
            return 0
        finally:
            if own_session:
                db.close()

    # ---------- 内部 ----------

    def _mark_running(self, run_id: int) -> None:
        db = SessionLocal()
        try:
            db.execute(
                update(PerfRun)
                .where(PerfRun.id == run_id)
                .values(
                    status="running",
                    started_at=datetime.now(),
                    last_heartbeat_at=datetime.now(),
                    runner_id=RUNNER_ID,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("压测运行 #%s 标记 running 失败", run_id)
            db.rollback()
        finally:
            db.close()

    def _on_heartbeat(self, run_id: int, snapshot: dict) -> None:
        """协调线程每秒回调一次。只更新计数与心跳，**不改状态** ——
        否则用户点了停止（stopping）会被下一拍覆盖回 running。"""
        db = SessionLocal()
        try:
            db.execute(
                update(PerfRun)
                .where(PerfRun.id == run_id)
                .values(
                    requests_done=snapshot.get("requests_done", 0),
                    requests_failed=snapshot.get("requests_failed", 0),
                    current_tps=snapshot.get("current_tps", 0),
                    last_heartbeat_at=datetime.now(),
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            # 心跳写失败不能中断压测本身，下一拍会再试
            logger.warning("压测运行 #%s 心跳写库失败", run_id, exc_info=True)
            db.rollback()
        finally:
            db.close()

    def _on_finish(self, run_id: int, metrics: dict) -> None:
        stop_reason = metrics.get("stop_reason") or "completed"
        status_value = final_status(stop_reason)
        counts = metrics.get("counts") or {}
        window = metrics.get("window") or {}
        duration_ms = int(window.get("duration_ms") or 0)

        db = SessionLocal()
        try:
            # 条件更新：reaper 已经把记录标成 failed 时不要再覆盖
            result = db.execute(
                update(PerfRun)
                .where(
                    PerfRun.id == run_id,
                    PerfRun.status.in_(["queued", "running", "stopping"]),
                )
                .values(
                    status=status_value,
                    finished_at=datetime.now(),
                    duration_ms=duration_ms,
                    requests_done=counts.get("total", 0),
                    requests_failed=counts.get("failed", 0),
                    current_tps=(metrics.get("tps") or {}).get("avg", 0),
                    last_heartbeat_at=datetime.now(),
                    stop_reason=stop_reason,
                    error_msg=metrics.get("error_msg", ""),
                    metrics_json=metrics,
                )
            )
            db.commit()
            if result.rowcount == 0:
                logger.warning("压测运行 #%s 已不在活跃状态，最终结果未覆盖", run_id)
        except Exception:  # noqa: BLE001
            logger.exception("压测运行 #%s 最终结果写库失败", run_id)
            db.rollback()
        finally:
            db.close()
            with self._lock:
                self._handles.pop(run_id, None)


# 进程内单例
perf_run_manager = PerfRunManager()
