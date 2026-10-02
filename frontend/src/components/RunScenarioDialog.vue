<script setup>
import { computed, ref, watch } from 'vue'

import StatusTag from '@/components/StatusTag.vue'
import ExecutionResult from '@/components/ExecutionResult.vue'
import { listEnvironments } from '@/api/environment'
import { runScenario } from '@/api/scenario'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  scenarioRow: { type: Object, default: null },
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
const activeStep = ref(0)

async function loadEnvironments() {
  if (props.projectId == null) return
  environments.value = await listEnvironments(props.projectId)
  envId.value = environments.value.length ? environments.value[0].id : null
}

async function run() {
  running.value = true
  result.value = null
  activeStep.value = 0
  try {
    result.value = await runScenario(props.scenarioRow.id, { env_id: envId.value, timeout: 30 })
    emit('executed')
  } finally {
    running.value = false
  }
}

/** 步骤结果套上 ExecutionResult 期望的形状（{status, duration_ms, result_json}）。 */
function asExecution(step) {
  return { status: step.status, duration_ms: step.duration_ms, result_json: step.result || {} }
}

watch(visible, (open) => {
  if (open) {
    result.value = null
    loadEnvironments()
  }
})
</script>

<template>
  <el-dialog v-model="visible" title="执行场景" width="860px" top="6vh">
    <div v-if="scenarioRow" class="run-head">
      <div class="run-title">
        <span class="run-name">{{ scenarioRow.name }}</span>
        <span class="muted">共 {{ scenarioRow.step_count }} 步</span>
      </div>
      <div class="run-actions">
        <el-select v-model="envId" placeholder="不使用环境" clearable style="width: 170px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" :loading="running" @click="run">开始执行</el-button>
      </div>
    </div>

    <el-empty v-if="!result && !running" description="选择环境后点击「开始执行」" :image-size="80" />
    <div v-if="running" class="running-hint">正在逐步执行场景…</div>

    <div v-if="result">
      <div class="summary">
        <StatusTag :status="result.status" />
        <span class="mono muted">总耗时 {{ result.total_duration_ms }} ms</span>
      </div>

      <el-steps :active="activeStep" simple class="step-bar">
        <el-step
          v-for="(s, i) in result.steps"
          :key="i"
          :title="`${i + 1}. ${s.case_name}`"
          :status="s.status === 'pass' ? 'success' : s.status === 'fail' || s.status === 'error' ? 'error' : 'wait'"
          @click="activeStep = i"
        />
      </el-steps>

      <div v-for="(s, i) in result.steps" :key="i">
        <template v-if="i === activeStep">
          <div class="step-head">
            <span class="mono step-no">步骤 {{ s.step_order }}</span>
            <span class="step-name">{{ s.case_name }}</span>
            <StatusTag :status="s.status" />
            <span class="mono muted">{{ s.duration_ms }} ms</span>
          </div>

          <p v-if="s.note" class="note">{{ s.note }}</p>

          <div v-if="Object.keys(s.extracted || {}).length" class="extracted">
            <span class="extract-label">本步提取：</span>
            <span v-for="(v, k) in s.extracted" :key="k" class="mono extract-chip">
              {{ k }} = {{ v === null ? '未匹配' : v }}
            </span>
          </div>

          <ExecutionResult v-if="s.result" :execution="asExecution(s)" />
        </template>
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
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.run-name {
  font-weight: 600;
  color: var(--text-1);
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

.summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.step-bar {
  margin-bottom: 14px;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 8px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.step-no {
  font-size: 12px;
  color: var(--brand-700);
  font-weight: 600;
}

.step-name {
  font-weight: 600;
  color: var(--text-1);
}

.muted {
  font-size: 12.5px;
  color: var(--text-3);
}

.note {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: var(--signal-warn);
}

.extracted {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.extract-label {
  font-size: 12px;
  color: var(--text-3);
}

.extract-chip {
  padding: 1px 7px;
  font-size: 12px;
  color: var(--text-2);
  background: #eef2f3;
  border-radius: var(--radius);
  word-break: break-all;
}
</style>
