<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CircleCheck,
  DataLine,
  Refresh,
  Search,
  TrendCharts,
  WarningFilled,
} from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import ExecutionResult from '@/components/ExecutionResult.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listProjects } from '@/api/project'
import { getExecution, listExecutions } from '@/api/execution'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const executions = ref([])
const loading = ref(false)

const filters = reactive({ status: '' })

const detailVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

const STATUS_OPTIONS = [
  { label: '通过', value: 'pass' },
  { label: '失败', value: 'fail' },
  { label: '错误', value: 'error' },
  { label: '运行中', value: 'running' },
]

// 统计只针对当前加载的这一页记录 —— limit 内有多少条就是多少条
const stats = computed(() => {
  const pass = executions.value.filter((e) => e.status === 'pass').length
  const fail = executions.value.filter((e) => e.status === 'fail' || e.status === 'error').length
  return { total: executions.value.length, pass, fail }
})

// 通过率为空时显示「—」，别显示 0% —— 一条记录都没有时 0% 是误导
const passRate = computed(() => {
  if (!stats.value.total) return '—'
  return `${((stats.value.pass / stats.value.total) * 100).toFixed(1)}%`
})

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function loadProjects() {
  projects.value = await listProjects()
  if (currentProjectId.value == null && projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadExecutions() {
  if (currentProjectId.value == null) {
    executions.value = []
    return
  }
  loading.value = true
  try {
    const params = { limit: 100 }
    if (filters.status) params.status = filters.status
    executions.value = await listExecutions({ project_id: currentProjectId.value, ...params })
  } finally {
    loading.value = false
  }
}

async function openDetailById(executionId) {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getExecution(executionId)
  } finally {
    detailLoading.value = false
  }
}

function openDetail(row) {
  return openDetailById(row.id)
}

/** 在缺陷详情里点「查看执行」会跳过来，带 ?open=<execution_id>，直接打开那次执行。 */
function openFromQuery() {
  const openId = Number(route.query.open)
  if (!openId) return
  openDetailById(openId)

  // 清掉 open，免得关掉抽屉后一刷新又弹出来
  const query = {}
  if (currentProjectId.value != null) query.project = String(currentProjectId.value)
  router.replace({ query })
}

/** 提完缺陷跳到缺陷页并打开那条缺陷；项目 id 一起带过去，那边才知道查哪个项目。 */
function gotoDefect(defectId) {
  detailVisible.value = false
  router.push({
    name: 'defects',
    query: { open: defectId, project: detail.value?.project_id ?? currentProjectId.value },
  })
}

watch(currentProjectId, loadExecutions)

onMounted(async () => {
  await loadProjects()
  await loadExecutions()
  openFromQuery()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="执行中心" description="历史执行记录，点「查看」可看请求 / 响应 / 断言，或 Web 用例的步骤明细">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button :icon="Refresh" @click="loadExecutions">刷新</el-button>
    </PageHeader>

    <div class="stat-row">
      <el-card class="stat-card" shadow="never">
        <span class="stat-icon is-total"><el-icon :size="18"><DataLine /></el-icon></span>
        <div class="stat-text">
          <div class="stat-label">执行记录</div>
          <div class="mono stat-value">{{ stats.total }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <span class="stat-icon is-pass"><el-icon :size="18"><CircleCheck /></el-icon></span>
        <div class="stat-text">
          <div class="stat-label">通过</div>
          <div class="mono stat-value">{{ stats.pass }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <span class="stat-icon is-fail"><el-icon :size="18"><WarningFilled /></el-icon></span>
        <div class="stat-text">
          <div class="stat-label">失败 / 错误</div>
          <div class="mono stat-value">{{ stats.fail }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <span class="stat-icon is-rate"><el-icon :size="18"><TrendCharts /></el-icon></span>
        <div class="stat-text">
          <div class="stat-label">通过率</div>
          <div class="mono stat-value">{{ passRate }}</div>
        </div>
      </el-card>
    </div>

    <el-card class="card-filter" shadow="never">
      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
          <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="loadExecutions">查询</el-button>
        <el-button
          @click="
            () => {
              filters.status = ''
              loadExecutions()
            }
          "
        >
          重置
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ executions.length }} 条记录</span>
        <el-button link :icon="Refresh" @click="loadExecutions">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="executions">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="用例" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.case_name">{{ row.case_name }}</span>
            <span v-else class="deleted">已删除用例 #{{ row.case_id ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ row.duration_ms }} ms</span>
          </template>
        </el-table-column>
        <el-table-column label="执行时间" width="180">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有执行记录，到「用例管理」点执行后会出现在这里" />
        </template>
      </el-table>
    </el-card>

    <el-drawer
      v-model="detailVisible"
      :title="detail ? `执行详情 #${detail.id}` : '执行详情'"
      size="740px"
    >
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <div class="detail-head">
            <span class="detail-title">{{ detail.case_name || '已删除用例' }}</span>
            <span class="mono detail-time">{{ formatTime(detail.created_at) }}</span>
          </div>
          <ExecutionResult :execution="detail" @goto-defect="gotoDefect" />
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.stat-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
}

/* 图标底色区分三态，比原来那条左边的色条更像卡片 */
.stat-icon {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius);
}

.stat-icon.is-total {
  background: var(--brand-100);
  color: var(--brand-700);
}

.stat-icon.is-pass {
  background: var(--signal-pass-bg);
  color: var(--signal-pass);
}

.stat-icon.is-fail {
  background: var(--signal-fail-bg);
  color: var(--signal-fail);
}

.stat-icon.is-rate {
  background: var(--signal-warn-bg);
  color: var(--signal-warn);
}

.stat-label {
  font-size: 12.5px;
  color: var(--text-3);
}

.stat-value {
  margin-top: 2px;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text-1);
}

.deleted {
  color: var(--text-3);
}

.detail-body {
  min-height: 200px;
}

.detail-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
}

.detail-title {
  font-weight: 600;
  color: var(--text-1);
}

.detail-time {
  font-size: 12.5px;
  color: var(--text-3);
}
</style>
