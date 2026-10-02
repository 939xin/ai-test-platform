"""数据驱动 —— 读取 CSV / Excel 参数化文件。

用例挂一个数据文件后按行执行：每行的「列名 → 值」作为运行时变量注入，
用例里用 ${列名} 引用（优先级高于全局变量）。

CSV 用 utf-8-sig 读（Excel「另存为 CSV」会带 BOM，不处理的话第一个列名会多出 \\ufeff）；
Excel 用 openpyxl 只读模式，首行当表头。
"""
import csv
from pathlib import Path

from openpyxl import load_workbook

from app.config import settings

CSV_SUFFIXES = {".csv"}
EXCEL_SUFFIXES = {".xlsx", ".xlsm"}
ALLOWED_SUFFIXES = CSV_SUFFIXES | EXCEL_SUFFIXES


def dataset_dir(project_id: int) -> Path:
    path = Path(settings.dataset_dir) / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_path(project_id: int, filename: str) -> Path:
    """把文件名解析成数据目录下的路径，挡住 ../ 之类的越界访问与非法后缀。"""
    name = (filename or "").strip()
    if not name or Path(name).name != name or "/" in name or "\\" in name:
        raise ValueError("非法的文件名")
    if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("只支持 .csv / .xlsx 文件")
    return dataset_dir(project_id) / name


def _clean(value) -> str:
    return "" if value is None else str(value).strip()


def _load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return []
        columns = [(c or "").strip() for c in reader.fieldnames]
        rows = []
        for raw in reader:
            # DictReader 的 key 是原始表头，这里按位置取值，避免表头带空格时对不上
            values = list(raw.values())
            rows.append({columns[i]: _clean(values[i]) for i in range(len(columns)) if columns[i]})
        return rows


def _load_excel(path: Path) -> list[dict]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook.active
        iterator = sheet.iter_rows(values_only=True)
        header = next(iterator, None)
        if not header:
            return []
        columns = [_clean(c) for c in header]
        rows = []
        for raw in iterator:
            values = list(raw)
            rows.append({columns[i]: _clean(values[i]) for i in range(len(columns)) if columns[i]})
        return rows
    finally:
        workbook.close()


def load_rows(project_id: int, filename: str) -> list[dict]:
    """读出一个数据文件的全部数据行，返回 [{列名: 值}]。

    全空行会被丢掉（Excel 里很容易留下尾部空行）。文件不存在抛 FileNotFoundError，
    格式非法抛 ValueError —— 都由调用方转成 HTTP 400。
    """
    path = resolve_path(project_id, filename)
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在：{filename}")

    try:
        rows = _load_csv(path) if path.suffix.lower() in CSV_SUFFIXES else _load_excel(path)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"解析失败：{type(e).__name__}: {str(e)[:120]}") from e

    return [r for r in rows if any(v for v in r.values())]


def describe(project_id: int, filename: str) -> dict:
    """给列表/预览用的元信息。"""
    path = resolve_path(project_id, filename)
    rows = load_rows(project_id, filename)
    columns: list[str] = []
    for r in rows:
        for key in r:
            if key not in columns:
                columns.append(key)
    return {
        "filename": path.name,
        "size": path.stat().st_size,
        "rows": len(rows),
        "columns": columns,
    }
