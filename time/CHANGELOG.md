# 版本功能清单

> 项目：接口自动化测试工具  
> 用途：记录每个版本的功能点，方便版本回溯

---

## v1.0.0 (2026-06-27) — 基础框架 + 全功能 MVP

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

## 待规划版本

### v1.1.0（计划中）
- 批量执行（勾选多条用例一次执行）
- Setup/Teardown（前置步骤 + 后置步骤）
- 用例导入/导出（JSON 格式）

### v1.2.0（计划中）
- 数据驱动测试（CSV/Excel 参数化）
- 定时任务
- 接口用例并发执行
