"""接口压测引擎 —— 纯执行，不碰数据库。

并发模型刻意选 ThreadPoolExecutor + 每线程独立 requests.Session：
- 复用 api_executor.build_request() 与 VariableResolver，避免两套请求语义漂移；
- 当前定位是单机测试工具，并发上限 50，线程模型足够；
- 每线程一个 Session，连接池不跨线程共享，避免 requests.Session 的线程安全问题。

采样只保留「每线程分片 + 固定分桶直方图 + 1 秒时间线」，
不存每条请求明细 —— 否则 10 万请求会把 JSON 列和序列化成本打爆。
"""
from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning

from app.services.api_executor import build_request
from app.services.sanitize import redact_query_params, redact_url, scrub_message
from app.services.variable_resolver import VariableResolver

logger = logging.getLogger(__name__)

# 响应体只读这么多就断开：压测关心的是状态与延迟，不是内容
MAX_DRAIN_BYTES = 2 * 1024 * 1024

# 延迟直方图的桶上界（毫秒）。最后还有一个 >60000ms 的溢出桶。
# 常用区间（1–300ms）桶宽 1–5ms，百分位近似误差可控。
LATENCY_BOUNDS_MS: tuple[float, ...] = (
    1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90,
    100, 120, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1500, 2000,
    3000, 5000, 8000, 10000, 15000, 20000, 30000, 60000,
)

# 脱敏规则统一放在 services/sanitize.py：压测与功能执行必须同一套口径


@dataclass(frozen=True)
class RequestSpec:
    """不可变请求规格。绝不把 ORM 对象、Session 或 Response 传进工作线程。"""

    method: str
    url: str
    headers: dict
    body: bytes | None
    auth: tuple[str, str] | None
    verify_ssl: bool
    timeout: float
    expected_status: int | None = None
    success_rule: str = "2xx/3xx"
    case_name: str = ""
    env_name: str = ""
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class LoadShape:
    """一次压测的负载形状。count 与 duration 两种模式共用同一套 worker 循环。"""

    mode: Literal["count", "duration"]
    concurrency: int
    request_timeout: float
    total_requests: int = 0
    duration_seconds: int = 0
    target_rps: float | None = None
    warmup_seconds: int = 0
    error_rate_threshold: float | None = None  # 0..1，None 表示关闭熔断
    min_requests_before_abort: int = 20
    hard_wall_seconds: int = 900
    max_total_requests: int = 200_000


# ---------------------------------------------------------------------------
# 统计分片
# ---------------------------------------------------------------------------


class LatencyHistogram:
    """固定分桶直方图。内存只与桶数有关，与请求数无关。"""

    def __init__(self, bounds_ms: tuple[float, ...] = LATENCY_BOUNDS_MS):
        self.bounds = tuple(bounds_ms)
        self.counts = [0] * (len(self.bounds) + 1)
        self.total = 0

    def record(self, value_ms: float) -> None:
        value = max(0.0, float(value_ms))
        for index, bound in enumerate(self.bounds):
            if value <= bound:
                self.counts[index] += 1
                break
        else:
            self.counts[-1] += 1
        self.total += 1

    def merge_counts(self, counts: list[int]) -> None:
        for index, count in enumerate(counts):
            if index < len(self.counts):
                self.counts[index] += count
                self.total += count

    def percentile(self, p: float) -> float | None:
        """nearest-rank 百分位 + 桶内线性插值（近似值）。"""
        if self.total <= 0:
            return None
        p = min(100.0, max(0.0, float(p)))
        rank = max(1, math.ceil(self.total * p / 100.0))
        seen = 0
        for index, count in enumerate(self.counts):
            if count <= 0:
                continue
            if seen + count >= rank:
                lower = 0.0 if index == 0 else self.bounds[index - 1]
                upper = self.bounds[index] if index < len(self.bounds) else self.bounds[-1] * 2
                within = (rank - seen) / count
                return round(lower + (upper - lower) * within, 2)
            seen += count
        return float(self.bounds[-1])

    def as_dict(self) -> dict:
        return {"bounds_ms": list(self.bounds), "counts": list(self.counts)}


class WorkerStats:
    """单个工作线程的统计分片。worker 只写自己的分片，没有全局 per-request 锁。"""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.total = 0
        self.success = 0
        self.failed = 0
        self.latency_sum = 0.0
        self.latency_min: float | None = None
        self.latency_max = 0.0
        self.histogram = LatencyHistogram()
        self.status_codes: dict[str, int] = {}
        self.errors = {"connection": 0, "timeout": 0, "http_4xx": 0, "http_5xx": 0, "other": 0}
        self.sample_errors: list[dict] = []
        self.warmup_requests = 0
        self.warmup_errors = 0

    def record(
        self,
        ok: bool,
        status: int | None,
        latency_ms: float,
        error_kind: str | None = None,
        message: str = "",
    ) -> None:
        with self.lock:
            self.total += 1
            if ok:
                self.success += 1
            else:
                self.failed += 1

            self.latency_sum += latency_ms
            self.latency_min = latency_ms if self.latency_min is None else min(self.latency_min, latency_ms)
            self.latency_max = max(self.latency_max, latency_ms)
            self.histogram.record(latency_ms)

            if status is not None:
                key = str(status)
                self.status_codes[key] = self.status_codes.get(key, 0) + 1

            if error_kind:
                self.errors[error_kind] = self.errors.get(error_kind, 0) + 1
                # 每个分片最多留 2 条，最终合并最多 10 条
                if len(self.sample_errors) < 2:
                    self.sample_errors.append({
                        "kind": error_kind,
                        "status": status,
                        "message": scrub_message(message),
                    })

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "total": self.total,
                "success": self.success,
                "failed": self.failed,
                "latency_sum": self.latency_sum,
                "latency_min": self.latency_min,
                "latency_max": self.latency_max,
                "histogram_counts": list(self.histogram.counts),
                "status_codes": dict(self.status_codes),
                "errors": dict(self.errors),
                "sample_errors": list(self.sample_errors),
                "warmup_requests": self.warmup_requests,
                "warmup_errors": self.warmup_errors,
            }


def _merge_stats(parts: list[WorkerStats]) -> dict:
    """合并所有分片。运行中每秒调一次，结束时再调一次。"""
    total = success = failed = 0
    latency_sum = 0.0
    latency_min: float | None = None
    latency_max = 0.0
    histogram = LatencyHistogram()
    status_codes: dict[str, int] = {}
    errors = {"connection": 0, "timeout": 0, "http_4xx": 0, "http_5xx": 0, "other": 0}
    sample_errors: list[dict] = []
    warmup_requests = warmup_errors = 0

    for part in parts:
        snap = part.snapshot()
        total += snap["total"]
        success += snap["success"]
        failed += snap["failed"]
        latency_sum += snap["latency_sum"]
        if snap["latency_min"] is not None:
            latency_min = snap["latency_min"] if latency_min is None else min(latency_min, snap["latency_min"])
        latency_max = max(latency_max, snap["latency_max"])
        histogram.merge_counts(snap["histogram_counts"])
        for key, value in snap["status_codes"].items():
            status_codes[key] = status_codes.get(key, 0) + value
        for key, value in snap["errors"].items():
            errors[key] = errors.get(key, 0) + value
        if len(sample_errors) < 10:
            sample_errors.extend(snap["sample_errors"][: 10 - len(sample_errors)])
        warmup_requests += snap["warmup_requests"]
        warmup_errors += snap["warmup_errors"]

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "latency_sum": latency_sum,
        "latency_min": latency_min,
        "latency_max": latency_max,
        "histogram": histogram,
        "status_codes": status_codes,
        "errors": errors,
        "sample_errors": sample_errors,
        "warmup_requests": warmup_requests,
        "warmup_errors": warmup_errors,
    }


# ---------------------------------------------------------------------------
# 限速与请求
# ---------------------------------------------------------------------------


class RateLimiter:
    """全局令牌间隔限速。

    这是「请求发起速率上限」，不是开环恒定到达率：实际 TPS 仍受并发数和
    目标延迟限制，最大约为 concurrency / avg_latency。
    """

    def __init__(self, rps: float | None):
        self.rps = float(rps) if rps else None
        self.interval = 1.0 / self.rps if self.rps else 0.0
        self.lock = threading.Lock()
        self.next_at = time.perf_counter()

    def wait(self, stop_event: threading.Event) -> bool:
        if not self.rps:
            return not stop_event.is_set()
        with self.lock:
            now = time.perf_counter()
            if self.next_at < now:
                self.next_at = now
            delay = self.next_at - now
            self.next_at += self.interval
        if delay > 0:
            stop_event.wait(delay)
        return not stop_event.is_set()


def _is_success(spec: RequestSpec, status: int | None) -> bool:
    if status is None:
        return False
    if spec.expected_status is not None:
        return status == spec.expected_status
    return 200 <= status < 400


def _classify_status(status: int | None) -> str:
    if status is None:
        return "other"
    if 400 <= status < 500:
        return "http_4xx"
    if 500 <= status < 600:
        return "http_5xx"
    return "other"


def _send_once(
    session: requests.Session, spec: RequestSpec
) -> tuple[str | None, int | None, float, str]:
    """发一次请求。返回 (错误类型, 状态码, 耗时ms, 错误信息)。

    分块读取并丢弃响应体：大响应体不会撑爆内存，也不会把压测机的带宽当成瓶颈。
    """
    start = time.perf_counter()
    try:
        with session.request(
            spec.method,
            spec.url,
            headers=spec.headers,
            data=spec.body,
            params=spec.params or None,
            auth=spec.auth,
            timeout=spec.timeout,
            verify=spec.verify_ssl,
            stream=True,
            allow_redirects=True,
        ) as response:
            status = response.status_code
            drained = 0
            for chunk in response.iter_content(chunk_size=8192):
                drained += len(chunk)
                if drained >= MAX_DRAIN_BYTES:
                    break
        return None, status, (time.perf_counter() - start) * 1000, ""
    except requests.exceptions.Timeout:
        return "timeout", None, (time.perf_counter() - start) * 1000, "请求超时"
    except requests.exceptions.ConnectionError as exc:
        return "connection", None, (time.perf_counter() - start) * 1000, str(exc)[:200]
    except Exception as exc:  # noqa: BLE001 - 压测必须把任何异常记成一次失败，不能中断
        return "other", None, (time.perf_counter() - start) * 1000, f"{type(exc).__name__}: {str(exc)[:150]}"


# ---------------------------------------------------------------------------
# 执行器
# ---------------------------------------------------------------------------


class PerfRunner:
    """一次压测运行。start() 非阻塞；stop() 协作式取消。"""

    def __init__(
        self,
        run_id: int,
        spec: RequestSpec,
        shape: LoadShape,
        on_heartbeat: Callable[[dict], None] | None = None,
        on_finish: Callable[[dict], None] | None = None,
    ):
        self.run_id = run_id
        self.spec = spec
        self.shape = shape
        self.on_heartbeat = on_heartbeat
        self.on_finish = on_finish

        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._stop_reason = ""
        self._active = False
        self._thread: threading.Thread | None = None
        self._metrics: dict = {}
        self._fatal_error = ""

        self._measure_start: float | None = None
        self._wall_start: datetime | None = None
        self._timeline: list[dict] = []
        self._last_snapshot: dict = {}
        self._stats: list[WorkerStats] = []
        self._next_index = 0
        self._index_lock = threading.Lock()

    # ---------- 对外 ----------

    @property
    def active(self) -> bool:
        return self._active

    @property
    def metrics(self) -> dict:
        return self._metrics

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name=f"perf-run-{self.run_id}", daemon=True
        )
        self._thread.start()

    def stop(self, reason: str = "user") -> None:
        with self._lock:
            if not self._stop_reason:
                self._stop_reason = reason
        self._stop_event.set()

    def join(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def live_snapshot(self) -> dict:
        with self._lock:
            return dict(self._last_snapshot)

    # ---------- 内部 ----------

    def _set_reason(self, reason: str) -> None:
        with self._lock:
            if not self._stop_reason:
                self._stop_reason = reason

    def _claim_index(self) -> int | None:
        with self._index_lock:
            if self._next_index >= self.shape.total_requests:
                return None
            index = self._next_index
            self._next_index += 1
            return index

    def _new_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        if not self.spec.verify_ssl:
            session.verify = False
        return session

    def _worker(self, stats: WorkerStats, barrier: threading.Barrier, limiter: RateLimiter) -> None:
        session = self._new_session()
        try:
            # 预热：只建立连接、不吃正式指标，且不限速
            if self.shape.warmup_seconds > 0 and not self._stop_event.is_set():
                deadline = time.perf_counter() + self.shape.warmup_seconds
                while time.perf_counter() < deadline and not self._stop_event.is_set():
                    error_kind, _, _, _ = _send_once(session, self.spec)
                    with stats.lock:
                        stats.warmup_requests += 1
                        if error_kind:
                            stats.warmup_errors += 1

            try:
                barrier.wait(timeout=max(30, int(self.shape.request_timeout) + 10))
            except threading.BrokenBarrierError:
                return

            measure_start = time.perf_counter()
            deadline = (
                measure_start + self.shape.duration_seconds
                if self.shape.mode == "duration"
                else None
            )

            while not self._stop_event.is_set():
                if self.shape.mode == "count":
                    if self._claim_index() is None:
                        break
                elif deadline is not None and time.perf_counter() >= deadline:
                    break

                if not limiter.wait(self._stop_event):
                    break
                if self._stop_event.is_set():
                    break

                error_kind, status, latency_ms, message = _send_once(session, self.spec)
                ok = error_kind is None and _is_success(self.spec, status)
                kind = None if ok else (error_kind or _classify_status(status))
                stats.record(ok, status, latency_ms, kind, message)
        finally:
            session.close()

    def _publish_snapshot(self, merged: dict, elapsed: float, stop_requested: bool) -> None:
        total = merged["total"]
        failed = merged["failed"]
        elapsed_seconds = max(elapsed, 0.001)
        current_tps = self._timeline[-1]["tps"] if self._timeline else total / elapsed_seconds

        if self.shape.mode == "count" and self.shape.total_requests:
            pct = total / self.shape.total_requests * 100
            eta = ((self.shape.total_requests - total) / current_tps) if current_tps > 0 else None
        elif self.shape.mode == "duration" and self.shape.duration_seconds:
            pct = elapsed / self.shape.duration_seconds * 100
            eta = max(0.0, self.shape.duration_seconds - elapsed)
        else:
            pct = 0.0
            eta = None

        histogram = merged["histogram"]
        snapshot = {
            "run_id": self.run_id,
            "status": "running",
            "phase": "load",
            "elapsed_ms": int(elapsed * 1000),
            "requests_done": total,
            "requests_failed": failed,
            "progress_pct": round(min(100.0, max(0.0, pct)), 1),
            "current_tps": round(current_tps, 2),
            "error_rate": round(failed / total, 4) if total else 0,
            "eta_seconds": round(eta, 1) if eta is not None else None,
            "metrics_preview": {
                "avg_ms": round(merged["latency_sum"] / total, 2) if total else 0,
                "p50": histogram.percentile(50),
                "p90": histogram.percentile(90),
                "p95": histogram.percentile(95),
                "p99": histogram.percentile(99),
            },
            "stale": False,
            "stop_requested": stop_requested,
        }
        with self._lock:
            self._last_snapshot = snapshot
        if self.on_heartbeat:
            self.on_heartbeat(snapshot)

    def _append_timeline(self, merged: dict, elapsed: float, interval: float) -> None:
        previous = self._timeline[-1]["_total"] if self._timeline else 0
        previous_failed = self._timeline[-1]["_failed"] if self._timeline else 0
        previous_sum = self._timeline[-1]["_latency_sum"] if self._timeline else 0.0

        delta_total = merged["total"] - previous
        delta_failed = merged["failed"] - previous_failed
        delta_sum = merged["latency_sum"] - previous_sum
        tps = delta_total / interval if interval > 0 else 0.0

        self._timeline.append({
            "sec": len(self._timeline) + 1,
            "total": delta_total,
            "success": delta_total - delta_failed,
            "failed": delta_failed,
            "tps": round(tps, 2),
            "avg_ms": round(delta_sum / delta_total, 2) if delta_total else 0,
            # 内部累计值，输出前会剔除
            "_total": merged["total"],
            "_failed": merged["failed"],
            "_latency_sum": merged["latency_sum"],
        })

    def _check_limits(self, merged: dict, elapsed: float) -> None:
        if self.shape.mode == "duration" and elapsed >= self.shape.duration_seconds:
            self.stop("completed")
            return
        if elapsed >= self.shape.hard_wall_seconds:
            self.stop("wall_timeout")
            return
        if merged["total"] >= self.shape.max_total_requests:
            self.stop("request_cap")
            return

        threshold = self.shape.error_rate_threshold
        if (
            threshold is not None
            and merged["total"] >= self.shape.min_requests_before_abort
            and merged["failed"] / merged["total"] > threshold
        ):
            self.stop("error_rate")

    def _coordinate(self, stats: list[WorkerStats], futures: list) -> None:
        """协调线程：每秒汇总一次、写进度、检查停止条件。"""
        start = time.perf_counter()
        last_tick = start

        while True:
            now = time.perf_counter()
            elapsed = now - start
            done = all(future.done() for future in futures)

            if now - last_tick >= 1.0 or done:
                merged = _merge_stats(stats)
                self._append_timeline(merged, elapsed, max(now - last_tick, 0.001))
                self._publish_snapshot(merged, elapsed, self._stop_event.is_set())
                self._check_limits(merged, elapsed)
                last_tick = now

            if done or self._stop_event.is_set():
                break
            self._stop_event.wait(0.2)

    def _build_metrics(self, stats: list[WorkerStats]) -> dict:
        merged = _merge_stats(stats)
        histogram: LatencyHistogram = merged["histogram"]
        finished = time.perf_counter()
        measure_start = self._measure_start or finished
        window_seconds = max(finished - measure_start, 0.001)
        total = merged["total"]
        failed = merged["failed"]
        success = merged["success"]

        timeline = [
            {key: value for key, value in row.items() if not key.startswith("_")}
            for row in self._timeline
        ]
        peak_tps = max((row["tps"] for row in timeline), default=0.0)

        stop_reason = self._stop_reason or "completed"

        # 桶内插值是近似值，可能略微越过真实 min/max（例如所有请求 63ms，
        # 却落在 (60,70] 桶里插出 64）。夹回精确区间，保证
        # min <= p50 <= p90 <= p95 <= p99 <= max 这条验收断言恒成立。
        low = merged["latency_min"] if merged["latency_min"] is not None else 0.0
        high = merged["latency_max"]

        def _pct(p: float) -> float | None:
            value = histogram.percentile(p)
            if value is None:
                return None
            return round(min(high, max(low, value)), 2)

        metrics = {
            "schema_version": 1,
            "success_rule": self.spec.success_rule,
            "planned": {
                "mode": self.shape.mode,
                "total_requests": self.shape.total_requests,
                "duration_seconds": self.shape.duration_seconds,
                "concurrency": self.shape.concurrency,
                "target_rps": self.shape.target_rps,
                "warmup_seconds": self.shape.warmup_seconds,
            },
            "window": {
                "started_at": (self._wall_start or datetime.now()).isoformat(timespec="seconds"),
                "finished_at": datetime.now().isoformat(timespec="seconds"),
                "duration_ms": int(window_seconds * 1000),
            },
            "counts": {
                "total": total,
                "success": success,
                "failed": failed,
                "success_rate": round(success / total, 4) if total else 0,
                "error_rate": round(failed / total, 4) if total else 0,
            },
            "tps": {
                "avg": round(total / window_seconds, 2),
                "peak": peak_tps,
            },
            "latency_ms": {
                "min": round(merged["latency_min"], 2) if merged["latency_min"] is not None else None,
                "max": round(merged["latency_max"], 2),
                "avg": round(merged["latency_sum"] / total, 2) if total else 0,
                "p50": _pct(50),
                "p90": _pct(90),
                "p95": _pct(95),
                "p99": _pct(99),
            },
            "status_codes": merged["status_codes"],
            "errors": merged["errors"],
            "histogram": histogram.as_dict(),
            "timeline": timeline,
            "sample_errors": merged["sample_errors"],
            "warmup": {
                "seconds": self.shape.warmup_seconds,
                "requests": merged["warmup_requests"],
                "errors": merged["warmup_errors"],
            },
            "stop_reason": stop_reason,
            "partial": stop_reason != "completed",
        }
        if self._fatal_error:
            metrics["error_msg"] = self._fatal_error
        return metrics

    def _run(self) -> None:
        self._active = True
        stats = [WorkerStats() for _ in range(self.shape.concurrency)]
        self._stats = stats
        barrier = threading.Barrier(self.shape.concurrency + 1)
        limiter = RateLimiter(self.shape.target_rps)
        futures: list = []
        executor = ThreadPoolExecutor(
            max_workers=self.shape.concurrency, thread_name_prefix=f"perf-{self.run_id}"
        )

        try:
            for index in range(self.shape.concurrency):
                futures.append(executor.submit(self._worker, stats[index], barrier, limiter))

            # 协调线程也加入 barrier：预热结束、所有 worker 就位后一起开始计时
            try:
                barrier.wait(timeout=max(30, int(self.shape.request_timeout) + 10))
            except threading.BrokenBarrierError:
                self._set_reason("exception")
                self._stop_event.set()

            self._measure_start = time.perf_counter()
            self._wall_start = datetime.now()
            self._coordinate(stats, futures)
        except Exception as exc:  # noqa: BLE001
            self._fatal_error = f"{type(exc).__name__}: {str(exc)[:300]}"
            logger.exception("压测运行 #%s 异常终止", self.run_id)
            self._set_reason("exception")
            self._stop_event.set()
        finally:
            self._stop_event.set()
            executor.shutdown(wait=True, cancel_futures=True)
            metrics = self._build_metrics(stats)
            self._metrics = metrics
            self._active = False
            # 先取快照再进锁：self.live_snapshot() 自己会拿同一把不可重入锁
            final_snapshot = self.live_snapshot()
            with self._lock:
                self._last_snapshot = {
                    **final_snapshot,
                    "status": "finished",
                    "phase": "finished",
                    "stop_requested": True,
                }
            if self.on_finish:
                try:
                    self.on_finish(metrics)
                except Exception:  # noqa: BLE001
                    logger.exception("压测运行 #%s 结果写回失败", self.run_id)


def run_sync(
    run_id: int,
    spec: RequestSpec,
    shape: LoadShape,
    on_heartbeat: Callable[[dict], None] | None = None,
    on_finish: Callable[[dict], None] | None = None,
) -> dict:
    """同步执行一次压测，供离线脚本 / 单元验证使用。内部不碰数据库。"""
    runner = PerfRunner(run_id, spec, shape, on_heartbeat, on_finish)
    runner._run()
    return runner.metrics


# ---------------------------------------------------------------------------
# 用例 → 请求规格
# ---------------------------------------------------------------------------


def build_request_spec(
    case: dict,
    environment: dict | None,
    *,
    timeout: int,
    verify_ssl: bool,
) -> RequestSpec:
    """复用 api_executor.build_request 与 VariableResolver，生成线程安全的请求规格。

    成功判定只取用例里的 status_code + eq 断言（廉价且覆盖最常见的「200 才算成功」）；
    响应体断言不执行 —— JSONPath 解析会污染延迟指标。
    """
    environment = environment or {}
    global_vars = {
        "base_url": (environment.get("base_url") or "").strip().rstrip("/"),
        **(environment.get("variables_json") or {}),
    }
    resolver = VariableResolver(global_vars=global_vars)
    method, url, headers, body, auth, params = build_request(case, environment, resolver)

    expected: int | None = None
    for rule in case.get("assertions_json") or []:
        if rule.get("assertion_type") != "status_code":
            continue
        if (rule.get("operator") or "eq") != "eq":
            continue
        raw = resolver.resolve(str(rule.get("expected_value") or "")).strip()
        try:
            expected = int(raw)
            break
        except (TypeError, ValueError):
            continue

    return RequestSpec(
        method=method,
        url=url,
        headers=headers,
        body=body.encode("utf-8") if body else None,
        auth=auth,
        params=params,
        verify_ssl=verify_ssl,
        timeout=float(timeout),
        expected_status=expected,
        success_rule=f"status_code={expected}" if expected is not None else "2xx/3xx",
        case_name=case.get("name") or "",
        env_name=environment.get("name") or "",
    )


def redact_request_spec(spec: RequestSpec) -> dict:
    """落库用的脱敏请求快照：不存 Authorization、Cookie、密码或请求体原文。"""
    header_names = {name.lower() for name in spec.headers}
    if spec.auth:
        auth_type = "basic"
    elif "authorization" in header_names:
        auth_type = "bearer"
    elif "x-api-key" in header_names:
        auth_type = "apikey"
    else:
        auth_type = "none"

    return {
        "method": spec.method,
        "url": redact_url(spec.url),
        # 查询参数单列（值与 URL 里同一套敏感键规则），前端分两行展示
        "params": redact_query_params(spec.params),
        "header_names": sorted(spec.headers.keys()),
        "body_bytes": len(spec.body) if spec.body else 0,
        "auth_type": auth_type,
        "verify_ssl": spec.verify_ssl,
        "timeout": spec.timeout,
        "expected_status": spec.expected_status,
        "success_rule": spec.success_rule,
    }


# verify_ssl=False 时 requests 每个请求都会刷一条警告，压测下会淹没日志
urllib3.disable_warnings(InsecureRequestWarning)
