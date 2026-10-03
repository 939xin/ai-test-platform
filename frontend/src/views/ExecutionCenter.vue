<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
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
import PagePagination from '@/components/PagePagination.vue'
import ExecutionResult from '@/components/ExecutionResult.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listProjects } from '@/api/project'
import { getExecution, getExecutionStats, listExecutions } from '@/api/execution'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const executions = ref([])
const loading = ref(false)

// 分页状态。total 是「筛选后的全部条数」，由后端返回，不是 executions.length
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

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

/**
 * 统计卡的数据，走专门的统计接口 —— 统计的是整个项目，与分页无关。
 *
 * 原来是对当前加载的那一页 reduce 出来的，分页之后会变成「翻一页数字就变」，
 * 所以口径必须落在后端。
 *
 * 不把状态筛选传给它：四张卡在筛选条**上方**，语义是项目总览；而且按状态筛完
 * 之后「通过率」只可能是 0% 或 100%，那张卡就没意义了。
 * 若要让卡片跟着状态筛选走，把 filters.status 一起传过去即可。
 */
const stats = ref({ total: 0, passed: 0, failed: 0 })

// 通过率为空时显示「—」，别显示 0% —— 一条记录都没有时 0% 是误导
const passRate = computed(() => {
  if (!stats.value.total) return '—'
  return `${((stats.value.passed / stats.value.total) * 100).toFixed(1)}%`
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
    if (filters.status) params.status = filters.status
    const data = await listExecutions(params)
    executions.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  if (currentProjectId.value == null) {
    stats.value = { total: 0, passed: 0, failed: 0 }
    return
  }
  stats.value = await getExecutionStats({ project_id: currentProjectId.value })
}

/** 列表和统计卡一起刷 —— 只刷一个会出现「卡片和表格对不上」。 */
async function refresh() {
  await Promise.all([loadExecutions(), loadStats()])
}

/** 状态筛选变了就回到第 1 页，再查。
 *
 * 不重置页码的话，可能停在一个新条件下根本不存在的页上，
 * 用户看到的是一张空表，会以为没数据。
 */
function search() {
  page.value = 1
  return refresh()
}

/** 分页条回调：页码和每页条数由组件一次给全，避免两者先后生效导致多查一次。 */
function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadExecutions()
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

function resetFilters() {
  filters.status = ''
  return search()
}

// 换项目不走 watch，走 el-select 的 @change（见模板）。
// watch 会在 loadProjects() 给 select 赋初值时也触发一次，加上 onMounted 里
// 那句显式查询，开局就查了两遍 —— 请求面板里能看到两条一模一样的。
// @change 只有用户真的选了才发，程序赋值不发。
onMounted(async () => {
  await loadProjects()
  await refresh()
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
        @change="search"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button :icon="Refresh" @click="refresh">刷新</el-button>
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
          <div class="mono stat-value">{{ stats.passed }}</div>
        </div>
      </el-card>
      <el-card class="stat-card" shadow="never">
        <span class="stat-icon is-fail"><el-icon :size="18"><WarningFilled /></el-icon></span>
        <div class="stat-text">
          <div class="stat-label">失败 / 错误</div>
          <div class="mono stat-value">{{ stats.failed }}</div>
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
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ total }} 条记录</span>
        <el-button link :icon="Refresh" @click="refresh">刷新</el-button>
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

      <PagePagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @change="onPageChange"
      />
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
