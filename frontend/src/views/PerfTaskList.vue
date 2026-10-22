<script setup>
/**
 * 性能测试任务列表。
 *
 * 任务只保存压测配置；真正跑起来是后台线程，进度与结果在「运行记录 / 运行详情」里看。
 * 这样调整并发、重复执行都不会把一屏结果塞进列表页。
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import PerfTaskEditorDrawer from '@/components/PerfTaskEditorDrawer.vue'
import RunPerfDialog from '@/components/RunPerfDialog.vue'
import { listProjects } from '@/api/project'
import { deletePerfTask, listPerfTasks } from '@/api/perf'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const tasks = ref([])
const loading = ref(false)

const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const drawerVisible = ref(false)
const editingId = ref(null)

const runVisible = ref(false)
const runningTask = ref(null)

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

function loadText(row) {
  return row.load_mode === 'duration'
    ? `${row.concurrency} 并发 · ${row.duration_seconds} 秒`
    : `${row.concurrency} 并发 · ${row.total_requests} 次`
}

function syncProjectToQuery(id) {
  if (id != null) router.replace({ query: { ...route.query, project: id } })
}

async function loadProjects() {
  projects.value = await listProjects()
  const fromQuery = Number(route.query.project)
  if (fromQuery && projects.value.some((p) => p.id === fromQuery)) {
    currentProjectId.value = fromQuery
  } else if (projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadTasks() {
  if (currentProjectId.value == null) {
    tasks.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await listPerfTasks(currentProjectId.value, {
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    tasks.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

/** 换项目回第 1 页，否则会停在新项目根本不存在的页码上 */
function onProjectChange() {
  syncProjectToQuery(currentProjectId.value)
  page.value = 1
  return loadTasks()
}

function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadTasks()
}

function openCreate() {
  editingId.value = null
  drawerVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  drawerVisible.value = true
}

function openRun(row) {
  runningTask.value = row
  runVisible.value = true
}

function openRuns() {
  router.push({ name: 'perf-runs', query: { project: currentProjectId.value ?? undefined } })
}

function onStarted(runId) {
  router.push({ name: 'perf-run-detail', params: { runId } })
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除压测任务「${row.name}」？已有的运行记录会保留。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deletePerfTask(row.id)
  ElMessage.success('已删除')
  if (tasks.value.length === 1 && page.value > 1) page.value -= 1
  await loadTasks()
}

onMounted(async () => {
  await loadProjects()
  await loadTasks()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="性能测试" description="对接口用例发起真实并发流量，观察吞吐、延迟分布与错误率">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
        @change="onProjectChange"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button :icon="VideoPlay" @click="openRuns">运行记录</el-button>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建任务
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ total }} 个压测任务</span>
        <el-button link :icon="Refresh" @click="loadTasks">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="tasks">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="任务名称" min-width="170" show-overflow-tooltip />
        <el-table-column label="版本" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.release_tag" class="mono">{{ row.release_tag }}</span>
            <span v-else class="muted">未标注</span>
          </template>
        </el-table-column>
        <el-table-column label="目标接口" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.case_id" class="mono target">
              <span class="method">{{ row.method || 'GET' }}</span>{{ row.url || '（未填 URL）' }}
            </span>
            <span v-else class="muted">用例已删除</span>
          </template>
        </el-table-column>
        <el-table-column label="负载" width="150">
          <template #default="{ row }">
            <span class="mono">{{ loadText(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="目标 RPS" width="100" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.target_rps || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="环境" width="120">
          <template #default="{ row }">
            <span v-if="row.env_name">{{ row.env_name }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="right" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openRun(row)">运行</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              link
              @click="router.push({ name: 'perf-runs', query: { project: currentProjectId, task: row.id } })"
            >记录</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有压测任务。先准备一条接口用例，再点右上角「新建任务」" />
        </template>
      </el-table>

      <PagePagination :page="page" :page-size="pageSize" :total="total" @change="onPageChange" />
    </el-card>

    <PerfTaskEditorDrawer
      v-model="drawerVisible"
      :task-id="editingId"
      :project-id="currentProjectId"
      @saved="loadTasks"
    />

    <RunPerfDialog
      v-model="runVisible"
      :task-row="runningTask"
      :project-id="currentProjectId"
      @started="onStarted"
    />
  </div>
</template>

<style scoped>
.muted {
  color: var(--text-3);
}

.target {
  font-size: 12.5px;
  color: var(--text-2);
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
</style>
