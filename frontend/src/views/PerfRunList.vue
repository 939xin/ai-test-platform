<script setup>
/**
 * 压测运行记录。
 *
 * 列表只展示摘要，完整指标在运行详情里。有活跃运行时每 3 秒自动刷新一次，
 * 全部结束就停下 —— 不要用一个永不停止的 setInterval 空转。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import PerfRunStatusTag from '@/components/PerfRunStatusTag.vue'
import { listProjects } from '@/api/project'
import {
  ACTIVE_PERF_STATUSES, deletePerfRun, listPerfRuns, listPerfTasks, stopPerfRun,
} from '@/api/perf'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const tasks = ref([])
const runs = ref([])
const loading = ref(false)

const statusFilter = ref('')
const taskFilter = ref(null)

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

let refreshTimer = null

const STATUS_OPTIONS = [
  { value: 'queued', label: '排队中' },
  { value: 'running', label: '运行中' },
  { value: 'stopping', label: '停止中' },
  { value: 'completed', label: '已完成' },
  { value: 'stopped', label: '已停止' },
  { value: 'aborted', label: '已熔断' },
  { value: 'failed', label: '失败' },
]

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

function loadText(row) {
  return row.load_mode === 'duration'
    ? `${row.concurrency} 并发 · ${row.duration_seconds} 秒`
    : `${row.concurrency} 并发 · ${row.total_requests} 次`
}

function progressText(row) {
  if (row.load_mode === 'duration') {
    return `${row.requests_done} 次 / ${row.duration_seconds}s`
  }
  return `${row.requests_done} / ${row.total_requests}`
}

function percent(value) {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

function loadProjects() {
  return listProjects().then((list) => {
    projects.value = list
    const fromQuery = Number(route.query.project)
    if (fromQuery && list.some((p) => p.id === fromQuery)) currentProjectId.value = fromQuery
    else if (list.length) currentProjectId.value = list[0].id
  })
}

async function loadTasks() {
  if (currentProjectId.value == null) {
    tasks.value = []
    return
  }
  const data = await listPerfTasks(currentProjectId.value, { limit: 200 })
  tasks.value = data.items
}

async function loadRuns() {
  clearTimeout(refreshTimer)
  if (currentProjectId.value == null) {
    runs.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params = {
      project_id: currentProjectId.value,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    }
    if (statusFilter.value) params.status = statusFilter.value
    if (taskFilter.value) params.task_id = taskFilter.value
    const data = await listPerfRuns(params)
    runs.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
  scheduleRefresh()
}

function scheduleRefresh() {
  clearTimeout(refreshTimer)
  if (runs.value.some((row) => ACTIVE_PERF_STATUSES.includes(row.status))) {
    refreshTimer = setTimeout(loadRuns, 3000)
  }
}

function syncProjectToQuery() {
  router.replace({
    query: {
      ...route.query,
      project: currentProjectId.value ?? undefined,
      task: taskFilter.value ?? undefined,
    },
  })
}

async function onProjectChange() {
  taskFilter.value = null
  page.value = 1
  syncProjectToQuery()
  await loadTasks()
  await loadRuns()
}

function onFilterChange() {
  page.value = 1
  syncProjectToQuery()
  return loadRuns()
}

function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadRuns()
}

function openDetail(row) {
  router.push({ name: 'perf-run-detail', params: { runId: row.id } })
}

async function stop(row) {
  await ElMessageBox.confirm(
    `停止运行 #${row.id}？在途请求最多还要等待一个请求超时。`,
    '停止压测',
    { type: 'warning', confirmButtonText: '停止', cancelButtonText: '取消' },
  )
  await stopPerfRun(row.id)
  ElMessage.success('已请求停止')
  await loadRuns()
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除运行记录 #${row.id}？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deletePerfRun(row.id)
  ElMessage.success('已删除')
  if (runs.value.length === 1 && page.value > 1) page.value -= 1
  await loadRuns()
}

onMounted(async () => {
  await loadProjects()
  const fromQueryTask = Number(route.query.task)
  if (fromQueryTask) taskFilter.value = fromQueryTask
  await loadTasks()
  await loadRuns()
})

onBeforeUnmount(() => clearTimeout(refreshTimer))
</script>

<template>
  <div class="page-stack">
    <PageHeader title="压测运行记录" description="每次压测的摘要指标；点「详情」看延迟分布与时间线">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 180px"
        @change="onProjectChange"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button @click="router.push({ name: 'perf' })">返回任务</el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <div class="filters">
          <el-select
            v-model="taskFilter"
            placeholder="全部任务"
            clearable
            style="width: 190px"
            @change="onFilterChange"
          >
            <el-option v-for="t in tasks" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <el-select
            v-model="statusFilter"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            @change="onFilterChange"
          >
            <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <span class="muted">共 {{ total }} 条运行记录</span>
        </div>
        <el-button link :icon="Refresh" @click="loadRuns">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="runs">
        <el-table-column prop="id" label="ID" width="64" />
        <el-table-column label="任务" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span>{{ row.task_name || '—' }}</span>
            <span v-if="row.task_id == null" class="muted">（任务已删除）</span>
          </template>
        </el-table-column>
        <el-table-column prop="case_name" label="用例" min-width="130" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }"><PerfRunStatusTag :status="row.status" /></template>
        </el-table-column>
        <el-table-column label="负载" width="140">
          <template #default="{ row }"><span class="mono">{{ loadText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="进度" width="110" align="right">
          <template #default="{ row }"><span class="mono">{{ progressText(row) }}</span></template>
        </el-table-column>
        <el-table-column label="成功率" width="88" align="right">
          <template #default="{ row }"><span class="mono">{{ percent(row.success_rate) }}</span></template>
        </el-table-column>
        <el-table-column label="TPS" width="76" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.tps_avg == null ? '—' : row.tps_avg.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="P95" width="88" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.p95_ms == null ? '—' : `${row.p95_ms} ms` }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }"><span class="mono">{{ row.duration_ms }} ms</span></template>
        </el-table-column>
        <el-table-column label="开始时间" width="168">
          <template #default="{ row }"><span class="mono">{{ formatTime(row.started_at || row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="right" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button
              v-if="ACTIVE_PERF_STATUSES.includes(row.status)"
              link
              type="warning"
              @click="stop(row)"
            >停止</el-button>
            <el-button
              v-else
              link
              type="danger"
              @click="remove(row)"
            >删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有压测运行记录，去「性能测试」里运行一个任务" />
        </template>
      </el-table>

      <PagePagination :page="page" :page-size="pageSize" :total="total" @change="onPageChange" />
    </el-card>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 10px;
}

.muted {
  color: var(--text-3);
  font-size: 12.5px;
}
</style>
