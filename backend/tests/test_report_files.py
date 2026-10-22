"""报告按项目归属 + 删项目清磁盘（P1-3）。"""
from pathlib import Path

import pytest
from sqlalchemy import text

from app.api.reports import _project_id_of
from app.config import settings
from app.database import SessionLocal, engine
from app.models import Execution, Project


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="需要 MySQL 开发库")


# ---------- 纯函数 ----------

def test_project_id_parsed_from_new_filename():
    assert _project_id_of("report_api_p29_r318_20261022_101500.html") == 29


def test_project_id_parsed_with_random_suffix():
    """P1-8 之后文件名末尾多了 8 位随机段，前缀解析不能受影响。"""
    assert _project_id_of("report_api_p29_r318_20261022_101500_9f3a1c2b.html") == 29


def test_random_suffix_pattern():
    import re

    # 与 build_report 里的 secrets.token_hex(4) 对应：8 位十六进制、位于 .html 之前
    assert re.fullmatch(r"report_api_p29_r318_\d{8}_\d{6}_[0-9a-f]{8}\.html",
                        "report_api_p29_r318_20261022_101500_9f3a1c2b.html")


def test_project_id_none_for_old_filename():
    assert _project_id_of("report_api_r318_20261003_101500.html") is None


def test_project_id_none_for_unrelated_filename():
    assert _project_id_of("weird name.html") is None


# ---------- 落库 + 磁盘 ----------

@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@requires_db
def test_report_filename_carries_project_id(db):
    from app.services.report_generator import build_report

    project = Project(name="[单元测试] 报告归属")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(project_id=project.id, status="pass", duration_ms=1, result_json={})
    db.add(execution)
    db.commit()
    db.refresh(execution)

    info = build_report(db, [execution.id], test_type="api")
    second = build_report(db, [execution.id], test_type="api")
    try:
        assert f"_p{project.id}_" in info["filename"]
        assert _project_id_of(info["filename"]) == project.id
        # 同一秒内连生两份：随机段保证文件名不同（撞名序号只是兜底）
        assert info["filename"] != second["filename"]
        stem = info["filename"].removesuffix(".html")
        assert len(stem.rsplit("_", 1)[1]) == 8
    finally:
        Path(second["path"]).unlink(missing_ok=True)
        Path(info["path"]).unlink(missing_ok=True)
        db.rollback()
        db.delete(db.get(Project, project.id))
        db.commit()


@requires_db
def test_delete_project_removes_its_files_only(db):
    """删项目清报告 / 截图 / 数据集，但不碰别的项目的文件。"""
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.main import app

    project = Project(name="[单元测试] 删项目清理")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(project_id=project.id, status="pass", duration_ms=1, result_json={})
    db.add(execution)
    db.commit()
    db.refresh(execution)
    project_id, execution_id = project.id, execution.id

    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    own_report = report_dir / f"report_api_p{project_id}_r{execution_id}_20260101_000000.html"
    other_report = report_dir / f"report_api_p{project_id + 100000}_r1_20260101_000000.html"
    own_report.write_text("<html>own</html>", encoding="utf-8")
    other_report.write_text("<html>other</html>", encoding="utf-8")

    shots_root = report_dir / "screenshots"
    own_shots = shots_root / f"execution_{execution_id}"
    other_shots = shots_root / f"execution_{execution_id + 100000}"
    own_shots.mkdir(parents=True, exist_ok=True)
    other_shots.mkdir(parents=True, exist_ok=True)
    (own_shots / "step.png").write_bytes(b"png")

    dataset_dir = Path(settings.dataset_dir) / str(project_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    try:
        app.dependency_overrides[get_current_user] = lambda: None
        try:
            response = TestClient(app).delete(f"/api/projects/{project_id}")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 204
        assert not own_report.exists()
        assert not own_shots.exists()
        assert not dataset_dir.exists()
        # 别的项目/执行的文件必须还在
        assert other_report.exists()
        assert other_shots.exists()
    finally:
        db.rollback()
        row = db.get(Project, project_id)
        if row is not None:
            db.delete(row)
            db.commit()
        other_report.unlink(missing_ok=True)
        import shutil

        shutil.rmtree(other_shots, ignore_errors=True)
