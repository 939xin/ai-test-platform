"""压测自检靶子 —— 仅供 verify_all.py 使用。

为什么需要它：压测验收要稳定地制造「20ms 延迟 / 500 错误 / 超时 / 限速」，
依赖 httpbin 会被外网抖动带偏，断言会随机红。这个端点在本机、参数可控、
延迟用 asyncio.sleep 不占线程池。

⚠️ 挂在 guard 之内，且延迟/大小都有硬限制；不对外宣传。
"""
import asyncio
import json

from fastapi import APIRouter, Query, Response

router = APIRouter()


@router.get("/perf-target/echo", summary="压测验收靶子（内部使用）")
async def perf_target_echo(
    delay_ms: int = Query(0, ge=0, le=2000, description="模拟服务端处理延迟"),
    status: int = Query(200, ge=200, le=599, description="返回的状态码"),
    size: int = Query(0, ge=0, le=1024 * 1024, description="响应体字节数"),
):
    if delay_ms:
        await asyncio.sleep(delay_ms / 1000)

    # 204 / 304 按规范不能带 body
    if status in (204, 304):
        return Response(status_code=status)

    if size:
        return Response(content=b"x" * size, status_code=status, media_type="text/plain")

    body = json.dumps({
        "ok": status < 400,
        "status": status,
        "delay_ms": delay_ms,
        "size": size,
    })
    return Response(content=body, status_code=status, media_type="application/json")
