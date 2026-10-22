"""场景执行 —— 多个用例按 step_order 串联，上一步提取的变量传给下一步。

设计要点：整个场景**共用一个 VariableResolver**，每步跑完把提取到的变量
`set_extra_var()` 灌进去；下一步执行时把「全局变量 + 运行时变量」合并后作为
环境变量传给 `execute_case`，这样下一步里的 ${变量名} 就能解析到上一步的取值。

之所以不去改 execute_case 的签名（让它接受一个现成 resolver），是因为合并
变量字典这一步是不侵入的：`get_all_variables()` 返回的正是「运行时优先」的结果。
"""
import time
from datetime import datetime

from app.services.api_executor import error_result, execute_case
from app.services.variable_resolver import VariableResolver


def run_scenario(steps: list[dict], environment: dict | None = None, timeout: int = 30) -> dict:
    """按顺序执行场景步骤。

    steps 元素：{"case_id": int, "case_name": str, "case": dict, "fail_strategy": "stop"|"continue"}
                （case 是执行引擎认识的用例字典，由 api 层组装好）

    返回 {"status", "steps", "variables", "total_duration_ms"}。
    因 fail_strategy=stop 中止时，剩余步骤会以 status="skip" 记进结果，方便前端说明原因。
    """
    environment = environment or {}
    resolver = VariableResolver(global_vars=environment.get("variables_json") or {})

    step_results: list[dict] = []
    stopped = False

    for index, step in enumerate(steps, start=1):
        if stopped:
            step_results.append({
                "step_order": index,
                "case_id": step["case_id"],
                "case_name": step.get("case_name", ""),
                "status": "skip",
                "duration_ms": 0,
                "extracted": {},
                "note": "前一步失败且失败策略为「中止」，本步未执行",
            })
            continue

        merged_env = {**environment, "variables_json": resolver.get_all_variables()}
        # 真实起止时间：api 层落 execution 时直接用它，
        # 而不是落库那一刻 now() 出来的「同一刻」——那样执行时长在界面上是假的
        started_at = datetime.now()
        step_started = time.time()
        try:
            result = execute_case(step["case"], merged_env, timeout=timeout)
        except Exception as e:
            # 单步异常必须就地转成 error 结果：异常一旦穿透到 api 层，
            # scenarios.py 的落库循环根本走不到 —— 前面几步明明真跑了，
            # 执行中心却一条记录都没有。失败策略照旧由下面的统一判断处理。
            result = error_result(e, int((time.time() - step_started) * 1000))

        # 提取到的变量并入运行时变量，供后续步骤引用
        extracted = result.get("extracted") or {}
        for name, value in extracted.items():
            if value is not None:
                resolver.set_extra_var(name, value)

        step_results.append({
            "step_order": index,
            "case_id": step["case_id"],
            "case_name": step.get("case_name", ""),
            "status": result["status"],
            "duration_ms": result["duration_ms"],
            "started_at": started_at,
            "finished_at": datetime.now(),
            "extracted": extracted,
            "result": result,
        })

        if result["status"] != "pass" and step.get("fail_strategy", "stop") == "stop":
            stopped = True

    executed = [s for s in step_results if s["status"] != "skip"]
    if any(s["status"] == "error" for s in executed):
        overall = "error"
    elif any(s["status"] != "pass" for s in executed):
        overall = "fail"
    else:
        overall = "pass"

    return {
        "status": overall,
        "steps": step_results,
        "variables": resolver.get_all_variables(),
        "total_duration_ms": sum(s["duration_ms"] for s in step_results),
    }
