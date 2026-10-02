<script setup>
import { computed, ref, watch } from 'vue'

import ExecutionResult from '@/components/ExecutionResult.vue'
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

    <ExecutionResult v-if="result" :execution="result" />
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
</style>
