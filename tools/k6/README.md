# k6 压测工具（上线放行用）

配合 `docs/process/上线放行标准.md` 的 **G4（容量）/ G5（稳定性）** 使用。

平台自带的性能模块只能压单接口、客户端是本机、最长 10 分钟 —— 它适合「改前改后对比」，
**不适合**判断「能不能扛住上线」。容量结论一律用 k6 跑。

---

## 1. 安装（Windows，装在 E 盘）

```powershell
winget install k6 --source winget
# 或
scoop install k6
# 或（免安装：解压到 E 盘，别放 C 盘）
#   下载 https://github.com/grafana/k6/releases 的 windows-amd64.zip
#   解到 E:\项目\接口测试工具\.cache\k6\ ，把该目录加进 PATH
```

验证：`k6 version`

---

## 2. 三步走（顺序不要跳）

```powershell
$env:BASE_URL="https://被测环境地址/api"
$env:RELEASE_TAG="v1.2.0"

# 第 1 步：冒烟。只验证脚本本身通不通，不看容量
$env:PROFILE="smoke"
k6 run tools/k6/link-template.js

# 第 2 步：阶段加压，找拐点
$env:PROFILE="ramp"; $env:TARGET_RPS="100"
k6 run tools/k6/link-template.js

# 第 3 步：30 分钟稳定性（G5）。跑之前先确认服务端监控开着
$env:PROFILE="steady"; $env:TARGET_RPS="100"
k6 run tools/k6/link-template.js
```

> 第一次用之前，先把脚本里的 **TODO 1~4** 换成被测产品的真实接口。不改就是压示例靶子，
> 结论无效。

---

## 3. 怎么读结果

### 先看这一行

```
✓ http_req_failed...: 0.00%  ✓ http_req_duration...: avg=42ms p(95)=88ms
```

- **阈值全 `✓`** = 这一档通过；出现 `✗` = **不通过**，不要解释成「差不多」
- `handleSummary` 会写一个 `k6-result-{RELEASE_TAG}-{PROFILE}.json`，里面 `thresholds_ok`
  就是最终判定，直接贴进放行记录

### 阶段加压（ramp）时看什么

对照 JSON 里的 `p95_ms` 和服务端监控，找**拐点**：RPS 继续涨但 p95 开始陡升、错误率抬头的那个点。
那就是这套环境的上限。放行记录里写：

> 「该环境在约 N RPS 时 p95 从 X ms 升至 Y ms，判定容量上限为 N RPS，目标值取其 70%。」

### 稳定性（steady）时看什么

30 分钟内，服务端**内存、DB 连接数、线程数**应该走平或轻微波动。持续单调上升就是泄漏，
不管延迟多好看，**G5 不通过**。

### `biz_failed` 是干什么的

`http_req_failed` 只统计 HTTP 层（4xx/5xx）。真实产品常见「200 但返回空数据 / 业务错误码」，
所以脚本里单独记了 `biz_failed`：**200 也要校验响应体**，否则压测会假装全绿。

---

## 4. 六个一定会踩的坑

| 坑 | 后果 | 怎么办 |
|---|---|---|
| 压测机与被测机同一台 | 测的是自己机器的 CPU | 客户端分离；做不到就在放行记录里写明「同机压测」 |
| 压测机上还挂着浏览器 / 后端服务 | 结果波动无解释 | 压测前关掉无关进程 |
| 删掉脚本里的 `sleep` | 压力模型从「用户」变「机器」，容量虚高 | 保留思考时间 |
| `BASE_URL` 末尾带 `/` | 拼出 `//auth/login`，有的网关直接 404 | 统一不带尾斜杠 |
| 30 分钟长跑 token 过期 | 后半程全是 401，看起来像产品挂了 | 用 `-e TOKEN=xxx` 传长期令牌，或在 setup 里改成刷新逻辑 |
| 直接打生产环境 | 可能真触发业务（下单、扣款） | **只打测试/预发**；必须打生产时先确认环境是只读的、且拿到授权 |

---

## 5. 数据清理

脚本给每条创建请求都带了 `RUN_TAG`（`k6-<时间戳>`）。跑完：

- 产品支持按名称/备注搜索 → 按 `RUN_TAG` 搜出来删掉
- 不支持 → 在放行记录里写明「测试环境存在 k6 压测脏数据，标记为 k6-xxx」

**不要留着不处理**：脏数据会让下一轮统计口径跑偏，也容易被当成本次发布的真实数据。
