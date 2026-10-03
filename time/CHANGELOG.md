# 版本功能清单

> 项目：鑫测试平台  
> 用途：记录每个版本的功能点，方便版本回溯
>
> 本仓库有两套代码：**v2.x 是当前在做的 Web 平台**（`backend/` + `frontend/`），
> **v1.0.0 是已冻结的 PySide6 桌面版**（`app/`），作为执行引擎的复用源保留。

---

## v2.0.0 (2026-10-02) — Web 平台 MVP ★当前版本

> 从 PySide6 桌面版重做为 Web 平台：Vue3 + Element Plus / FastAPI + MySQL。
> 按 Day 1–6 推进，每日的取舍与踩坑见 `dev_logs/`。

### Day 1 · 工程骨架
- [x] Docker MySQL 8（宿主映射 3307，避开本机 3306）
- [x] FastAPI + SQLAlchemy 2.0 骨架、10 张表 ORM、`GET /api/health`
- [x] bcrypt + JWT 登录（默认账号 `admin` / `admin123`）
- [x] 执行引擎复用：`variable_resolver` / `assertion_engine` / `api_executor`
- [x] Vue3 + Element Plus 前端骨架、设计令牌、AppLayout、路由与 axios 封装

### Day 2 · 核心 CRUD 与接口执行闭环
- [x] 项目 / 环境 / 用例三套 CRUD（含全局变量行编辑）
- [x] 接口执行闭环：建项目 → 建环境 → 建用例 → 执行 → 看结果
- [x] 一键验收脚本 `backend/scripts/verify_all.py`

### Day 3 · 执行中心 / 报告 / 用例串联
- [x] 执行中心页（项目与状态筛选、统计卡片、详情抽屉）
- [x] 测试报告 HTML 生成（与旧桌面版输出物理隔离到 `reports/platform/`）
- [x] 变量提取 `extract_json`、场景串联（`scenario` / `scenario_step`）
- [x] 数据驱动（CSV / Excel 参数化，按行执行）

### Day 4 · Web UI 执行
- [x] Selenium 执行层迁入服务化（`browser_manager` / `web_executor`）
- [x] Web 步骤编排器 + 执行闭环 + 失败自动截图
- [x] **修掉旧桌面版 `_capture_screenshot()` 从未生效的老 bug**
      （`self.screenshots` 未初始化，异常被 `except Exception: pass` 吞掉）
- [x] 一键启停 `start.bat` / `stop.bat`

### Day 5 · 测试计划
- [x] 测试计划：一组用例 + 一个环境，一键批量执行并汇总
- [x] `test_plan.case_ids_json`（无外键的 JSON 数组）改关联表 `test_plan_case`，
      删用例时关联级联清理

### Day 6 · 用例拆分 / 操作补全 / 视觉改版
- [x] 用例按类型拆成「接口测试」+「UI 测试」两条独立线路：
      各自菜单、列表与**全屏编辑页**，编辑器不再有类型下拉
- [x] Web 步骤操作 **15 → 31 种**，按导航/鼠标/表单/弹窗/等待/滚动/断言/其他分 8 组；
      字段规格（`ACTION_SPEC`）由后端声明并下发，前端照着渲染
- [x] 新增操作补齐了旧版做不了的场景：下拉框选择（原生 select 点不开）、
      上传文件、键盘按键、悬停、拖拽、弹窗处理（alert/confirm/prompt）、
      等待元素消失、刷新/后退、滚动到底部、断言 URL/数量/属性
- [x] 步骤编排交互重做：分组添加面板、**拖拽排序**（补回旧桌面版有、新版丢掉的能力）、
      折叠、复制、校验失败高亮到具体步骤
- [x] **修掉「弹窗确认 / 取消」永远不生效的 bug** —— Selenium 4 默认
      `unhandledPromptBehavior=dismiss`，会在点击后那段 execute_script 撞上弹窗时
      把它自动关掉，且不报错
- [x] 视觉改版：现代 SaaS 卡片化（品牌青蓝侧栏、三段式列表页、统计卡重做）

### Day 7 · 缺陷管理
- [x] 缺陷 CRUD（`schemas/defect.py` + `api/defects.py`），状态流转
      新建 → 处理中 → 已修复 → 已关闭 → 重新打开
- [x] 严重程度 / 优先级 / 状态三组枚举用 `Literal` 约束，非法值直接 422
- [x] **一键提缺陷**：从失败 / 错误的执行记录自动生成标题（`[fail] 用例名`）
      与描述（执行状态、耗时、未通过的断言 / 步骤），并关联 `execution_id` / `case_id`
- [x] 同一条执行重复提缺陷返回 409，`detail` 带上已有缺陷 id，前端提示并跳转，
      不产生重复数据
- [x] 缺陷列表页（三段式 + 状态 / 严重程度 / 标题关键字筛选）与编辑抽屉
- [x] 执行 ↔ 缺陷双向跳转：`/defects?open=&project=`、`/executions?open=`
- [x] **修掉统一报错只认字符串 `detail` 的 bug** —— FastAPI 的 422 返回数组、
      409 返回对象，原来都会被渲染成 `[object Object]`（422 那条是旧有隐患）

### 验收规模

| 阶段 | 验收项数 |
|---|---|
| Day 2 | 23 |
| Day 3 | 62 |
| Day 4 | 82 |
| Day 5 | 98 |
| Day 6 | 122 |
| Day 7 | **144（全过）** |

### 已知未做（v2.0.0 范围内）

- [ ] 全站接口未校验 JWT（登录能签发，后端没有一处 `Depends`）
- [ ] AI 助手 / 设置两个页面仍是占位
- [ ] 列表没有分页（接口一次性返回全部，8 个列表页都是）
- [ ] Web 用例不支持场景串联与数据驱动
- [ ] 缺陷无附件 / 评论 / 指派（表里没有这些字段，要做先改表）

---

## v1.0.0 (2026-06-27) — 桌面版：基础框架 + 全功能 MVP ⏸已冻结

> PySide6 桌面应用，功能已冻结，源码保留作为执行引擎的复用来源。

### Phase 1: 基础框架
- [x] 项目目录结构搭建
- [x] SQLite 数据库模型定义和初始化
- [x] PySide6 主窗口 + 顶部导航栏
- [x] 首页双入口卡片（接口测试 / Web 测试）
- [x] 蓝色主题 QSS 样式表
- [x] 各页面占位（接口测试、Web 测试、报告、设置）
- [x] 应用能正常启动并切换页面 ✅ 已通过全量验证

### Phase 2: 接口自动化测试
- [x] 环境管理 CRUD（settings_page.py 中实现）
- [x] 接口测试用例列表（表格）
- [x] 接口用例编辑器（弹窗）：URL/方法/Headers/Body/认证/断言
- [x] 接口测试执行引擎（APIRunner - QThread + pytest）
- [x] pytest 脚本生成器（ScriptGenerator）
- [ ] 验证：创建用例 → 执行 → 查看结果 → 导出脚本

### Phase 3: Web 自动化测试
- [x] Web 测试用例列表（表格）
- [x] 步骤编排器（StepEditorDialog - 表格 + 菜单添加）
- [x] 15 种操作类型支持
- [x] 8 种定位方式支持
- [x] Web 测试执行引擎（WebRunner - Selenium + QThread）
- [x] 浏览器驱动管理器（BrowserManager）
- [x] 调试模式 / 无头模式
- [x] 截图机制（失败自动 + 手动）
- [x] 变量传递（提取变量 + ${变量名} 引用）
- [ ] 验证：创建 Web 用例 → 编排步骤 → 执行 → 查看截图

### Phase 4: 测试报告
- [x] HTML 报告生成器（ReportGenerator - 五模块）
- [x] 报告查看器（report_viewer.py - 历史结果列表 + 统计看板）
- [x] 截图 Base64 嵌入 HTML（点击放大）
- [x] PDF 导出功能（Chrome CDP Page.printToPDF）
- [x] 报告文件命名关联 result_id（方便查找）
- [ ] 验证：实际浏览器中打开报告查看效果

### Phase 5: 收尾与打包
- [x] 设置页完善（环境管理 + 全局变量 + 浏览器驱动配置）
- [x] 结果历史查看功能
- [x] PyInstaller 打包配置（build.spec）
- [x] 环境初始化脚本（setup.bat）
- [x] 构建脚本（build.bat）
- [ ] 完整 PyInstaller 打包测试（需 Windows 桌面）

---

## 待规划

> 桌面版已冻结，下列计划项不再针对它。沿用下来的逐条标注去向，避免看着像还没做。

### 新平台待做

- [ ] 缺陷管理（表已建，缺 schema / api / 前端）
- [ ] AI 助手（DeepSeek 接入：用例生成 / 失败分析）
- [ ] 设置页
- [ ] 列表分页（接口目前一次性返回全部）
- [ ] 全站接口校验 JWT
- [ ] Web 用例支持场景串联与数据驱动
- [ ] Setup/Teardown（前置步骤 + 后置步骤）—— 沿自桌面版计划，两版都未做
- [ ] 定时执行 —— `test_plan.schedule` 字段已在 Day 5 删除，要做需引入常驻调度器，是独立工程
- [ ] 前后端一起 Docker 化（目前只有数据库跑了 compose）

### 桌面版计划项的去向

| 原计划项 | 去向 |
|---|---|
| 批量执行（勾选多条用例一次执行） | ✅ 新平台已做 —— 测试计划（Day 5） |
| 数据驱动测试（CSV / Excel 参数化） | ✅ 新平台已做（Day 3） |
| 用例导入 / 导出（JSON） | 📋 新平台未做，如需可补 |
| 接口用例并发执行 | 📋 新平台未做（当前串行） |
| PyInstaller 打包测试 | ⏸ 随桌面版冻结作废 |
