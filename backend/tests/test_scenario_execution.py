"""场景执行落 scenario_id、起止时间真实（P1-2）。"""
from datetime import datetime

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine
from app.models import Execution, Project, Scenario


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(
    not _db_available(), reason="需要 MySQL 开发库；纯函数用例不受影响"
)

if _db_available():
    # 存量库靠 _ADDED_COLUMNS 补列，这里先确保 scenario_id 列已就位（幂等）
    from app.database import ensure_schema

    ensure_schema()


# ---------- 纯函数层 ----------

def test_scenario_steps_carry_real_start_and_finish(monkeypatch):
    import app.services.scenario_runner as runner_module

    def fake_execute(case, env, timeout=30):
        return {"status": "pass", "duration_ms": 5, "extracted": {}, "request": {}, "response": {}}

    monkeypatch.setattr(runner_module, "execute_case", fake_execute)

    result = runner_module.run_scenario(
        [{"case_id": 1, "case_name": "a", "case": {"url": "x"}, "fail_strategy": "stop"}], {}
    )
    step = result["steps"][0]
    assert isinstance(step["started_at"], datetime)
    assert isinstance(step["finished_at"], datetime)
    assert step["finished_at"] >= step["started_at"]


# ---------- 落库与筛选 ----------

@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@requires_db
def test_execution_keeps_scenario_id_and_list_filters_by_it(db):
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.main import app

    project = Project(name="[单元测试] 场景执行")
    db.add(project)
    db.commit()
    db.refresh(project)
    scenario = Scenario(project_id=project.id, name="[单元测试] 场景")
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    started = datetime(2026, 10, 22, 10, 0, 0)
    execution = Execution(
        project_id=project.id,
        scenario_id=scenario.id,
        status="pass",
        start_time=started,
        end_time=datetime(2026, 10, 22, 10, 0, 1),
        duration_ms=1000,
        result_json={},
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    try:
        app.dependency_overrides[get_current_user] = lambda: None
        try:
            client = TestClient(app)
            page = client.get(f"/api/executions?scenario_id={scenario.id}").json()
            other = client.get(f"/api/executions?scenario_id={scenario.id + 999999}").json()
            detail = client.get(f"/api/executions/{execution.id}").json()
        finally:
            app.dependency_overrides.clear()

        assert page["total"] >= 1
        assert all(item["scenario_id"] == scenario.id for item in page["items"])
        assert other["total"] == 0
        assert detail["scenario_id"] == scenario.id
        # 起止时间按落库的真实值返回，不再是「同一刻」
        assert detail["end_time"] > detail["start_time"]
    finally:
        db.rollback()
        db.delete(db.get(Project, project.id))
        db.commit()
