"""浏览器并发闸门（P1-1）：配额、超时、释放、重入。"""
import app.services.web_executor as web_executor


def _reset(monkeypatch, size: int):
    monkeypatch.setattr(web_executor, "_slot_sem", None)
    monkeypatch.setattr(web_executor, "_slot_size", 0)
    monkeypatch.setattr(web_executor, "_active_browsers", 0)
    monkeypatch.setattr(web_executor.settings, "web_max_concurrent_sessions", size)


def test_second_acquire_times_out_when_full(monkeypatch):
    _reset(monkeypatch, 1)

    assert web_executor.acquire_browser_slot(0) is True
    assert web_executor.browser_slot_status() == {"active_sessions": 1, "max_sessions": 1}
    # 等不到配额要返回 False，调用方据此产出 error 结果，而不是无限阻塞
    assert web_executor.acquire_browser_slot(0.05) is False


def test_release_frees_the_slot(monkeypatch):
    _reset(monkeypatch, 1)

    assert web_executor.acquire_browser_slot(0) is True
    web_executor.release_browser_slot()
    assert web_executor.browser_slot_status()["active_sessions"] == 0
    assert web_executor.acquire_browser_slot(0) is True
    web_executor.release_browser_slot()


def test_double_release_does_not_corrupt_counter(monkeypatch):
    """异常路径多释放一次不能把并发数变成负数，也不能因此中断执行。"""
    _reset(monkeypatch, 1)

    assert web_executor.acquire_browser_slot(0) is True
    web_executor.release_browser_slot()
    web_executor.release_browser_slot()  # 多余的一次被吞掉
    assert web_executor.browser_slot_status()["active_sessions"] == 0


def test_two_slots_are_independent(monkeypatch):
    _reset(monkeypatch, 2)

    assert web_executor.acquire_browser_slot(0) is True
    assert web_executor.acquire_browser_slot(0) is True
    assert web_executor.acquire_browser_slot(0.05) is False
    assert web_executor.browser_slot_status() == {"active_sessions": 2, "max_sessions": 2}
    web_executor.release_browser_slot()
    web_executor.release_browser_slot()


def test_web_status_exposes_slot_fields(monkeypatch):
    """前端靠这两个字段决定要不要禁用执行按钮。"""
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: None
    try:
        body = TestClient(app).get("/api/web/status").json()
    finally:
        app.dependency_overrides.clear()

    assert "active_sessions" in body
    assert "max_sessions" in body
    assert isinstance(body["active_sessions"], int)
