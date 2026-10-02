<script setup>
import { computed, ref, watch } from 'vue'

import ExecutionResult from '@/components/ExecutionResult.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listEnvironments } from '@/api/environment'
import { runCase, runCaseDataDriven, runWebCase } from '@/api/execution'
import { getWebStatus } from '@/api/web'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  caseRow: { type: Object, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'executed'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const environments = ref([])
const envId = ref(null)
const running = ref(false)
const result = ref(null)

// 数据驱动：用例绑了数据文件时，可以按行执行（仅接口用例）
const dataDriven = ref(false)
const batch = ref(null)
const activeRow = ref(0)

const isWeb = computed(() => props.caseRow?.type === 'web')
const hasDataFile = computed(() => !isWeb.value && Boolean(props.caseRow?.data_file))

// Web 用例的执行参数
const webInfo = ref(null)
const browser = ref('chrome')
const headless = ref(true)
const webTimeout = ref(300)
// 本机没有可用浏览器时禁用执行，并直接说明原因
const webBlocked = computed(() => isWeb.value && Boolean(webInfo.value) && !webInfo.value.available)

async function loadEnvironments() {
  if (props.projectId == null) return
  environments.value = await listEnvironments(props.projectId)
  envId.value = environments.value.length ? environments.value[0].id : null
}

async function loadWebInfo() {
  if (!isWeb.value || webInfo.value) return
  webInfo.value = await getWebStatus()
}

async function run() {
  running.value = true
  result.value = null
  batch.value = null
  activeRow.value = 0
  try {
    if (isWeb.value) {
      result.value = await runWebCase(props.caseRow.id, {
        env_id: envId.value,
        browser: browser.value,
        headless: headless.value,
        timeout: webTimeout.value,
      })
    } else if (dataDriven.value && hasDataFile.value) {
      batch.value = await runCaseDataDriven(props.caseRow.id, { env_id: envId.value, timeout: 30 })
    } else {
      result.value = await runCase(props.caseRow.id, { env_id: envId.value, timeout: 30 })
    }
    emit('executed')
  } finally {
    running.value = false
  }
}

/** 批量结果里的一行套上 ExecutionResult 期望的形状。 */
function asExecution(row) {
  return { status: row.status, duration_ms: row.duration_ms, result_json: row.result_json || {} }
}

/** 把该行的数据内容拼成 "列=值" 串，方便一眼看出这行跑的是什么。 */
function rowDataText(row) {
  const data = row.result_json?.row_data || {}
  const text = Object.entries(data)
    .map(([key, value]) => `${key}=${value}`)
    .join('  ')
  return text || '—'
}

watch(visible, (open) => {
  if (open) {
    result.value = null
    batch.value = null
    dataDriven.value = false
    loadEnvironments()
    loadWebInfo()
  }
})
</script>

<template>
  <el-dialog v-model="visible" title="执行用例" width="820px" top="6vh">
    <div v-if="caseRow" class="run-head">
      <div class="run-title">
        <span class="mono method">{{ isWeb ? 'WEB' : caseRow.method }}</span>
        <span class="run-name">{{ caseRow.name }}</span>
      </div>
      <div class="run-actions">
        <el-select v-model="envId" placeholder="不使用环境" clearable style="width: 170px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" :loading="running" :disabled="webBlocked" @click="run">
          开始执行
        </el-button>
      </div>
    </div>

    <div v-if="isWeb" class="web-bar">
      <el-select v-model="browser" style="width: 118px">
        <el-option label="Chrome" value="chrome" />
        <el-option label="Edge" value="edge" />
      </el-select>
      <el-checkbox v-model="headless">无头模式</el-checkbox>
      <el-input-number
        v-model="webTimeout"
        :min="10"
        :max="1800"
        :step="30"
        controls-position="right"
        style="width: 130px"
      />
      <span class="web-bar-text">秒（整条用例超时）</span>
    </div>

    <el-alert
      v-if="webBlocked"
      type="error"
      show-icon
      :closable="false"
      class="web-blocked"
      :title="`本机没有可用的浏览器，无法执行：${webInfo.error}`"
    />

    <div v-if="hasDataFile" class="data-driven-bar">
      <el-switch v-model="dataDriven" />
      <span class="data-driven-text">
        按数据文件逐行执行
        <span class="mono data-file">{{ caseRow.data_file }}</span>
      </span>
    </div>

    <el-empty v-if="!result && !batch && !running" description="选择环境后点击「开始执行」" :image-size="80" />
    <div v-if="running" class="running-hint">
      {{
        isWeb
          ? '正在启动浏览器并执行步骤，首次运行需下载驱动，可能较慢…'
          : dataDriven && hasDataFile
            ? '正在逐行执行…'
            : '正在请求接口…'
      }}
    </div>

    <ExecutionResult v-if="result" :execution="result" />

    <div v-if="batch">
      <div class="batch-summary">
        <span class="mono">共 {{ batch.total }} 行</span>
        <span class="summary-item">通过 {{ batch.passed }}</span>
        <span class="summary-item" :class="{ 'is-bad': batch.failed > 0 }">失败 {{ batch.failed }}</span>
      </div>

      <el-table :data="batch.rows" size="small" border highlight-current-row
                @current-change="(row) => (activeRow = batch.rows.indexOf(row))">
        <el-table-column label="行" width="60" align="center">
          <template #default="{ row }">
            <span class="mono">{{ row.result_json?.row_index }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="数据行" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono muted">{{ rowDataText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.duration_ms }} ms</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="batch.rows[activeRow]" class="batch-detail">
        <div class="label">第 {{ batch.rows[activeRow].result_json?.row_index }} 行明细</div>
        <ExecutionResult :execution="asExecution(batch.rows[activeRow])" />
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.run-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 14px;
}

.run-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.method {
  font-weight: 700;
  color: var(--brand-700);
}

.run-name {
  font-weight: 600;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.running-hint {
  padding: 30px 0;
  text-align: center;
  color: var(--text-3);
}

.data-driven-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--brand-100);
  border: 1px solid #b3d6dd;
  border-radius: var(--radius);
}

.web-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--brand-100);
  border: 1px solid #b3d6dd;
  border-radius: var(--radius);
}

.web-bar-text {
  font-size: 12.5px;
  color: var(--text-2);
}

.web-blocked {
  margin-bottom: 12px;
}

.data-driven-text {
  font-size: 12.5px;
  color: var(--text-2);
}

.data-file {
  color: var(--brand-700);
  font-weight: 600;
}

.batch-summary {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--text-2);
}

.batch-summary .is-bad {
  color: var(--signal-fail);
}

.batch-detail {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.batch-detail .label {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--text-3);
}

.muted {
  color: var(--text-3);
}
</style>
