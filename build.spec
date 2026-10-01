# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件
用法: pyinstaller build.spec
"""

import sys
import os
from pathlib import Path

# 自动发现 PySide6 路径
import PySide6
pyside6_path = os.path.dirname(PySide6.__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Qt 样式表
        ('app/ui/styles/blue_theme.qss', 'app/ui/styles'),
        # PySide6 依赖的 Qt 插件和翻译
        (os.path.join(pyside6_path, 'plugins'), 'PySide6/plugins'),
        (os.path.join(pyside6_path, 'translations'), 'PySide6/translations'),
    ],
    hiddenimports=[
        # PySide6 相关
        'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets',
        'PySide6.QtNetwork', 'PySide6.QtPrintSupport',
        # Selenium 相关
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.edge.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        # webdriver-manager 相关
        'webdriver_manager.chrome',
        'webdriver_manager.microsoft',
        'webdriver_manager.core',
        'webdriver_manager.driver',
        # jsonpath-ng
        'jsonpath_ng',
        'jsonpath_ng.ext',
        # 标准库补充
        'sqlite3', 'json', 'tempfile', 'subprocess',
        'urllib3', 'certifi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas',
        'PIL', 'cv2', 'scipy',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

# 单文件打包
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='接口自动化测试工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 可后续添加 .ico 图标
    uac_admin=False,
)
