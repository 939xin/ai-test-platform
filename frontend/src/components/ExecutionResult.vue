<script setup>
import { computed } from 'vue'

import StatusTag from '@/components/StatusTag.vue'

const props = defineProps({
  // 一次执行记录（ExecutionOut）：{ status, duration_ms, result_json }
  execution: { type: Object, required: true },
})

// 提取到的变量：{变量名: 值}，没配提取规则时为空
const extracted = computed(() => props.execution.result_json?.extracted || {})
const extractErrors = computed(() => props.execution.result_json?.extract_errors || [])
const hasExtract = computed(
  () => Object.keys(extracted.value).length > 0 || extractErrors.value.length > 0,
)

function prettyJson(value) {
  if (value == null || value === '') return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <div class="exec-result">
    <div class="result-summary">
      <StatusTag :status="execution.status" />
      <span class="mono summary-item">耗时 {{ execution.duration_ms }} ms</span>
      <span v-if="execution.result_json?.error_msg" class="mono error">
        {{ execution.result_json.error_msg }}
      </span>
    </div>

    <el-tabs>
      <el-tab-pane label="请求">
        <div class="mono block">
          {{ execution.result_json?.request?.method }} {{ execution.result_json?.request?.url }}
        </div>
        <div class="label">请求头</div>
        <pre class="mono pre">{{ prettyJson(execution.result_json?.request?.headers) }}</pre>
        <template v-if="execution.result_json?.request?.body">
          <div class="label">请求体</div>
          <pre class="mono pre">{{ execution.result_json.request.body }}</pre>
        </template>
      </el-tab-pane>

      <el-tab-pane label="响应">
        <div class="label">状态码</div>
        <div class="mono block">{{ execution.result_json?.response?.status }}</div>
        <div class="label">响应体</div>
        <pre class="mono pre tall">{{ prettyJson(execution.result_json?.response?.body) }}</pre>
      </el-tab-pane>

      <el-tab-pane :label="`断言 (${execution.result_json?.assertions?.length || 0})`">
        <div
          v-for="(a, i) in execution.result_json?.assertions || []"
          :key="i"
          class="assert-item"
          :class="a.passed ? 'is-pass' : 'is-fail'"
        >
          <span class="assert-mark">{{ a.passed ? '✓' : '✗' }}</span>
          <span class="mono assert-text">{{ a.message }}</span>
        </div>
        <el-empty
          v-if="!execution.result_json?.assertions?.length"
          description="该用例没有断言条件"
          :image-size="60"
        />
      </el-tab-pane>

      <el-tab-pane v-if="hasExtract" :label="`变量 (${Object.keys(extracted).length})`">
        <div
          v-for="(value, name) in extracted"
          :key="name"
          class="extract-item"
          :class="value === null ? 'is-missing' : 'is-found'"
        >
          <span class="mono extract-name">{{ name }}</span>
          <span class="mono extract-value">{{ value === null ? '未匹配到值' : value }}</span>
        </div>
        <div v-for="(err, i) in extractErrors" :key="`e${i}`" class="extract-error">
          <span class="mono">{{ err }}</span>
        </div>
        <p class="extract-hint">
          这些变量可在后续用例里用 <code>${变量名}</code> 引用；提取失败不影响用例结果。
        </p>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
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

.extract-item {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 7px 10px;
  margin-bottom: 6px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 12.5px;
}

.extract-item.is-found {
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.extract-item.is-missing {
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

.extract-name {
  font-weight: 600;
  color: var(--text-1);
  flex-shrink: 0;
}

.extract-value {
  color: var(--text-2);
  word-break: break-all;
}

.extract-error {
  padding: 6px 10px;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--signal-warn);
}

.extract-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
}
</style>
