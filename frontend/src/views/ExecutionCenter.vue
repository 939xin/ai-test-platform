<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import ExecutionResult from '@/components/ExecutionResult.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listProjects } from '@/api/project'
import { getExecution, listExecutions } from '@/api/execution'

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

async function openDetail(row) {
  detailVisible.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getExecution(row.id)
  } finally {
    detailLoading.value = false
  }
}

watch(currentProjectId, loadExecutions)

onMounted(async () => {
  await loadProjects()
  await loadExecutions()
})
</script>

<template>
  <div>
    <PageHeader title="执行中心" description="历史执行记录，点「查看」可看请求 / 响应 / 断言明细">
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
      <div class="stat-card">
        <div class="stat-label">当前列表执行数</div>
        <div class="mono stat-value">{{ stats.total }}</div>
      </div>
      <div class="stat-card is-pass">
        <div class="stat-label">通过</div>
        <div class="mono stat-value">{{ stats.pass }}</div>
      </div>
      <div class="stat-card is-fail">
        <div class="stat-label">失败 / 错误</div>
        <div class="mono stat-value">{{ stats.fail }}</div>
      </div>
    </div>

    <el-card shadow="never">
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

      <el-table v-loading="loading" :data="executions" stripe>
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
          <ExecutionResult :execution="detail" />
        </template>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.stat-row {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.stat-card {
  flex: 1;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid var(--border);
  border-left: 3px solid var(--brand-700);
  border-radius: var(--radius);
}

.stat-card.is-pass {
  border-left-color: var(--signal-pass);
}

.stat-card.is-fail {
  border-left-color: var(--signal-fail);
}

.stat-label {
  font-size: 12px;
  color: var(--text-3);
}

.stat-value {
  margin-top: 4px;
  font-size: 22px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text-1);
}

.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
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
