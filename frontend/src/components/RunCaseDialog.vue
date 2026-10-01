<script setup>
import { computed, ref, watch } from 'vue'

import StatusTag from '@/components/StatusTag.vue'
import { listEnvironments } from '@/api/environment'
import { runCase } from '@/api/execution'

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

async function loadEnvironments() {
  if (props.projectId == null) return
  environments.value = await listEnvironments(props.projectId)
  envId.value = environments.value.length ? environments.value[0].id : null
}

async function run() {
  running.value = true
  result.value = null
  try {
    result.value = await runCase(props.caseRow.id, { env_id: envId.value, timeout: 30 })
    emit('executed')
  } finally {
    running.value = false
  }
}

function prettyJson(value) {
  if (value == null || value === '') return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

watch(visible, (open) => {
  if (open) {
    result.value = null
    loadEnvironments()
  }
})
</script>

<template>
  <el-dialog v-model="visible" title="执行用例" width="820px" top="6vh">
    <div v-if="caseRow" class="run-head">
      <div class="run-title">
        <span class="mono method">{{ caseRow.method }}</span>
        <span class="run-name">{{ caseRow.name }}</span>
      </div>
      <div class="run-actions">
        <el-select v-model="envId" placeholder="不使用环境" clearable style="width: 170px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" :loading="running" @click="run">开始执行</el-button>
      </div>
    </div>

    <el-empty v-if="!result && !running" description="选择环境后点击「开始执行」" :image-size="80" />
    <div v-if="running" class="running-hint">正在请求接口…</div>

    <div v-if="result" class="result">
      <div class="result-summary">
        <StatusTag :status="result.status" />
        <span class="mono summary-item">耗时 {{ result.duration_ms }} ms</span>
        <span v-if="result.result_json?.error_msg" class="mono error">
          {{ result.result_json.error_msg }}
        </span>
      </div>

      <el-tabs>
        <el-tab-pane label="请求">
          <div class="mono block">{{ result.result_json?.request?.method }} {{ result.result_json?.request?.url }}</div>
          <div class="label">请求头</div>
          <pre class="mono pre">{{ prettyJson(result.result_json?.request?.headers) }}</pre>
          <template v-if="result.result_json?.request?.body">
            <div class="label">请求体</div>
            <pre class="mono pre">{{ result.result_json.request.body }}</pre>
          </template>
        </el-tab-pane>

        <el-tab-pane label="响应">
          <div class="label">状态码</div>
          <div class="mono block">{{ result.result_json?.response?.status }}</div>
          <div class="label">响应体</div>
          <pre class="mono pre tall">{{ prettyJson(result.result_json?.response?.body) }}</pre>
        </el-tab-pane>

        <el-tab-pane :label="`断言 (${result.result_json?.assertions?.length || 0})`">
          <div
            v-for="(a, i) in result.result_json?.assertions || []"
            :key="i"
            class="assert-item"
            :class="a.passed ? 'is-pass' : 'is-fail'"
          >
            <span class="assert-mark">{{ a.passed ? '✓' : '✗' }}</span>
            <span class="mono assert-text">{{ a.message }}</span>
          </div>
          <el-empty
            v-if="!result.result_json?.assertions?.length"
            description="该用例没有断言条件"
            :image-size="60"
          />
        </el-tab-pane>
      </el-tabs>
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

.result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.summary-item {
  font-size: 13px;
  color: var(--text-2);
}

.error {
  font-size: 12px;
  color: var(--signal-fail);
}

.label {
  margin: 10px 0 4px;
  font-size: 12px;
  color: var(--text-3);
}

.block {
  font-size: 13px;
  color: var(--text-1);
  word-break: break-all;
}

.pre {
  margin: 0;
  padding: 10px;
  max-height: 200px;
  overflow: auto;
  font-size: 12.5px;
  line-height: 1.55;
  background: #f7f9fa;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  white-space: pre-wrap;
  word-break: break-all;
}

.pre.tall {
  max-height: 300px;
}

.assert-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 7px 10px;
  margin-bottom: 6px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 12.5px;
}

.assert-item.is-pass {
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
  color: #1f6d4a;
}

.assert-item.is-fail {
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
  color: #a12f2f;
}

.assert-mark {
  font-weight: 700;
}
</style>
