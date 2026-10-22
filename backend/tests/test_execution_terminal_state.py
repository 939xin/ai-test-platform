"""执行记录必达终态（P0-2）。

两条链路各有一组：
- 纯函数层（场景执行）不依赖数据库，任何机器都能跑；
- 落库链路（单条执行、启动清扫）需要开发库，没有 MySQL 时自动跳过。

刻意不用真实 HTTP 请求去打外部地址：单条执行那条把 `execute_case` 换成
直接抛异常，验证的是「异常也一定写回终态」，与网络无关。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
# 别名：类名 TestCase 会被 pytest 当成测试类去收集（有 __init__ 就报警告）
from app.models import Execution, Project, TestCase as CaseRow


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="需要 MySQL 开发库；其余单元测试不依赖数据库"
)


# ---------- 纯函数层：场景执行 ----------

def test_scenario_runner_step_exception_becomes_error(monkeypatch):
    """某一步执行器抛异常时，该步记 error，后续步骤照常按失败策略处理。"""
    import app.services.scenario_runner as runner_module

    calls = []

    def fake_execute(case, env, timeout=30):
        calls.append(case["url"])
        if case["url"] == "boom":
            raise RuntimeError("模拟执行器崩溃")
        return {"status": "pass", "duration_ms": 1, "extracted": {}, "request": {}, "response": {}}

    monkeypatch.setattr(runner_module, "execute_case", fake_execute)

    steps = [
        {"case_id": 1, "case_name": "炸", "case": {"url": "boom"}, "fail_strategy": "continue"},
        {"case_id": 2, "case_name": "好", "case": {"url": "ok"}, "fail_strategy": "stop"},
    ]
    result = runner_module.run_scenario(steps, {})

    assert result["status"] == "error"
    assert result["steps"][0]["status"] == "error"
    assert "模拟执行器崩溃" in result["steps"][0]["result"]["error_msg"]
    # continue 策略下第二步必须真的被执行
    assert result["steps"][1]["status"] == "pass"
    assert calls == ["boom", "ok"]


def test_scenario_runner_step_exception_respects_stop_strategy(monkeypatch):
    import app.services.scenario_runner as runner_module

    def fake_execute(case, env, timeout=30):
        raise RuntimeError("炸")

    monkeypatch.setattr(runner_module, "execute_case", fake_execute)
    steps = [
        {"case_id": 1, "case_name": "炸", "case": {"url": "x"}, "fail_strategy": "stop"},
        {"case_id": 2, "case_name": "不该跑", "case": {"url": "y"}, "fail_strategy": "stop"},
    ]
    result = runner_module.run_scenario(steps, {})

    assert result["steps"][1]["status"] == "skip"
    # 场景结果仍然完整返回，才能让 api 层逐条落库
    assert len(result["steps"]) == 2


# ---------- 落库链路 ----------

@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def project(db):
    """临时项目，测试结束连带删掉它下面的用例 / 执行记录（外键 CASCADE）。"""
    row = Project(name="[单元测试] 执行终态")
    db.add(row)
    db.commit()
    db.refresh(row)
    yield row
    db.delete(row)
    db.commit()


@requires_db
def test_run_case_exception_still_writes_terminal_state(db, project, monkeypatch):
    """执行器抛异常时接口照常返回 200，记录必须是 error + end_time，不能停在 running。"""
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.main import app

    case = CaseRow(project_id=project.id, name="[单元测试] 执行器崩溃", type="api",
                   url="https://example.com")
    db.add(case)
    db.commit()
    db.refresh(case)

    def boom(*args, **kwargs):
        raise RuntimeError("模拟执行器崩溃")

    monkeypatch.setattr("app.api.executions.execute_case", boom)

    # 这条路由在全站 guard 之下，单元测试不造 token，直接覆盖鉴权依赖
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        response = TestClient(app).post(f"/api/cases/{case.id}/run")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["end_time"] is not None

    # MySQL 默认 REPEATABLE READ：这里必须先结束旧事务，否则会读到写入之前的快照
    db.rollback()
    row = db.get(Execution, body["id"])
    assert row.status == "error"
    assert row.end_time is not None
    assert row.duration_ms is not None
    assert "模拟执行器崩溃" in row.result_json["error_msg"]


@requires_db
def test_reap_stale_executions_marks_old_running_as_error(db, project):
    from app.services.execution_reaper import reap_stale_executions

    stale = Execution(project_id=project.id, status="running",
                      start_time=datetime.now() - timedelta(hours=2))
    fresh = Execution(project_id=project.id, status="running", start_time=datetime.now())
    db.add_all([stale, fresh])
    db.commit()
    db.refresh(stale)
    db.refresh(fresh)

    count = reap_stale_executions()
    assert count >= 1

    # MySQL 默认 REPEATABLE READ：这里必须先结束旧事务，否则会读到写入之前的快照
    db.rollback()
    swept = db.get(Execution, stale.id)
    assert swept.status == "error"
    assert swept.end_time is not None
    assert "未完成" in swept.result_json["error_msg"]
    # 刚开始跑的不能被误伤
    assert db.get(Execution, fresh.id).status == "running"
