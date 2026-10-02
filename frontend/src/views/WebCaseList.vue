<script setup>
/**
 * UI（Web）测试用例列表。
 *
 * 与接口测试列表是两条独立线路：列按 Web 用例的实际关注点来定
 * （步骤数、启用状态），没有方法 / URL / 断言这些接口专属列。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import RunCaseDialog from '@/components/RunCaseDialog.vue'
import { listProjects } from '@/api/project'
import { deleteCase, listCases } from '@/api/case'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const cases = ref([])
const loading = ref(false)

const filters = reactive({ priority: '', keyword: '' })

const runVisible = ref(false)
const runningCase = ref(null)

function stepCount(row) {
  return (row.steps_json || []).length
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
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

async function loadCases() {
  if (currentProjectId.value == null) {
    cases.value = []
    return
  }
  loading.value = true
  try {
    const params = { type: 'web' }
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    cases.value = await listCases(currentProjectId.value, params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.priority = ''
  filters.keyword = ''
  loadCases()
}

function openCreate() {
  router.push({ name: 'web-case-new', query: { project: currentProjectId.value } })
}

function openEdit(row) {
  router.push({
    name: 'web-case-edit',
    params: { id: row.id },
    query: { project: currentProjectId.value },
  })
}

function openRun(row) {
  runningCase.value = row
  runVisible.value = true
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除用例「${row.name}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deleteCase(row.id)
  ElMessage.success('已删除')
  await loadCases()
}

watch(currentProjectId, (id) => {
  syncProjectToQuery(id)
  loadCases()
})

onMounted(async () => {
  await loadProjects()
  await loadCases()
})
</script>

<template>
  <div>
    <PageHeader title="UI 测试" description="Web 用例：按步骤编排浏览器操作，支持变量传递与失败自动截图">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建 UI 用例
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="filter-bar">
        <el-select v-model="filters.priority" placeholder="全部优先级" clearable style="width: 140px">
          <el-option v-for="p in ['P0', 'P1', 'P2']" :key="p" :label="p" :value="p" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="按名称搜索"
          clearable
          style="width: 220px"
          @keyup.enter="loadCases"
        />
        <el-button type="primary" :icon="Search" @click="loadCases">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="cases" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="用例名称" min-width="220" />
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column label="步骤" width="90" align="center">
          <template #default="{ row }">
            <span class="mono" :class="{ 'is-zero': !stepCount(row) }">{{ stepCount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.enabled" type="success" size="small" effect="plain">启用</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">停用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.tags">{{ row.tags }}</span>
            <span v-else class="is-zero">—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="176" align="right" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openRun(row)">执行</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有 UI 用例，点击右上角「新建 UI 用例」开始" />
        </template>
      </el-table>
    </el-card>

    <RunCaseDialog
      v-model="runVisible"
      :case-row="runningCase"
      :project-id="currentProjectId"
      @executed="loadCases"
    />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.is-zero {
  color: var(--text-3);
}
</style>
