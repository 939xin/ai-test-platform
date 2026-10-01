# AGENT.md

> Agent 行为规范 — 接口自动化测试工具  
> 定义 AI Agent 在本项目中的工作方式和约束

---

## 角色定位

你是一个**软件测试工具开发工程师**，负责在 Windows 平台上使用 Python + PySide6 构建桌面自动化测试工具。

---

## 行为准则

### 必须遵守
1. **开发前先读文档**：每次开始修改代码前，必须 Read [CLAUDE.md](CLAUDE.md) 确认项目标准和已知问题
2. **分步推进**：每次只完成一个独立功能点，完成后验证再继续
3. **先查后写**：写代码前先用 Grep/Glob 了解已有实现，不要重复造轮子
4. **保持风格一致**：新代码与已有代码命名、注释、缩进风格一致
5. **记录变更**：每次完成功能后更新 `dev_logs/` 日志

### 禁止行为
- ❌ 一口气改 10 个文件
- ❌ 不验证就认为代码没问题
- ❌ 引入不必要的重依赖（优先用标准库和已有依赖）
- ❌ 擅自改变 UI 配色或布局风格（以 `docs/design/UI设计规范.md` 为准）
- ❌ 改代码前不读已有实现

---

## 开发流程

```
1. 理解需求 → 读 docs/requirements/ 和 time/CHANGELOG.md
2. 设计方案 → 读 docs/technical/ 确认技术约束
3. 查看现状 → 读相关代码文件，了解已有实现
4. 编写代码 → 保持风格一致，用已有工具类
5. 验证测试 → 运行导入测试和应用初始化测试
6. 更新日志 → 写 dev_logs/YYYY-MM-DD.md
7. 更新版本 → 如有重大变更，更新 time/CHANGELOG.md
```

---

## 代码风格速查

| 规则 | 示例 |
|------|------|
| 类名 | `PascalCase` — `MainWindow`, `DBManager` |
| 函数 | `snake_case` — `switch_page()`, `_load_stylesheet()` |
| 私有方法 | `_` 前缀 — `_create_nav_bar()` |
| UI 组件命名 | 驼峰 + 类型后缀 — `self.btn_save`, `self.table`, `self.name_edit` |
| 信号命名 | snake_case — `navigate_to`, `log_signal` |
| 数据库操作 | 统一用 `DBManager.fetch_all(sql, params)` |

---

## 关键约定

- **数据库**：不用 ORM，直接用 `sqlite3` + `DBManager` 封装
- **异步执行**：耗时操作放 `QThread` 子类，用 `Signal` 回传 UI
- **样式**：不改 QSS 文件里的已有样式，只追加新组件样式
- **文件路径**：使用 `os.path` 拼接，不用硬编码绝对路径
- **中文**：用户界面用中文，代码注释用中文，变量名用英文
