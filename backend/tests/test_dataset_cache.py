"""数据集元信息缓存（P1-5）：文件没变就不重复解析。"""
import app.services.dataset as dataset


def _write(path, rows: int):
    lines = "name,age\n" + "".join(f"u{i},{20 + i}\n" for i in range(rows))
    path.write_text(lines, encoding="utf-8")


def test_describe_reuses_cache_until_file_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset.settings, "dataset_dir", str(tmp_path))
    project_dir = tmp_path / "999999"
    project_dir.mkdir()
    data = project_dir / "cache_test.csv"
    _write(data, 2)

    calls = []
    original = dataset._load_csv

    def counting(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(dataset, "_load_csv", counting)

    first = dataset.describe(999999, "cache_test.csv")
    second = dataset.describe(999999, "cache_test.csv")
    assert first == second
    assert first["rows"] == 2
    assert first["columns"] == ["name", "age"]
    # 第二次没有再解析文件
    assert len(calls) == 1

    # 文件变了（行数与大小都变）→ 必须重新解析
    _write(data, 3)
    third = dataset.describe(999999, "cache_test.csv")
    assert third["rows"] == 3
    assert len(calls) == 2


def test_invalidate_forces_reparse(tmp_path, monkeypatch):
    monkeypatch.setattr(dataset.settings, "dataset_dir", str(tmp_path))
    project_dir = tmp_path / "999998"
    project_dir.mkdir()
    data = project_dir / "invalidate_test.csv"
    _write(data, 2)

    calls = []
    original = dataset._load_csv

    def counting(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(dataset, "_load_csv", counting)

    dataset.describe(999998, "invalidate_test.csv")
    dataset.invalidate(999998, "invalidate_test.csv")
    dataset.describe(999998, "invalidate_test.csv")
    assert len(calls) == 2


def test_missing_file_raises_file_not_found(tmp_path, monkeypatch):
    """列表接口依赖这个异常类型来决定「记 0 行」而不是整个 500。"""
    monkeypatch.setattr(dataset.settings, "dataset_dir", str(tmp_path))
    (tmp_path / "999997").mkdir()

    try:
        dataset.describe(999997, "nope.csv")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("文件不存在时应抛 FileNotFoundError")
