<script setup>
import { computed, ref, watch } from 'vue'

import StatusTag from '@/components/StatusTag.vue'
import ExecutionResult from '@/components/ExecutionResult.vue'
import { listEnvironments } from '@/api/environment'
import { runPlan } from '@/api/plan'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  planRow: { type: Object, default: null },
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
// 展开的用例：默认只展开没通过的，通过的收起来，免得一屏铺不下
const activeNames = ref([])

async function loadEnvironments() {
  if (props.projectId == null) return
  environments.value = await listEnvironments(props.projectId)
  // 默认沿用计划绑定的环境；计划没绑就落到第一个
  envId.value = props.planRow?.env_id ?? (environments.value.length ? environments.value[0].id : null)
}

async function run() {
  running.value = true
  result.value = null
  try {
    result.value = await runPlan(props.planRow.id, { env_id: envId.value })
    activeNames.value = result.value.cases.filter((c) => c.status !== 'pass').map((c) => c.id)
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
  <el-dialog v-model="visible" title="执行计划" width="900px" top="6vh">
    <div v-if="planRow" class="run-head">
      <div class="run-title">
        <span class="run-name">{{ planRow.name }}</span>
        <span class="muted">共 {{ planRow.case_count }} 条用例</span>
      </div>
      <div class="run-actions">
        <el-select v-model="envId" placeholder="不使用环境" clearable style="width: 170px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" :loading="running" @click="run">开始执行</el-button>
      </div>
    </div>

    <el-empty v-if="!result && !running" description="选择环境后点击「开始执行」" :image-size="80" />
    <div v-if="running" class="running-hint">
      正在逐条执行用例{{ planRow?.case_count ? `（共 ${planRow.case_count} 条）` : '' }}，含 Web 用例时会慢一些…
    </div>

    <div v-if="result">
      <div class="summary">
        <StatusTag :status="result.status" />
        <span class="mono">通过 {{ result.passed }}/{{ result.total }}</span>
        <span v-if="result.skipped" class="mono muted">停用跳过 {{ result.skipped }}</span>
        <span class="mono muted">总耗时 {{ result.total_duration_ms }} ms</span>
      </div>

      <el-collapse v-model="activeNames">
        <el-collapse-item v-for="c in result.cases" :key="c.id" :name="c.id">
          <template #title>
            <StatusTag :status="c.status" />
            <span class="case-name">{{ c.case_name }}</span>
            <span class="mono muted">{{ c.duration_ms }} ms</span>
          </template>
          <ExecutionResult :execution="c" />
        </el-collapse-item>
      </el-collapse>
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

.case-name {
  flex: 1;
  margin-left: 8px;
  font-weight: 600;
  color: var(--text-1);
}

.muted {
  font-size: 12.5px;
  color: var(--text-3);
}
</style>
