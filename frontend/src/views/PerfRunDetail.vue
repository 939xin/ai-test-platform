<script setup>
/**
 * 压测运行详情。
 *
 * 运行中每秒轮询 /progress（页面隐藏时降为 5 秒），终态立刻停止轮询并拉一次完整详情。
 * 用 setTimeout 递归而不是 setInterval：慢请求不会叠在一起。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Refresh, VideoPause } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PerfRunStatusTag from '@/components/PerfRunStatusTag.vue'
import PerfHistogram from '@/components/PerfHistogram.vue'
import PerfLineChart from '@/components/PerfLineChart.vue'
import {
  ACTIVE_PERF_STATUSES, getPerfLimits, getPerfRun, getPerfRunProgress, stopPerfRun,
} from '@/api/perf'

const route = useRoute()
const router = useRouter()
const runId = Number(route.params.runId)

const run = ref(null)
const progress = ref(null)
const loading = ref(true)
const actionLoading = ref(false)

// 能力边界要写进常驻说明块，数字一律从后端读 —— 页面里再写一份 50 / 600 早晚会对不上
const limits = ref({
  max_concurrency: null,
  max_duration_seconds: null,
  hard_wall_seconds: null,
})

let timer = null
let failCount = 0

const isActive = computed(() => ACTIVE_PERF_STATUSES.includes(progress.value?.status || run.value?.status))

const metrics = computed(() => run.value?.metrics_json || {})
const counts = computed(() => metrics.value.counts || {})
const latency = computed(() => metrics.value.latency_ms || {})
const tps = computed(() => metrics.value.tps || {})
const timeline = computed(() => metrics.value.timeline || [])
const histogram = computed(() => metrics.value.histogram || { bounds_ms: [], counts: [] })
const errorCounts = computed(() => metrics.value.errors || {})
const statusCodes = computed(() =>
  Object.entries(metrics.value.status_codes || {})
    .sort((a, b) => Number(b[1]) - Number(a[1])),
)
const sampleErrors = computed(() => (metrics.value.sample_errors || []).slice(0, 10))
const planned = computed(() => metrics.value.planned || {})
// 运行中 metrics_json 还是空的，判定规则先读请求快照里存的那份
const successRule = computed(
  () => metrics.value.success_rule || run.value?.request_json?.success_rule || '—',
)

const ERROR_LABELS = {
  connection: '连接失败',
  timeout: '请求超时',
  http_4xx: 'HTTP 4xx',
  http_5xx: 'HTTP 5xx',
  other: '其他异常',
}

const errorRows = computed(() =>
  Object.entries(errorCounts.value)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => ({
      key,
      label: ERROR_LABELS[key] || key,
      count,
      pct: counts.value.total ? (count / counts.value.total) * 100 : 0,
    })),
)

const progressPct = computed(() => progress.value?.progress_pct ?? (run.value?.status === 'completed' ? 100 : 0))
const preview = computed(() => progress.value?.metrics_preview || {})

// 运行中 metrics_json 为空，模式与目标量要回退读 perf_run 上的配置快照；
// 否则 duration 模式会显示任务表里那个没被使用的 total_requests（1000 次）。
const totalLabel = computed(() => {
  const mode = planned.value.mode || run.value?.load_mode
  if (mode === 'duration') {
    return `${planned.value.duration_seconds || run.value?.duration_seconds || 0} 秒`
  }
  return `${planned.value.total_requests || run.value?.total_requests || 0} 次`
})

// 运行中指标卡：用进度接口的实时数据，不要在运行中一排「— / 0」
const liveStats = computed(() => {
  if (!isActive.value || !progress.value) return null
  const done = progress.value.requests_done || 0
  const failed = progress.value.requests_failed || 0
  return {
    tps: progress.value.current_tps ?? 0,
    successRate: done ? (done - failed) / done : null,
    p95: preview.value.p95,
    total: done,
    avg: preview.value.avg_ms,
    durationMs: progress.value.elapsed_ms || 0,
  }
})

const displayStats = computed(() => {
  if (liveStats.value) {
    return {
      tps: liveStats.value.tps,
      success: percent(liveStats.value.successRate),
      p95: ms(liveStats.value.p95),
      total: liveStats.value.total,
      avg: ms(liveStats.value.avg),
      duration: (liveStats.value.durationMs / 1000).toFixed(2),
    }
  }
  return {
    tps: tps.value.avg ?? '—',
    success: percent(counts.value.success_rate),
    p95: ms(latency.value.p95),
    total: counts.value.total ?? 0,
    avg: ms(latency.value.avg),
    duration: ((run.value?.duration_ms || 0) / 1000).toFixed(2),
  }
})

const stopReasonText = computed(() => {
  const reason = run.value?.stop_reason
  if (reason === 'error_rate') return '错误率超过阈值，已自动熔断停止'
  if (reason === 'wall_timeout') return '超过单次运行的硬墙钟上限，已自动停止'
  if (reason === 'request_cap') return '达到单次运行的请求数硬上限，已自动停止'
  if (reason === 'stale') return '服务重启或心跳中断，运行已终止'
  if (reason === 'exception') return '压测进程异常终止'
  return ''
})

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

function ms(value) {
  return value == null ? '—' : `${value} ms`
}

function percent(value) {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

const releaseTag = computed(() => run.value?.release_tag || '')

/** 导出文件名的安全化：版本号里常带 / : 空格，不能直接进文件名 */
function safeFileName(text) {
  return String(text).replace(/[\\/:*?"<>|\s]+/g, '_')
}

function downloadBlob(content, filename, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  // 立刻 revoke 在部分浏览器会掐断下载，延后一拍
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** 导出整份详情响应（含 metrics_json），归档 / 机读用。 */
function exportJson() {
  if (!run.value) return
  const suffix = releaseTag.value ? `-${safeFileName(releaseTag.value)}` : ''
  const content = JSON.stringify(
    { exported_at: new Date().toISOString(), run: run.value },
    null,
    2,
  )
  downloadBlob(content, `perf-run-${run.value.id}${suffix}.json`, 'application/json')
  ElMessage.success('已导出结果 JSON')
}

/** 放行记录要的那几行；直接粘进 docs/process/上线放行标准.md §6 */
function buildMarkdown() {
  const rows = [
    ['运行记录', `#${run.value.id}`],
    ['版本（release_tag）', releaseTag.value || '未标注'],
    ['环境', run.value.env_name || '不使用环境'],
    ['并发', String(run.value.concurrency)],
    ['时长', `${((run.value.duration_ms || 0) / 1000).toFixed(2)} s`],
    ['平均延迟', ms(latency.value.avg)],
    ['p95', ms(latency.value.p95)],
    ['p99', ms(latency.value.p99)],
    ['TPS（平均）', tps.value.avg == null ? '—' : String(tps.value.avg)],
    ['失败率', percent(counts.value.error_rate)],
    ['结束时间', formatTime(run.value.finished_at)],
  ]
  const table = [
    '| 项 | 实测 |',
    '|---|---|',
    ...rows.map(([key, value]) => `| ${key} | ${value} |`),
  ]
  return [
    ...table,
    '',
    `> 来源：平台压测 #${run.value.id}（单机客户端、仅校验状态码），`
      + '仅用于同一任务改前改后对比，**不作为容量验收依据**；容量结论用 k6。',
  ].join('\n')
}

async function copyMarkdown() {
  if (!run.value) return
  const text = buildMarkdown()
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制 Markdown 摘要')
  } catch {
    // 非安全上下文（http + 非 localhost）没有 clipboard API，退回旧写法
    const area = document.createElement('textarea')
    area.value = text
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    document.execCommand('copy')
    document.body.removeChild(area)
    ElMessage.success('已复制 Markdown 摘要')
  }
}

function clearTimer() {
  clearTimeout(timer)
  timer = null
}

function needsPolling() {
  const status = progress.value?.status || run.value?.status
  return ACTIVE_PERF_STATUSES.includes(status)
}

async function refreshRun() {
  run.value = await getPerfRun(runId)
}

async function poll() {
  try {
    progress.value = await getPerfRunProgress(runId)
    failCount = 0
    if (!ACTIVE_PERF_STATUSES.includes(progress.value.status)) {
      // 终态：再拉一次完整详情（最终 metrics_json 在这一步才完整）
      await refreshRun()
      progress.value = null
    }
  } catch {
    failCount += 1
  }
}

function schedule() {
  clearTimer()
  if (!needsPolling()) return
  const delay = document.hidden ? 5000 : (failCount >= 3 ? 5000 : 1000)
  timer = setTimeout(async () => {
    await poll()
    schedule()
  }, delay)
}

async function load() {
  loading.value = true
  try {
    // 上限读不到不影响看数据，说明块里先显示「—」
    const [limitsData] = await Promise.all([
      getPerfLimits().catch(() => null),
      refreshRun(),
    ])
    if (limitsData) limits.value = limitsData
    if (needsPolling()) {
      await poll()
      schedule()
    }
  } catch {
    ElMessage.error('运行记录不存在或已被删除')
    router.replace({ name: 'perf-runs' })
  } finally {
    loading.value = false
  }
}

async function reload() {
  await poll()
  if (!isActive.value) await refreshRun()
  schedule()
}

async function stop() {
  await ElMessageBox.confirm(
    '停止后在途请求最多还要等待一个请求超时，指标会标记为部分数据。确定停止？',
    '停止压测',
    { type: 'warning', confirmButtonText: '停止', cancelButtonText: '取消' },
  )
  actionLoading.value = true
  try {
    await stopPerfRun(runId)
    ElMessage.success('已请求停止')
    await poll()
    schedule()
  } finally {
    actionLoading.value = false
  }
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'perf-runs' })
}

onMounted(load)
onBeforeUnmount(clearTimer)
</script>

<template>
  <div v-loading="loading" class="page-stack">
    <PageHeader :title="`运行详情 #${runId}`" :description="run ? `${run.task_name || '—'} · ${run.case_name || '—'}` : ''">
      <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
      <el-button :icon="Refresh" @click="reload">刷新</el-button>
      <el-button :disabled="!run || isActive" @click="exportJson">导出结果 JSON</el-button>
      <el-button :disabled="!run || isActive" @click="copyMarkdown">复制 Markdown 摘要</el-button>
      <el-button
        v-if="isActive"
        type="warning"
        :icon="VideoPause"
        :loading="actionLoading"
        @click="stop"
      >停止压测</el-button>
    </PageHeader>

    <!-- 能力边界：必须常驻可见。刻意不做折叠 / tooltip / 一次性提示 ——
         半年后打开这条记录的人，不会去点开一个「了解更多」。 -->
    <el-card shadow="never" class="boundary-card">
      <div class="boundary-title">这份数据能证明什么</div>
      <ul class="boundary-list">
        <li>
          压测客户端就是<strong>本机单进程</strong>（Python 线程），并发上限
          <b class="mono">{{ limits.max_concurrency ?? '—' }}</b>（读自
          <span class="mono">GET /api/perf-limits</span>，不是页面写死的数字）
        </li>
        <li>
          单轮最长 <b class="mono">{{ limits.max_duration_seconds ?? '—' }}</b> 秒，
          超过 <b class="mono">{{ limits.hard_wall_seconds ?? '—' }}</b> 秒会被强制停止
        </li>
        <li><strong>只校验 HTTP 状态码</strong>，不校验响应体内容 —— 接口返回了错数据也算成功</li>
        <li>
          p50 / p95 / p99 来自固定分桶插值：100 ms 以内桶宽 1–10 ms（够用）；
          <strong>1 秒以上桶宽达数百毫秒到秒级</strong>，长尾不能当精确值引用
        </li>
      </ul>
      <p class="boundary-conclusion">
        结论：本页数据<strong>仅用于「同一任务、同一环境、改前改后」的对比，不作为容量验收依据</strong>；
        容量结论用 k6（<span class="mono">tools/k6/</span>）。
      </p>
    </el-card>

    <template v-if="run">
      <el-card shadow="never" class="summary-card">
        <div class="summary">
          <PerfRunStatusTag :status="run.status" />
          <el-tag v-if="releaseTag" size="small" effect="light" class="mono">{{ releaseTag }}</el-tag>
          <el-tag v-else size="small" type="info" effect="plain">未标注版本</el-tag>
          <span class="mono">{{ run.env_name || '不使用环境' }}</span>
          <span class="mono muted">开始 {{ formatTime(run.started_at) }}</span>
          <span class="mono muted">结束 {{ formatTime(run.finished_at) }}</span>
          <span class="mono muted">授权人 {{ run.authorized_by || '—' }}</span>
        </div>
        <div class="rule">
          成功判定：<span class="mono">{{ successRule }}</span>
          <span class="muted">（压测只校验状态码，不执行响应体断言）</span>
        </div>
      </el-card>

      <el-alert
        v-if="run.status === 'stopped'"
        type="info"
        :closable="false"
        show-icon
        title="运行被手动停止，以下指标是停止时的部分数据"
      />
      <el-alert
        v-else-if="run.status === 'aborted'"
        type="warning"
        :closable="false"
        show-icon
        :title="stopReasonText || '运行被自动中止'"
      />
      <el-alert
        v-else-if="run.status === 'failed'"
        type="error"
        :closable="false"
        show-icon
        :title="run.error_msg || stopReasonText || '运行失败'"
      />

      <!-- 运行中：实时进度 -->
      <el-card v-if="isActive" shadow="never" class="live-card">
        <div class="live-head">
          <div class="live-title">
            <PerfRunStatusTag :status="progress?.status || run.status" />
            <span class="mono">
              {{ progress?.requests_done || 0 }} 次
              <span class="muted">/ {{ totalLabel }}</span>
            </span>
            <span v-if="progress?.stop_requested" class="muted">· 正在停止</span>
          </div>
          <span v-if="progress?.stale" class="stale">心跳中断，可能已失联</span>
        </div>

        <el-progress
          :percentage="progressPct"
          :stroke-width="10"
          :status="progress?.stop_requested ? 'warning' : undefined"
        />

        <div class="live-grid">
          <span>当前 TPS <b class="mono">{{ progress?.current_tps ?? 0 }}</b></span>
          <span>实时 P95 <b class="mono">{{ ms(preview.p95) }}</b></span>
          <span>错误率 <b class="mono">{{ percent(progress?.error_rate) }}</b></span>
          <span>已耗时 <b class="mono">{{ ((progress?.elapsed_ms || 0) / 1000).toFixed(1) }} s</b></span>
          <span v-if="progress?.eta_seconds != null">预计剩余 <b class="mono">{{ progress.eta_seconds }} s</b></span>
        </div>
      </el-card>

      <!-- 核心指标 -->
      <div class="stat-row">
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">{{ isActive ? '当前 TPS' : '平均 TPS' }}</div>
          <div class="mono stat-value">{{ displayStats.tps }}</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">成功率</div>
          <div class="mono stat-value">{{ displayStats.success }}</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">P95 延迟</div>
          <div class="mono stat-value">{{ displayStats.p95 }}</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">总请求</div>
          <div class="mono stat-value">{{ displayStats.total }}</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">平均延迟</div>
          <div class="mono stat-value">{{ displayStats.avg }}</div>
        </el-card>
        <el-card shadow="never" class="stat-card">
          <div class="stat-label">运行时长</div>
          <div class="mono stat-value">{{ displayStats.duration }} s</div>
        </el-card>
      </div>

      <div class="two-col">
        <el-card shadow="never">
          <template #header><span class="card-title">延迟百分位</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="最小">{{ ms(latency.min) }}</el-descriptions-item>
            <el-descriptions-item label="最大">{{ ms(latency.max) }}</el-descriptions-item>
            <el-descriptions-item label="平均">{{ ms(latency.avg) }}</el-descriptions-item>
            <el-descriptions-item label="P50">{{ ms(latency.p50) }}</el-descriptions-item>
            <el-descriptions-item label="P90">{{ ms(latency.p90) }}</el-descriptions-item>
            <el-descriptions-item label="P95">{{ ms(latency.p95) }}</el-descriptions-item>
            <el-descriptions-item label="P99">{{ ms(latency.p99) }}</el-descriptions-item>
            <el-descriptions-item label="峰值 TPS">{{ tps.peak ?? '—' }}</el-descriptions-item>
          </el-descriptions>
          <p class="foot">百分位由固定分桶直方图近似，常用区间误差约 1–5 ms。</p>
        </el-card>

        <el-card shadow="never">
          <template #header><span class="card-title">延迟分布</span></template>
          <PerfHistogram :bounds="histogram.bounds_ms" :counts="histogram.counts" />
        </el-card>
      </div>

      <el-card shadow="never">
        <template #header><span class="card-title">时间趋势</span></template>
        <div class="two-col charts">
          <PerfLineChart :points="timeline" y-key="tps" label="每秒 TPS" unit="" color="#16697a" />
          <PerfLineChart :points="timeline" y-key="avg_ms" label="每秒平均延迟" unit=" ms" color="#d98c1f" />
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><span class="card-title">错误与状态码</span></template>
        <div v-if="errorRows.length" class="error-grid">
          <div v-for="row in errorRows" :key="row.key" class="error-item">
            <span class="error-label">{{ row.label }}</span>
            <span class="mono error-count">{{ row.count }}</span>
            <span class="mono error-pct">{{ row.pct.toFixed(2) }}%</span>
          </div>
        </div>
        <p v-else class="foot">没有失败请求。</p>

        <el-table
          v-if="statusCodes.length"
          :data="statusCodes.map(([code, count]) => ({ code, count }))"
          size="small"
          class="status-table"
        >
          <el-table-column prop="code" label="状态码" width="120">
            <template #default="{ row }"><span class="mono">{{ row.code }}</span></template>
          </el-table-column>
          <el-table-column prop="count" label="次数" width="120">
            <template #default="{ row }"><span class="mono">{{ row.count }}</span></template>
          </el-table-column>
        </el-table>

        <el-collapse v-if="sampleErrors.length" class="samples">
          <el-collapse-item :title="`错误样本（${sampleErrors.length} 条）`" name="samples">
            <div v-for="(item, index) in sampleErrors" :key="index" class="sample">
              <span class="mono sample-kind">{{ ERROR_LABELS[item.kind] || item.kind }}</span>
              <span v-if="item.status != null" class="mono muted">HTTP {{ item.status }}</span>
              <span class="mono sample-msg">{{ item.message || '—' }}</span>
            </div>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <div class="two-col">
        <el-card shadow="never">
          <template #header><span class="card-title">运行配置</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="版本标注">
              <span v-if="releaseTag" class="mono">{{ releaseTag }}</span>
              <span v-else class="muted">未标注</span>
            </el-descriptions-item>
            <el-descriptions-item label="负载模式">
              {{ planned.mode === 'duration' ? '按持续时长' : '按总请求数' }}
            </el-descriptions-item>
            <el-descriptions-item label="目标量">{{ totalLabel }}</el-descriptions-item>
            <el-descriptions-item label="并发数">{{ planned.concurrency ?? run.concurrency }}</el-descriptions-item>
            <el-descriptions-item label="目标 RPS">{{ planned.target_rps || '不限速' }}</el-descriptions-item>
            <el-descriptions-item label="预热">{{ planned.warmup_seconds ?? run.warmup_seconds }} 秒</el-descriptions-item>
            <el-descriptions-item label="单请求超时">{{ run.request_timeout }} 秒</el-descriptions-item>
            <el-descriptions-item label="校验 SSL">{{ run.verify_ssl ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="授权时间">{{ formatTime(run.authorized_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card shadow="never">
          <template #header><span class="card-title">目标请求（已脱敏）</span></template>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="方法">
              <span class="mono">{{ run.request_json.method || '—' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="URL">
              <span class="mono break">{{ run.request_json.url || '—' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="请求头">
              <span class="mono">
                {{ (run.request_json.header_names || []).join(', ') || '—' }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="请求体">
              <span class="mono">{{ run.request_json.body_bytes || 0 }} 字节</span>
            </el-descriptions-item>
            <el-descriptions-item label="认证方式">{{ run.request_json.auth_type || 'none' }}</el-descriptions-item>
          </el-descriptions>
          <p class="foot">只记录方法、打码 URL、请求头名称与体积，不保存令牌、Cookie 或请求体原文。</p>
        </el-card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.boundary-card {
  margin-bottom: 12px;
  border-left: 3px solid var(--brand-500, #16697a);
  background: var(--bg-sunken);
}

.boundary-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 6px;
}

.boundary-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.75;
  color: var(--text-2);
}

.boundary-list strong {
  color: var(--text-1);
}

.boundary-list b {
  color: var(--text-1);
}

.boundary-conclusion {
  margin: 8px 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-1);
}

.summary-card {
  margin-bottom: 12px;
}

.summary {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.rule {
  margin-top: 8px;
  font-size: 12.5px;
  color: var(--text-2);
}

.live-card {
  margin: 12px 0;
}

.live-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.live-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.live-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 12px;
  font-size: 12.5px;
  color: var(--text-2);
}

.live-grid b {
  color: var(--text-1);
  font-weight: 600;
}

.stale {
  font-size: 12px;
  color: var(--signal-warn);
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  margin: 12px 0;
}

.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 6px;
}

.stat-value {
  font-size: 19px;
  font-weight: 600;
  color: var(--text-1);
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.two-col.charts {
  gap: 18px;
  margin-bottom: 0;
}

.card-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
}

.foot {
  margin: 8px 0 0;
  font-size: 11.5px;
  line-height: 1.6;
  color: var(--text-3);
}

.error-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.error-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  font-size: 12.5px;
}

.error-label {
  flex: 1;
  color: var(--text-2);
}

.error-count {
  color: var(--signal-fail);
  font-weight: 600;
}

.error-pct {
  color: var(--text-3);
}

.status-table {
  margin-top: 8px;
}

.samples {
  margin-top: 10px;
}

.sample {
  display: flex;
  gap: 10px;
  padding: 5px 0;
  font-size: 12px;
  border-bottom: 1px dashed var(--border);
}

.sample-kind {
  color: var(--signal-warn);
  flex-shrink: 0;
}

.sample-msg {
  color: var(--text-2);
  word-break: break-all;
}

.break {
  word-break: break-all;
}

.muted {
  color: var(--text-3);
}

@media (max-width: 1100px) {
  .stat-row {
    grid-template-columns: repeat(3, 1fr);
  }

  .two-col {
    grid-template-columns: 1fr;
  }
}
</style>
