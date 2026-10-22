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
// 默认带出任务上的版本标注，本次可改可清空 ——
// 新版本上线时忘了改任务的 tag，就是靠这一处兜住，避免历史记录标错版本
const releaseTag = ref('')
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
  releaseTag.value = props.taskRow?.release_tag || ''
  confirmed.value = false
}

async function start() {
  if (!confirmed.value || !props.taskRow) return
  running.value = true
  try {
    const result = await runPerfTask(props.taskRow.id, {
      env_id: envId.value,
      // 显式传（包括空串）：清空输入框 = 本次标注为「未标注」，
      // 不能靠「不传」来表达，否则会悄悄回落到任务上的旧版本号
      release_tag: releaseTag.value.trim(),
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

      <el-form label-width="90px" class="tag-form" @submit.prevent>
        <el-form-item label="版本标注">
          <el-input
            v-model="releaseTag"
            maxlength="64"
            clearable
            placeholder="默认带出任务上的版本，可改可清空"
            style="width: 320px"
          />
          <span class="hint inline">写进本次运行记录；清空表示本次未标注</span>
        </el-form-item>
      </el-form>

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
  margin-bottom: 10px;
}

.tag-form {
  margin-bottom: 6px;
}

.hint.inline {
  margin-left: 10px;
  font-size: 12px;
  color: var(--text-3);
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
