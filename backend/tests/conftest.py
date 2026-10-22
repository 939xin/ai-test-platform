"""单元测试公共夹具。

这里的测试刻意不连 MySQL、不起浏览器、不启动服务：
它们要在任何一台机器上一条命令跑完，作为改完代码的第一道闸。
"""
import sys
from pathlib import Path

# pytest.ini 已经声明了 pythonpath = .，这里再补一次是为了
# 直接 `python -m pytest tests/xxx.py` 或从别的目录调用时也能 import app。
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
