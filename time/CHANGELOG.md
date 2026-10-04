# 版本功能清单

> 项目：鑫测试平台  
> 用途：记录每个版本的功能点，方便版本回溯
>
> 本仓库有两套代码：**v2.x 是当前在做的 Web 平台**（`backend/` + `frontend/`），
> **v1.0.0 是已冻结的 PySide6 桌面版**（`app/`），作为执行引擎的复用源保留。

---

## v2.0.0 (2026-10-02) — Web 平台 MVP ★当前版本

> 从 PySide6 桌面版重做为 Web 平台：Vue3 + Element Plus / FastAPI + MySQL。
> 按 Day 1–11 推进，每日的取舍与踩坑见 `dev_logs/`。

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

### Day 8 · 全站 JWT 校验
- [x] `api/deps.py` 的 `get_current_user`：验签 + 确认 `sub` 用户还在，
      没带 token / 伪造 / 过期 / 用户已删 一律 401（带 `WWW-Authenticate: Bearer`）
- [x] 守卫**不挂在各路由函数上**，集中在 `main.py` 的
      `include_router(..., dependencies=guard)` —— 11 个路由模块一行未改
- [x] 四类豁免：`/api/auth/login`、`/api/health`、`/api/demo/*`，
      以及报告 HTML 与截图（拆到 `reports.public_router`）
- [x] **前端补齐登录态**（此前前端**完全没有登录页**，只加后端校验会把整个 UI 打死）：
      `views/LoginView.vue` 登录页、`router` 双向守卫（未登录踢回登录页并带 `redirect`）、
      `AppLayout` 顶栏显示用户名 + 退出登录
- [x] `request.js` 401 拦截：清登录态 → 提示 → 整页跳登录页。
      多个并发 401 只提示一次、只跳一次；登录接口自身的 401（密码错）不按会话过期处理
- [x] `api/session.js` 单独一层存放登录态，避开 `auth ↔ request` 循环引用
- [x] `verify_all.py` 的 104 处裸调改走带 token 的 `requests.Session()`，
      并补 4 项边界断言（无 token 401 / 伪造 token 401 / 健康检查免鉴权 / 带 token 正常）
- [x] **修掉会话过期提示看不见的问题** —— 原来 `ElMessage.warning` 之后立刻整页跳转，
      页面先卸载，提示根本来不及渲染

### Day 9 · 列表分页
- [x] **6 个会长的列表接口改为分页**，返回 `{ items, total }`：
      用例 / 执行 / 缺陷 / 计划 / 场景 / 报告。统一走 `limit` + `offset`
      （不用 `page` / `page_size`，因为 `executions` 接口本来就带 `limit`，不引入第二套风格）
- [x] `schemas/common.py` 的 `Page[T]` 泛型信封 + `api/pagination.py` 的
      `PageParams` / `paginate()` 共用于 6 个接口
- [x] `total` 单独 count 一遍（不是 `len(rows)`）；越界参数（`limit=0` / `limit>200` /
      `offset<0`）一律 422
- [x] **项目 / 环境 / 数据集三个接口刻意保持裸数组** —— 它们同时是下拉数据源
      （8 / 4 / 1 处），分页会让选择器**静默只显示头一页的选项**。
      这条不对称契约写进 `CLAUDE.md` 并用断言钉住
- [x] 新增 `GET /executions/stats`（**必须声明在 `/executions/{id}` 之前**，
      否则 `stats` 会被当成执行 id 解析成整数 → 422）
- [x] 执行中心统计卡改走该接口，与列表**共用同一个筛选函数**；
      原来是对当前页 reduce，分页后会「翻一页数字就变」
- [x] `components/PagePagination.vue` 统一分页条：不走 `v-model` 只发
      `change({ page, pageSize })`（改每页条数必须连带重置页码），
      并加 `hide-on-single-page` 让条目少的页面保持原样
- [x] 6 个列表页接入分页；「共 N 条」改读后端 `total`（原为本页 `length`）；
      筛选 / 换项目回第 1 页；删除本页最后一条自动退一页
- [x] **修掉计划编辑器会静默丢用例的隐患** —— 提交时原来拿「已加载的」用例列表
      过滤勾选集，选择器限额 200 条，用例更多的计划一保存就少一批
- [x] 计划 / 场景的用例选择器显式取 200 条，超出时**在界面上明说**只列出前 200 条
- [x] **修掉报告文件名同一秒会互相覆盖** —— 连发 20 次生成请求返回同一个文件名，
      磁盘上只剩 1 份。改用 `open(path, "x")` 独占创建占坑，撞名加序号
- [x] **修掉列表页挂载时重复请求一次** —— `watch(currentProjectId)` 会在给
      select 赋初值时也触发，叠上 `onMounted` 的显式查询就是两遍。
      7 个页面改用 el-select 的 `@change`（只响应用户选择）
- [x] `verify_all.py` 新增 16 项分页与报告断言，并让收尾清理覆盖新产出的报告文件

### Day 10 · AI 辅助（DeepSeek）
- [x] `services/ai_client.py`：DeepSeek 客户端。**超时 60 秒**（整批用例生成偶尔要几十秒），
      网络类失败（超时 / 限流 / 5xx）**自动重试 1 次**；401/402/400 这类配置问题不重试，
      重试一次还是同样的错，只会让用户白等
- [x] **JSON 三层兜底**：直接 `json.loads` → 剥 ``` 代码围栏 → 正则取最外层 `{...}` / `[...]`。
      三层都不成就**重新调一次模型**（提示词末尾补「只输出 JSON」），
      而不是把同一段文本再解析一遍 —— 后者重试一百次也解析不出来。仍失败才报中文错误
- [x] `services/ai_prompts.py`：提示词写成后端常量。断言规则**显式列出引擎实现的那几组**
      （`status_code` / `response_time` / `response_body` 各自的 operator），
      否则模型会编出引擎跑不通的断言
- [x] `POST /api/ai/generate-cases`、`POST /api/ai/analyze-failure`；
      每次调用（含失败）落一条 `ai_task`（type / input / output / status），
      失败时 output 存模型原始返回，线上排查才看得到模型到底回了什么
- [x] **单条用例不合规就跳过、不连累整批**，少了几条在返回的 message 里明说
- [x] 失败分析入参只有 `execution_id`，上下文由后端查执行记录自己拼（响应体截断到 2000 字符）
- [x] AI 助手页：两个 Tab（用例生成 / 失败分析），生成结果表格预览 + 勾选保存，
      失败分析弹窗展示「可能原因 / 排查步骤 / 修复建议」
- [x] 用例编辑页加「AI 生成用例」（仅接口用例）；执行详情加「AI 分析失败」
- [x] `ExecutionBrief` / `ExecutionOut` 新增 `case_type`（api / web）——
      **执行表里没有类型字段**，由接口按 `case_id` 回查填充。
      前端靠它把「AI 分析失败」限制在接口执行上：Web 执行的 `result_json` 里是 steps，
      没有 request/response，喂给模型只能得到「记录里没有请求响应」这种空话
- [x] `verify_all.py` 新增 7 项 AI 边界断言（**离线**，换掉 `httpx.post`，不真的调 DeepSeek）：
      无 key → 400 / 返回非 JSON → 真的重调一次且补了提示词 / 超时 → 重试 1 次 /
      两个接口受 JWT 保护（无 token → 401）/ 两个路由已注册

### Day 11 · 设置页
- [x] `POST /api/auth/password` 修改当前用户密码。要旧密码是为了挡住
      「token 被人捡走就能直接改密码」；改完**不吊销已签发的 token** ——
      把正在干活的人踢下线比留个旧 token 更糟，旧 token 到期自然失效
- [x] ⚠️ `auth.router` 在 main.py 里是**没挂 guard** 的（它对全站豁免，因为
      `/login` 必须免登录）。所以这条新路由**自己声明**了 `get_current_user`，
      否则就是裸奔的 —— 验收里有一条断言专门钉它
- [x] `GET /api/system/info`：一次返回版本 / 当前用户 / 数据库 / 各目录 /
      浏览器驱动 / AI 配置状态。合成一个接口是有意的：这些都是「本机当前状态」，
      分开请求会出现互相矛盾的组合（数据库刚断，一半卡片说好一半说坏）
- [x] **数据库地址回显前先摘掉密码**（只回 scheme / host / port / 库名 / 用户）。
      这个字段会被渲染到页面上，直接回显等于把库密码贴在设置页，还会进浏览器历史与截图。
      **AI Key 连布尔值以外什么都不回**，只说「配没配」。两条都加了验收断言
- [x] 设置页三块：账号（改密码）/ 浏览器驱动（Chrome、Edge 可用性 + 路径 + 缓存目录，
      「重新检测」重取）/ 系统参数（只读：版本、数据库、连接状态、AI 配置、三个目录）
- [x] 驱动检测沿用 `check_browser()` 的**廉价探测**（浏览器装没装、缓存目录能不能写），
      **不启动浏览器也不下载驱动** —— 否则这一页首次打开就要卡几十秒。
      代价是**拿不到版本号**，页面显示的是可执行文件路径
- [x] `app.version` 从 `0.1.0` 改成 `2.0.0`，与本文档一致；设置页读的就是它，
      不在前端再写一份（两处各写一份必然漂移）
- [x] `verify_all.py` 新增 13 项设置断言。改密码是**写操作**，全程用临时用户
      `verify_tmp_user` 验、`finally` 里删掉，**绝不动 admin 的密码** ——
      万一中途异常退出，admin 被改了密码而文档里到处写着 admin123，等于把人锁在门外

### 验收规模

| 阶段 | 验收项数 |
|---|---|
| Day 2 | 23 |
| Day 3 | 62 |
| Day 4 | 82 |
| Day 5 | 98 |
| Day 6 | 122 |
| Day 7 | 144 |
| Day 8 | 148 |
| Day 9 | 164 |
| Day 10 | 171 |
| Day 11 | **184（全过）** |

### 已知未做（v2.0.0 范围内）

- [ ] Web 用例不支持场景串联与数据驱动
- [ ] 缺陷无附件 / 评论 / 指派（表里没有这些字段，要做先改表）
- [ ] 用例选择器有 200 条硬上限（超出时界面有提示，根治要给选择器加服务端搜索）

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
>
> 下面这份清单在 Day 8 逐条对照代码核实过（不是凭印象列的），**排序按投入产出比**而非发现顺序。
> 编号保持不变（正文里有「见上第 N 条」的交叉引用），做完的**划掉而不删除**。

### 新平台待做

1. [x] ~~**列表分页**~~ —— ✅ **Day 9 已完成**。会长的 6 个接口改为 `{ items, total }`；
   项目 / 环境 / 数据集**刻意保持裸数组**（它们同时是下拉数据源，分页会让选择器
   静默只显示头一页）。详见 Day 9
2. [x] ~~**设置页**~~ —— ✅ **Day 11 已完成**。账号（改密码）/ 浏览器驱动检测 /
   本机运行参数只读展示。详见 Day 11
3. [ ] **Setup / Teardown**（前置步骤 + 后置步骤）—— 全后端无任何实现
4. [ ] **缺陷附件 / 评论 / 指派** —— ⚠️ 表里没有这些字段，**要先改表**
5. [ ] **用例导入 / 导出（JSON / Excel）** —— 省手工录入
6. [ ] **前后端一起 Docker 化** —— 目前只有数据库跑了 compose。
   本地开发用不着，要给别人部署才需要
7. [ ] **窄视口表格横向溢出** —— 操作列已 `fixed="right"` 保证可点，
   整体仍需横向滚动，1440px 下正常
8. [ ] **Web 用例支持场景串联与数据驱动** —— 这两条链路目前只走接口执行器
9. [ ] **pytest 脚本导出** —— 若要做，定位是「给 CI 用」：
   Web 平台自己就能执行，不像桌面版非导出不可
10. [ ] **接口用例并发执行** —— 当前串行
11. [x] ~~**AI 助手**（DeepSeek 接入：用例生成 / 失败分析）~~ —— ✅ **Day 10 已完成**。
    当初记的顾虑是「`.env` 里 key 是空占位，做完也无法验证」，后来拿到真实 key 就解除了。
    边界情况（无 key / 非 JSON / 超时）用换掉 `httpx.post` 的方式在验收脚本里离线钉住，
    不依赖 key 是否可用
12. [ ] **定时执行** —— 独立工程：需引入常驻调度器
    （`test_plan.schedule` 字段已在 Day 5 删除）

### 桌面版有、新平台没搬（Day 8 逐模块比对发现）

> 这三条原先没记进待办，是比对旧桌面版 `app/engine/`、`app/utils/` 才发现的。

| 桌面版模块 | 新平台 | 去向 |
|---|---|---|
| `app/engine/script_generator.py` | 0 处引用 | 📋 见上第 9 条 |
| `app/engine/excel_exporter.py` / `json_exporter.py` | 0 处引用 | 📋 见上第 5 条 |
| `app/utils/pdf_exporter.py` | 0 处引用 | ⏸ **建议不做** —— 那是桌面程序没法调浏览器才要的 Chrome CDP `printToPDF`，Web 端浏览器自带「打印成 PDF」 |

> 注：后端依赖里有 `openpyxl`，但只用于**读取**数据驱动的 Excel，与导出无关，别被它误导。

### 桌面版计划项的去向

| 原计划项 | 去向 |
|---|---|
| 批量执行（勾选多条用例一次执行） | ✅ 新平台已做 —— 测试计划（Day 5） |
| 数据驱动测试（CSV / Excel 参数化） | ✅ 新平台已做（Day 3） |
| 用例导入 / 导出（JSON） | 📋 见「新平台待做」第 5 条 |
| 接口用例并发执行 | 📋 见「新平台待做」第 10 条 |
| PyInstaller 打包测试 | ⏸ 随桌面版冻结作废 |
