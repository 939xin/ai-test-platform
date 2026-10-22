<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { listEnvironments } from '@/api/environment'
import { runPerfTask } from '@/api/perf'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  taskRow: { type: Object, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'started'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const environments = ref([])
const envId = ref(null)
const confirmed = ref(false)
const running = ref(false)

const loadText = computed(() => {
  const row = props.taskRow
  if (!row) return ''
  if (row.load_mode === 'duration') {
    return `${row.concurrency} 并发 · 持续 ${row.duration_seconds} 秒`
  }
  return `${row.concurrency} 并发 · 共 ${row.total_requests} 个请求`
})

async function load() {
  if (props.projectId == null) return
  environments.value = await listEnvironments(props.projectId)
  envId.value = props.taskRow?.env_id ?? null
  confirmed.value = false
}

async function start() {
  if (!confirmed.value || !props.taskRow) return
  running.value = true
  try {
    const result = await runPerfTask(props.taskRow.id, {
      env_id: envId.value,
      authorization_confirmed: true,
    })
    ElMessage.success(`压测已启动（运行 #${result.run_id}）`)
    emit('started', result.run_id)
    visible.value = false
  } finally {
    running.value = false
  }
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-dialog v-model="visible" title="启动压测" width="620px" top="8vh">
    <template v-if="taskRow">
      <div class="target">
        <div class="target-name">{{ taskRow.name }}</div>
        <div class="target-url mono">
          <span class="method">{{ taskRow.method || 'GET' }}</span>
          {{ taskRow.url || '（未填 URL）' }}
        </div>
      </div>

      <el-descriptions :column="2" border size="small" class="meta">
        <el-descriptions-item label="负载">{{ loadText }}</el-descriptions-item>
        <el-descriptions-item label="目标 RPS">
          <span class="mono">{{ taskRow.target_rps || '不限速' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="接口用例">{{ taskRow.case_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="环境">
          <el-select v-model="envId" placeholder="不使用环境" clearable size="small" style="width: 170px">
            <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="warning"
        title="压测会向目标系统发送真实流量，可能影响其可用性"
      >
        <template #default>
          请仅对你已获得授权的系统使用。运行期间可随时点击「停止」，但在途请求最多还要等待一个请求超时。
        </template>
      </el-alert>

      <el-checkbox v-model="confirmed" class="confirm">
        我确认已获得对该系统的压测授权，并了解压测可能对目标系统造成影响
      </el-checkbox>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :disabled="!confirmed" :loading="running" @click="start">
        开始压测
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.target {
  padding: 12px 14px;
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
  margin-bottom: 14px;
}

.target-name {
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 6px;
}

.target-url {
  font-size: 12.5px;
  color: var(--text-2);
  word-break: break-all;
}

.method {
  display: inline-block;
  margin-right: 6px;
  padding: 0 5px;
  border-radius: 3px;
  background: var(--brand-100);
  color: var(--brand-700);
  font-weight: 600;
}

.meta {
  margin-bottom: 14px;
}

.warning {
  margin-bottom: 14px;
}

.confirm {
  display: block;
  white-space: normal;
  height: auto;
  line-height: 1.7;
}
</style>
