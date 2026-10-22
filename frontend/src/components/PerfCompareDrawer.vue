<script setup>
/**
 * 两次压测结果对比抽屉。
 *
 * 方向是钉死的：**左 = 较早（id 较小），右 = 较新（id 较大）**，
 * delta = (右 − 左) / 左。调用方负责按 id 排好再传进来，
 * 不能拿 el-table 的勾选顺序当基线 —— 那样 delta 符号会反、颜色会全错。
 *
 * 染色按语义而不是按符号：
 * - 延迟（avg / p50 / p90 / p95 / p99）、错误率、失败数 上升 = 劣化 → 红
 * - TPS 上升 = 改善 → 绿
 * 绝对不能写成「正数就红」。
 */
import { computed, ref, watch } from 'vue'

import { comparePerfRuns } from '@/api/perf'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  leftId: { type: Number, default: null },
  rightId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const data = ref(null)
const loading = ref(false)
const errorText = ref('')

// 方向：bad-up = 上升是劣化；good-up = 上升是改善；neutral 不上色
const METRICS = [
  { label: '总请求数', delta: 'total_pct', direction: 'neutral', format: (row) => num(row.counts?.total) },
  { label: '失败数', delta: 'failed_pct', direction: 'bad-up', format: (row) => num(row.counts?.failed) },
  { label: '错误率', delta: 'error_rate_pct', direction: 'bad-up', format: (row) => percent(row.error_rate) },
  { label: 'TPS（平均）', delta: 'tps_pct', direction: 'good-up', format: (row) => num(row.tps?.avg, 2) },
  { label: '平均延迟', delta: 'avg_pct', direction: 'bad-up', format: (row) => ms(row.latency_ms?.avg) },
  { label: 'P50 延迟', delta: 'p50_pct', direction: 'bad-up', format: (row) => ms(row.latency_ms?.p50) },
  { label: 'P90 延迟', delta: 'p90_pct', direction: 'bad-up', format: (row) => ms(row.latency_ms?.p90) },
  { label: 'P95 延迟', delta: 'p95_pct', direction: 'bad-up', format: (row) => ms(row.latency_ms?.p95) },
  { label: 'P99 延迟', delta: 'p99_pct', direction: 'bad-up', format: (row) => ms(row.latency_ms?.p99) },
]

const left = computed(() => data.value?.left || null)
const right = computed(() => data.value?.right || null)

const metricRows = computed(() => {
  if (!left.value || !right.value) return []
  return METRICS.map((item) => {
    const value = data.value.delta?.[item.delta]
    return {
      label: item.label,
      left: item.format(left.value),
      right: item.format(right.value),
      delta: value,
      direction: item.direction,
      deltaText: value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`,
    }
  })
})

const loadRows = computed(() => {
  if (!left.value || !right.value) return []
  return [
    { label: '负载模式', left: modeText(left.value), right: modeText(right.value) },
    { label: '并发', left: String(left.value.concurrency), right: String(right.value.concurrency) },
    { label: '版本标注', left: left.value.release_tag || '未标注', right: right.value.release_tag || '未标注' },
    { label: '环境', left: left.value.env_name || '不使用环境', right: right.value.env_name || '不使用环境' },
    { label: '用例', left: left.value.case_name || '—', right: right.value.case_name || '—' },
    { label: '开始时间', left: formatTime(left.value.started_at), right: formatTime(right.value.started_at) },
  ]
})

function modeText(row) {
  return row.load_mode === 'duration'
    ? `按持续时长 · ${row.duration_seconds} 秒`
    : `按总请求数 · ${row.total_requests} 次`
}

function num(value, digits = 0) {
  if (value == null) return '—'
  return digits ? Number(value).toFixed(digits) : String(value)
}

function ms(value) {
  return value == null ? '—' : `${value} ms`
}

function percent(value) {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

/** 染色只看「这个方向对用户是好是坏」，不看正负本身 */
function deltaClass(row) {
  if (row.delta == null || row.direction === 'neutral') return 'delta-flat'
  if (Math.abs(row.delta) < 0.01) return 'delta-flat'
  const worse = row.direction === 'bad-up' ? row.delta > 0 : row.delta < 0
  return worse ? 'delta-bad' : 'delta-good'
}

/** 条形宽度：变化越大越显眼，超过 100% 封顶 */
function barWidth(row) {
  if (row.delta == null) return 0
  return Math.min(100, Math.abs(row.delta))
}

async function load() {
  if (props.leftId == null || props.rightId == null) return
  loading.value = true
  errorText.value = ''
  data.value = null
  try {
    data.value = await comparePerfRuns(props.leftId, props.rightId)
  } catch (error) {
    errorText.value = error?.message || '对比失败'
  } finally {
    loading.value = false
  }
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-drawer v-model="visible" size="860px">
    <template #header>
      <div class="drawer-head">
        <span class="drawer-title">压测结果对比</span>
        <span v-if="left && right" class="drawer-sub">
          左 = 较早（#{{ left.run_id }}） · 右 = 较新（#{{ right.run_id }}）
        </span>
      </div>
    </template>

    <div v-loading="loading" class="compare-body">
      <p class="hint">
        变化率按 <span class="mono">(右 − 左) / 左</span> 计算；左侧为 0 或缺失时显示
        <span class="mono">—</span>，不编造百分比。
        <span class="delta-bad strong">红 = 劣化</span> ·
        <span class="delta-good strong">绿 = 改善</span>（TPS 上升是改善，不是劣化）
      </p>

      <el-alert
        v-if="data?.warning"
        type="warning"
        :closable="false"
        show-icon
        class="warning"
        :title="data.warning"
      />

      <el-alert
        v-if="errorText"
        type="error"
        :closable="false"
        show-icon
        :title="errorText"
      />

      <template v-if="data">
        <el-card shadow="never" class="block">
          <template #header><span class="block-title">负载与版本</span></template>
          <el-table :data="loadRows" size="small" class="table">
            <el-table-column prop="label" label="项" width="120" />
            <el-table-column label="左（较早）" min-width="180">
              <template #default="{ row }"><span class="mono">{{ row.left }}</span></template>
            </el-table-column>
            <el-table-column label="右（较新）" min-width="180">
              <template #default="{ row }"><span class="mono">{{ row.right }}</span></template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="block">
          <template #header><span class="block-title">指标对比</span></template>
          <el-table :data="metricRows" size="small" class="table">
            <el-table-column prop="label" label="指标" width="120" />
            <el-table-column label="左（较早）" width="150" align="right">
              <template #default="{ row }"><span class="mono">{{ row.left }}</span></template>
            </el-table-column>
            <el-table-column label="右（较新）" width="150" align="right">
              <template #default="{ row }"><span class="mono">{{ row.right }}</span></template>
            </el-table-column>
            <el-table-column label="变化" min-width="220">
              <template #default="{ row }">
                <div class="delta-cell" :class="deltaClass(row)">
                  <span class="delta-text mono">{{ row.deltaText }}</span>
                  <span class="delta-bar">
                    <i :style="{ width: `${barWidth(row)}%` }" />
                  </span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <p class="hint foot">
          只摆数据，不做「是否劣化」的阈值判定 —— 该不该放行是人来判断的。
          数据本身仍受能力边界约束：单机客户端、只校验状态码，长尾百分位是分桶近似。
        </p>
      </template>
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-head {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-1);
}

.drawer-sub {
  font-size: 12.5px;
  color: var(--text-3);
}

.compare-body {
  min-height: 200px;
}

.hint {
  margin: 0 0 12px;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-2);
}

.hint.foot {
  margin-top: 12px;
  color: var(--text-3);
}

.warning {
  margin-bottom: 12px;
}

.block {
  margin-bottom: 12px;
}

.block-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-1);
}

.table {
  width: 100%;
}

.delta-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.delta-text {
  min-width: 74px;
  font-weight: 600;
}

.delta-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-sunken);
  border-radius: 3px;
  overflow: hidden;
}

.delta-bar i {
  display: block;
  height: 100%;
  border-radius: 3px;
  background: currentColor;
  opacity: 0.55;
}

.delta-bad {
  color: var(--signal-fail, #d64545);
}

.delta-good {
  color: var(--signal-pass, #2e9e6b);
}

.delta-flat {
  color: var(--text-3);
}

.strong {
  font-weight: 600;
}
</style>
