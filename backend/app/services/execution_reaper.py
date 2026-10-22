"""启动清扫：把上一个进程遗留的 running 执行记录标成 error。

为什么需要：执行记录是「先写 running、跑完再回写终态」的。进程被 Ctrl+C、
崩溃或重启时，那条记录没有任何机会被回写，前端就永远显示「执行中」。
压测模块有 `perf_run_manager.reap_stale_runs()`，功能执行此前没有对应机制。

判据只用 start_time：running 记录在正常执行中也会长时间不更新（没有心跳），
所以只能按「开始至今超过 N 分钟」判断 —— 这也是阈值默认给到 60 分钟的原因，
宁可漏收，不能把正在跑的长用例误标成失败。
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)

_REAP_SQL = text("""
    UPDATE execution
       SET status = 'error',
           end_time = NOW(),
           result_json = JSON_SET(
               COALESCE(result_json, JSON_OBJECT()),
               '$.error_msg',
               :msg
           )
     WHERE status = 'running'
       AND start_time IS NOT NULL
       AND start_time < :cutoff
""")


def reap_stale_executions(stale_minutes: int | None = None) -> int:
    """把所有超时的 running 记录批量改成 error，返回受影响行数。

    单条 UPDATE 完成：这里要处理的是「积压了一夜的一堆记录」，
    逐行查再逐行改会在启动时拖出几十次往返。
    """
    minutes = settings.execution_stale_minutes if stale_minutes is None else stale_minutes
    cutoff = datetime.now() - timedelta(minutes=minutes)

    db = SessionLocal()
    try:
        result = db.execute(_REAP_SQL, {
            "msg": "进程重启或执行超时，本次执行未完成",
            "cutoff": cutoff,
        })
        db.commit()
        count = result.rowcount or 0
    finally:
        db.close()

    if count:
        logger.warning("启动清扫：%d 条超时未完成的执行记录已标为 error", count)
    return count
