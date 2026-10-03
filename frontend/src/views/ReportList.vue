<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import StatusTag from '@/components/StatusTag.vue'
import { listProjects } from '@/api/project'
import { listExecutions } from '@/api/execution'
import { createReport, listReports, reportUrl } from '@/api/report'

const projects = ref([])
const currentProjectId = ref(null)
const executions = ref([])
const reports = ref([])
const loading = ref(false)
const generating = ref(false)

// 只给「历史报告」分页。上面那张勾选表**不能**分页 ——
// 报告要跨记录勾选，表头「全选」在分页下只选得到当前页，用户会以为全选了。
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 勾选中的执行记录 id
const selectedIds = ref([])

function openReport(filename) {
  window.open(reportUrl(filename), '_blank')
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
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
  // 这张表是勾选用的，不分页，只取最近的 100 条（后端上限 200）
  const data = await listExecutions({ project_id: currentProjectId.value, limit: 100 })
  executions.value = data.items
  selectedIds.value = []
}

async function loadReports() {
  loading.value = true
  try {
    const data = await listReports({
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    reports.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

/** 分页条回调：页码和每页条数由组件一次给全，避免两者先后生效导致多查一次。 */
function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadReports()
}

async function generate() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请先勾选要纳入报告的执行记录')
    return
  }
  generating.value = true
  try {
    const res = await createReport(currentProjectId.value, { execution_ids: selectedIds.value })
    ElMessage.success(`报告已生成：${res.filename}`)
    // 报告是按生成时间倒序的，新报告在第 1 页；停在原页码会看不到刚生成那份
    page.value = 1
    await loadReports()
    openReport(res.filename)
  } finally {
    generating.value = false
  }
}

async function onProjectChange() {
  await loadExecutions()
  await loadReports()
}

async function refresh() {
  await loadExecutions()
  await loadReports()
}

onMounted(async () => {
  await loadProjects()
  await refresh()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="测试报告" description="勾选执行记录生成 HTML 报告，可在新标签页打开">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
        @change="onProjectChange"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button :icon="Refresh" @click="refresh">刷新</el-button>
    </PageHeader>

    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">选择执行记录</span>
          <span class="card-hint">已选 {{ selectedIds.length }} / {{ executions.length }} 条</span>
        </div>
      </template>

      <el-table
        :data="executions"
        max-height="300"
        @selection-change="(rows) => (selectedIds = rows.map((r) => r.id))"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="用例" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.case_name">{{ row.case_name }}</span>
            <span v-else class="muted">已删除用例 #{{ row.case_id ?? '—' }}</span>
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
        <template #empty>
          <el-empty description="该项目还没有执行记录" :image-size="70" />
        </template>
      </el-table>

      <div class="actions">
        <span class="card-hint">勾选左侧复选框选择要纳入报告的执行记录（表头可全选）</span>
        <el-button
          type="primary"
          :loading="generating"
          :disabled="!selectedIds.length"
          @click="generate"
        >
          生成报告
        </el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span class="card-title">历史报告</span>
          <span class="card-hint">共 {{ total }} 份 · 输出目录 reports/platform/</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="reports">
        <el-table-column prop="filename" label="报告文件" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.filename }}</span>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="110" align="right">
          <template #default="{ row }">
            <span class="mono">{{ formatSize(row.size) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="生成时间" width="180">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openReport(row.filename)">打开</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有生成过报告" :image-size="70" />
        </template>
      </el-table>

      <PagePagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @change="onPageChange"
      />
    </el-card>
  </div>
</template>

<style scoped>
.card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-weight: 600;
  color: var(--text-1);
}

.card-hint {
  font-size: 12px;
  color: var(--text-3);
}

.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}

.muted {
  color: var(--text-3);
}
</style>
