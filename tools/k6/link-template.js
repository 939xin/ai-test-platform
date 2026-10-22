/**
 * k6 业务链路压测模板
 * ---------------------------------------------------------------------------
 * 用途：给「要上线的产品」跑容量与稳定性，产出能写进《上线放行标准》G4/G5 的证据。
 *
 * 为什么不用平台自带的 perf 模块：那个只能压单接口、客户端就是本机、最长 10 分钟，
 * 数字不可辩护（见 docs/process/上线放行标准.md §7）。这个脚本才是放行依据。
 *
 * 三种档位（用 PROFILE 切换）：
 *   PROFILE=smoke   1 VU / 10 秒   —— 先验证脚本能跑通，别急着加压
 *   PROFILE=ramp    阶段加压        —— 找拐点（默认）
 *   PROFILE=steady  恒定 RPS / 30 分钟 —— 稳定性，对应 G5
 *
 * 用法：
 *   k6 run -e BASE_URL=https://test.example.com -e RELEASE_TAG=v1.2.0 tools/k6/link-template.js
 *   k6 run -e PROFILE=smoke -e BASE_URL=... tools/k6/link-template.js
 *   k6 run -e PROFILE=steady -e TARGET_RPS=100 -e BASE_URL=... tools/k6/link-template.js
 *
 * ⚠️ 脚本里所有 `TODO` 都必须换成被测产品的真实接口，否则脚本跑的是示例靶子。
 * ---------------------------------------------------------------------------
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ===== 配置（全部走环境变量，别在代码里写死地址）=======================
const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000/api';
const RELEASE_TAG = __ENV.RELEASE_TAG || 'unset';
const RUN_TAG = __ENV.RUN_TAG || `k6-${Date.now()}`; // 造数据标记，便于事后清理
const PROFILE = __ENV.PROFILE || 'ramp';
const TARGET_RPS = Number(__ENV.TARGET_RPS || 50);
const P95_MS = Number(__ENV.P95_MS || 500);
const MAX_ERR_RATE = Number(__ENV.MAX_ERR_RATE || 0.001);

// ===== 自定义指标（业务层失败要和 HTTP 层失败分开看）====================
const bizFailed = new Rate('biz_failed');      // 200 但业务字段不对
const loginMs = new Trend('login_duration_ms', true); // 登录耗时单独统计
const created = new Counter('created_resources');     // 造了多少数据

// ===== 场景 =============================================================
function buildScenarios() {
  if (PROFILE === 'smoke') {
    return { smoke: { executor: 'constant-vus', vus: 1, duration: '10s' } };
  }
  if (PROFILE === 'steady') {
    // 恒定到达率：这才是「目标 RPS」的准确表达，比固定 VU 数更贴近真实流量
    return {
      steady: {
        executor: 'constant-arrival-rate',
        rate: Math.max(1, Math.round(TARGET_RPS)),
        timeUnit: '1s',
        duration: '30m',
        preAllocatedVUs: Math.max(10, Math.round(TARGET_RPS / 2)),
        maxVUs: Math.max(100, Math.round(TARGET_RPS * 4)),
      },
    };
  }
  // 默认：阶段加压找拐点。每一阶段稳定 2 分钟，够服务端走出瞬时抖动
  return {
    ramp: {
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: Math.max(200, Math.round(TARGET_RPS * 4)),
      stages: [
        { target: Math.max(1, Math.round(TARGET_RPS * 0.1)), duration: '1m' },
        { target: Math.max(2, Math.round(TARGET_RPS * 0.3)), duration: '1m' },
        { target: Math.round(TARGET_RPS * 0.6), duration: '1m' },
        { target: Math.round(TARGET_RPS), duration: '2m' },
        { target: Math.round(TARGET_RPS), duration: '2m' },
        { target: 0, duration: '30s' },
      ],
    },
  };
}

export const options = {
  scenarios: buildScenarios(),
  // smoke 档只验证脚本可行性，不拿它判定容量
  thresholds:
    PROFILE === 'smoke'
      ? {}
      : {
          http_req_failed: [`rate<${MAX_ERR_RATE}`],
          http_req_duration: [`p(95)<${P95_MS}`],
          biz_failed: ['rate<0.01'],
        },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

// ===== setup：登录一次，拿 token 给所有 VU 复用 =========================
export function setup() {
  if (__ENV.TOKEN) return { token: __ENV.TOKEN }; // 已有 token 就跳过登录

  // TODO 1：改成被测产品的登录接口与字段
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ username: __ENV.USER || 'admin', password: __ENV.PASS || 'admin123' }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: 'login' } }
  );
  loginMs.add(res.timings.duration);

  const ok = check(res, {
    'login 200': (r) => r.status === 200,
  });
  if (!ok) {
    console.error(`登录失败：status=${res.status} body=${String(res.body).slice(0, 200)}`);
    // 登录挂了两件事：不是产品挂了，就是账号/字段不对。两者都必须停下来看
    throw new Error('登录失败，先修脚本或确认账号，不要继续压测');
  }

  // TODO 2：改成被测产品的 token 字段路径
  const body = res.json();
  const token = body.access_token || body.token || body.data?.token;
  if (!token) throw new Error('没从登录响应里取到 token，检查 TODO 2');

  return { token };
}

// ===== 主流程：按比例混合的三条请求 ====================================
// 60% 列表、30% 详情、10% 创建 —— 比例要按真实业务改，不要照抄
export default function (data) {
  const auth = { Authorization: `Bearer ${data.token}` };
  const roll = Math.random();

  if (roll < 0.6) {
    group('list', () => {
      const r = http.get(`${BASE_URL}/projects?limit=20`, { headers: auth, tags: { name: 'list' } });
      check(r, { 'list 200': (x) => x.status === 200 });
      bizFailed.add(!(r.status === 200 && r.body && r.body.length > 2));
    });
  } else if (roll < 0.9) {
    group('detail', () => {
      const r = http.get(`${BASE_URL}/projects/1`, { headers: auth, tags: { name: 'detail' } });
      check(r, { 'detail 200': (x) => x.status === 200 });
      bizFailed.add(!(r.status === 200 && r.json() !== null));
    });
  } else {
    group('create', () => {
      // TODO 3：改成一条真实写操作（下单 / 建单 / 提交）
      const payload = {
        name: `${RUN_TAG}-${__VU}-${__ITER}`, // 带标记，便于 teardown 或人工清理
        description: 'k6 压测数据',
      };
      const r = http.post(`${BASE_URL}/projects`, JSON.stringify(payload), {
        headers: { ...auth, 'Content-Type': 'application/json' },
        tags: { name: 'create' },
      });
      const ok = check(r, { 'create 2xx': (x) => x.status >= 200 && x.status < 300 });
      if (ok) created.add(1);
      bizFailed.add(!ok);
    });
  }

  // 真实用户有思考时间。**不要删这个 sleep**：删掉之后压力模型就从「用户」变成「机器」，
  // 测出来的容量会虚高，上线后打脸
  sleep(Math.random() * 2 + 0.5);
}

// ===== 收尾 ============================================================
export function teardown(data) {
  // 造的数据要么删、要么在放行记录里写明「测试环境脏数据未清理」。
  // 对真实产品（尤其共享测试环境）建议删：残留数据会让下一轮统计口径跑偏。
  // TODO 4：改成按 RUN_TAG 查询并批量删除；做不到就删掉这段，去 README 记一笔手工清理
  console.log(`本轮造数据标记：${RUN_TAG}（如需清理，按此标记过滤）`);
}

// ===== 摘要落盘：生成能直接贴进放行记录的 JSON =========================
export function handleSummary(data) {
  const m = data.metrics;
  const pick = (name, stat) => (m[name] && m[name].values && m[name].values[stat] !== undefined
    ? m[name].values[stat]
    : null);

  const summary = {
    release_tag: RELEASE_TAG,
    run_tag: RUN_TAG,
    profile: PROFILE,
    base_url: BASE_URL,
    target_rps: TARGET_RPS,
    p95_threshold_ms: P95_MS,
    max_error_rate: MAX_ERR_RATE,
    result: {
      http_req_failed: pick('http_req_failed', 'rate'),
      p95_ms: pick('http_req_duration', 'p(95)'),
      p99_ms: pick('http_req_duration', 'p(99)'),
      avg_ms: pick('http_req_duration', 'avg'),
      biz_failed: pick('biz_failed', 'rate'),
      login_ms: pick('login_duration_ms', 'avg'),
      iterations: pick('iterations', 'count'),
      created: pick('created_resources', 'count'),
    },
    // k6 自己判定阈值是否全过：false 就是「不通过」，别自己再算一遍
    thresholds_ok: Object.values(data.metrics)
      .filter((x) => x.thresholds)
      .every((x) => Object.values(x.thresholds).every((th) => th.ok)),
  };

  return {
    stdout: `\n===== ${RELEASE_TAG} / ${PROFILE} =====\n` + JSON.stringify(summary, null, 2) + '\n',
    [`k6-result-${RELEASE_TAG}-${PROFILE}.json`]: JSON.stringify(summary, null, 2),
  };
}
