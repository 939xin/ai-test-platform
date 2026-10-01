"""
变量解析器 — 解析 ${变量名} 占位符
"""
import re
from app.database.models import DBManager


class VariableResolver:
    """解析字符串中的 ${变量名} 占位符"""

    VARIABLE_PATTERN = re.compile(r'\$\{(\w+)\}')

    def __init__(self, environment_id: int = None):
        self.environment_id = environment_id
        self._extra_vars: dict = {}  # 运行时提取的变量
        self._global_cache: dict = None

    def set_extra_var(self, name: str, value: str):
        """设置运行时变量（如步骤间提取的值）"""
        self._extra_vars[name] = value

    def _load_global_vars(self):
        """加载全局变量到缓存"""
        if self._global_cache is None:
            self._global_cache = {}
            vars_list = DBManager.fetch_all(
                "SELECT name, value FROM global_variables "
                "WHERE environment_id IS NULL OR environment_id = ?",
                (self.environment_id,) if self.environment_id else (None,)
            )
            for v in vars_list:
                self._global_cache[v['name']] = v['value']

    def resolve(self, text: str) -> str:
        """解析文本中的变量占位符"""
        if not text or '${' not in text:
            return text

        self._load_global_vars()

        def replacer(match):
            var_name = match.group(1)
            # 优先使用运行时变量（步骤间传递）
            if var_name in self._extra_vars:
                return self._extra_vars[var_name]
            # 其次使用全局变量
            if var_name in self._global_cache:
                return self._global_cache[var_name]
            # 未找到则保留原样
            return match.group(0)

        return self.VARIABLE_PATTERN.sub(replacer, text)

    def get_all_variables(self) -> dict:
        """获取所有可用变量（全局 + 运行时）"""
        self._load_global_vars()
        result = dict(self._global_cache)
        result.update(self._extra_vars)
        return result
