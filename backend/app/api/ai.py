"""AI 辅助接口：用例生成 / 失败分析。

每次调用（含失败）都往 ai_task 落一条记录：type / input / output / status。
该表没有 project_id、case_id 字段，上下文一律写进 input 的 JSON 里。
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.projects import get_project_or_404
from app.database import get_db
from app.models import AITask, Execution, TestCase
from app.schemas.ai import (
    AnalyzeFailureRequest,
    AnalyzeFailureResponse,
    GeneratedCase,
    GenerateCasesRequest,
    GenerateCasesResponse,
)
from app.services.ai_client import AIError, chat_json
from app.services.ai_prompts import (
    ANALYZE_FAILURE_SYSTEM,
    GENERATE_CASES_SYSTEM,
    build_analyze_failure_user,
    build_generate_cases_user,
    json_dumps,
)

router = APIRouter()

# 响应体动辄几百 KB，全塞进提示词既费 token 也没用，截断后取前段足够定位问题
FAILURE_BODY_LIMIT = 2000


def _log_task(db: Session, task_type: str, input_text: str, output_text: str, task_status: str) -> AITask:
    """落一条 AI 调用记录。成功失败都落，失败时 output 存错误说明或模型原始返回。"""
    task = AITask(
        type=task_type,
        input=input_text,
        output=output_text or "",
        status=task_status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _as_str_list(value) -> list[str]:
    """把模型给的「字符串数组」规整成 list[str]。

    模型偶尔会返回单个字符串、或数组里混进数字，这里统一转字符串，
    免得响应模型校验失败把整次分析结果废掉。
    """
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


@router.post(
    "/ai/generate-cases",
    response_model=GenerateCasesResponse,
    summary="根据接口文档生成测试用例",
)
def generate_cases(payload: GenerateCasesRequest, db: Session = Depends(get_db)):
    get_project_or_404(db, payload.project_id)
    input_text = payload.model_dump_json()

    try:
        data, raw = chat_json(
            GENERATE_CASES_SYSTEM,
            build_generate_cases_user(payload.doc_text, payload.hint, payload.count),
        )
    except AIError as e:
        _log_task(db, "generate_cases", input_text, e.raw or e.message, "failed")
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    # 模型有时直接给数组、有时包一层 {"cases": [...]}，两种都认
    raw_cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(raw_cases, list) or not raw_cases:
        _log_task(db, "generate_cases", input_text, raw, "failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 没有返回任何用例，请补充接口文档内容后重试",
        )

    cases: list[GeneratedCase] = []
    skipped: list[str] = []
    for item in raw_cases:
        try:
            cases.append(GeneratedCase.model_validate(item))
        except ValidationError:
            # 单条不合规就跳过，不连累整批 —— 让用户拿到能用的部分，并明说少了几条
            name = item.get("name") if isinstance(item, dict) else None
            skipped.append(str(name or "(未命名)"))

    if not cases:
        _log_task(db, "generate_cases", input_text, raw, "failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 返回的用例字段都不合规，请重试或换个描述方式",
        )

    task = _log_task(db, "generate_cases", input_text, raw, "success")
    message = f"成功生成 {len(cases)} 条用例"
    if skipped:
        message += f"，另有 {len(skipped)} 条因字段不合规被跳过：{'、'.join(skipped)}"

    return GenerateCasesResponse(task_id=task.id, cases=cases, message=message)


@router.post(
    "/ai/analyze-failure",
    response_model=AnalyzeFailureResponse,
    summary="分析失败执行的原因",
)
def analyze_failure(payload: AnalyzeFailureRequest, db: Session = Depends(get_db)):
    execution = db.get(Execution, payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")

    context = _build_failure_context(db, execution)
    input_text = json_dumps({"execution_id": execution.id, **context})

    try:
        data, raw = chat_json(ANALYZE_FAILURE_SYSTEM, build_analyze_failure_user(context))
    except AIError as e:
        _log_task(db, "analyze_failure", input_text, e.raw or e.message, "failed")
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    if not isinstance(data, dict):
        _log_task(db, "analyze_failure", input_text, raw, "failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI 返回的分析结果格式不正确，请重试",
        )

    task = _log_task(db, "analyze_failure", input_text, raw, "success")
    return AnalyzeFailureResponse(
        task_id=task.id,
        possible_causes=_as_str_list(data.get("possible_causes")),
        troubleshooting_steps=_as_str_list(data.get("troubleshooting_steps")),
        fix_suggestion=str(data.get("fix_suggestion") or ""),
    )


def _build_failure_context(db: Session, execution: Execution) -> dict:
    """从执行记录里抽出喂给模型的上下文。

    result_json 的结构见 services/api_executor.py 的返回值：
    {status, duration_ms, request, response, assertions, extracted, extract_errors, error_msg}
    """
    result = execution.result_json or {}
    request = result.get("request") or {}
    response = result.get("response") or {}

    case = db.get(TestCase, execution.case_id) if execution.case_id else None

    body = response.get("body")
    if isinstance(body, str) and len(body) > FAILURE_BODY_LIMIT:
        body = body[:FAILURE_BODY_LIMIT] + "…（已截断）"

    return {
        "case_name": case.name if case else "（用例已删除）",
        "status": execution.status,
        "duration_ms": execution.duration_ms,
        "method": request.get("method"),
        "url": request.get("url"),
        "request_headers": request.get("headers"),
        "request_body": request.get("body"),
        "response_status": response.get("status"),
        "response_body": body,
        "assertions": result.get("assertions"),
        "error_msg": result.get("error_msg"),
    }
