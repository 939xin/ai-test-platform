"""变量解析器 — 解析 ${变量名} 占位符。

搬自旧 PySide6 项目的 app/utils/variable_resolver.py。
唯一改动：全局变量由构造参数注入，不再直接查 SQLite（原实现走 DBManager）。
"""
import re


class VariableResolver:
    """解析字符串中的 ${变量名} 占位符。

    优先级：运行时变量（步骤间提取）> 全局变量 > 原样保留。
    """

    VARIABLE_PATTERN = re.compile(r"\$\{(\w+)\}")

    def __init__(self, global_vars: dict | None = None):
        self._extra_vars: dict = {}
        self._global_cache: dict = dict(global_vars or {})

    def set_extra_var(self, name: str, value: str) -> None:
        """设置运行时变量（如步骤间提取的 token）。"""
        self._extra_vars[name] = value

    def resolve(self, text: str) -> str:
        """解析文本中的变量占位符；未命中的保持原样。"""
        if not text or "${" not in text:
            return text

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            if var_name in self._extra_vars:
                return str(self._extra_vars[var_name])
            if var_name in self._global_cache:
                return str(self._global_cache[var_name])
            return match.group(0)

        return self.VARIABLE_PATTERN.sub(replacer, text)

    def get_all_variables(self) -> dict:
        """获取所有可用变量（全局 + 运行时，运行时优先）。"""
        result = dict(self._global_cache)
        result.update(self._extra_vars)
        return result
