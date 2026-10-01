# 接口自动化测试工具

> 一站式桌面自动化测试平台 — 接口测试 + Web UI 测试 | PySide6 · pytest · Selenium

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://python.org)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-1976D2)](https://doc.qt.io/qtforpython/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 截图

<!-- 放 2-3 张截图：首页 + 接口测试执行 + 报告 -->

---

## 特性

- **双引擎架构** — 接口测试（pytest + requests）和 Web UI 测试（Selenium）共享同一平台
- **多环境管理** — 支持 dev/test/staging/prod 多环境，Base URL 动态切换
- **完整断言体系** — 状态码断言、JSONPath 响应体断言、响应时间断言
- **15 种 Web 操作** — 点击/输入/等待/截图/断言/IFrame 切换/JS 执行/变量提取
- **调试模式** — 执行时打开浏览器窗口，用户亲眼看到每一步操作
- **失败自动截图** — 断言失败或异常时自动保存截图并嵌入报告
- **HTML 测试报告** — 概览看板 + 请求/响应全量追溯 + 期望值 vs 实际值对比
- **PDF 导出** — Chrome CDP 生成 PDF 报告
- **数据持久化** — SQLite 本地存储，下次打开用例还在
- **绿色免安装** — PyInstaller 单 .exe 分发，解压即用

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/yourname/api-test-tool
cd api-test-tool

# 2. 安装
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 预填测试数据
python tests\seed_test_data.py

# 4. 启动
python main.py
```

---

## 技术栈

| 层 | 技术 |
|---|---|
| 桌面框架 | PySide6 (Qt for Python) |
| 接口测试 | pytest + requests + jsonpath-ng |
| Web 测试 | Selenium WebDriver |
| 数据库 | SQLite + WAL 模式 |
| 报告 | Jinja2 + 自研 HTML 模板 |
| PDF 导出 | Chrome CDP Page.printToPDF |
| 打包 | PyInstaller |

---

## 项目结构

```
├── main.py                  # 应用入口
├── app/
│   ├── database/            # 数据层 (10张表)
│   ├── ui/                  # 界面层 (5页 + 4组件)
│   ├── engine/              # 引擎层 (接口/Web/脚本/报告)
│   └── utils/               # 工具层 (浏览器/变量)
├── tests/                   # 95项自动化验证
├── docs/                    # 完整开发文档
├── reports/                 # HTML报告输出
└── scripts/                 # 导出脚本 + 打包
```

---

## 架构

```
┌─────────────────────────────────────────┐
│            UI 层 (PySide6)              │
│  首页 → 接口测试 → Web测试 → 报告 → 设置 │
└──────────────┬──────────────────────────┘
               │ Signal/Slot
┌──────────────▼──────────────────────────┐
│         引擎层 (QThread)                │
│  APIRunner / WebRunner / ReportGenerator│
└──────────────┬──────────────────────────┘
               │ DBManager
┌──────────────▼──────────────────────────┐
│        数据层 (SQLite + WAL)            │
│  10张表 / 外键约束 / 事务保护           │
└─────────────────────────────────────────┘
```

---

## 验证

```bash
python tests/test_comprehensive.py
# 95 items passed, 0 failed (100%)
```

---

## 简历加分项

如果你也是测试开发方向，这个项目可以写到简历上的亮点：

1. **从零搭建完整桌面应用** — 需求分析 → 架构设计 → 编码 → 测试 → 打包
2. **解决实际工程问题** — QThread 跨线程请求异常、QSS Qt6 兼容性、pytest 子进程数据丢失
3. **质量意识** — 95 项自动化验证用例、WAL 模式、事务保护、异常兜底
4. **完整的技术栈覆盖** — PySide6 + pytest + Selenium + SQLite + Jinja2 + PyInstaller

---

## 许可证

MIT License
