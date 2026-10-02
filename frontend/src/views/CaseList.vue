<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import CaseEditorDrawer from '@/components/CaseEditorDrawer.vue'
import RunCaseDialog from '@/components/RunCaseDialog.vue'
import { listProjects } from '@/api/project'
import { deleteCase, listCases } from '@/api/case'

const projects = ref([])
const currentProjectId = ref(null)
const cases = ref([])
const loading = ref(false)

const filters = reactive({ type: '', priority: '', keyword: '' })

const drawerVisible = ref(false)
const editingCaseId = ref(null)

const runVisible = ref(false)
const runningCase = ref(null)

// 请求方法用颜色区分，扫一眼就能看出用例构成
const METHOD_COLORS = {
  GET: '#2e9e6b',
  POST: '#16697a',
  PUT: '#d98c1f',
  PATCH: '#7a5cd9',
  DELETE: '#d64545',
  HEAD: '#7a8b94',
  OPTIONS: '#7a8b94',
}

function assertionCount(row) {
  return (row.assertions_json || []).length
}

function extractCount(row) {
  return (row.extract_json || []).length
}

function stepCount(row) {
  return (row.steps_json || []).length
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function loadProjects() {
  projects.value = await listProjects()
  if (currentProjectId.value == null && projects.value.length) {
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
    const params = {}
    if (filters.type) params.type = filters.type
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    cases.value = await listCases(currentProjectId.value, params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.type = ''
  filters.priority = ''
  filters.keyword = ''
  loadCases()
}

function openCreate() {
  editingCaseId.value = null
  drawerVisible.value = true
}

function openEdit(row) {
  editingCaseId.value = row.id
  drawerVisible.value = true
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

watch(currentProjectId, loadCases)

onMounted(async () => {
  await loadProjects()
  await loadCases()
})
</script>

<template>
  <div>
    <PageHeader title="用例管理" description="按项目、类型、优先级筛选；支持新建、编辑、删除">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建用例
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="filter-bar">
        <el-select v-model="filters.type" placeholder="全部类型" clearable style="width: 130px">
          <el-option label="接口" value="api" />
          <el-option label="Web UI" value="web" />
        </el-select>
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
        <el-table-column prop="name" label="用例名称" min-width="200" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <span class="mono type-chip">{{ row.type === 'api' ? '接口' : 'Web' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="步骤" width="76" align="center">
          <template #default="{ row }">
            <span v-if="row.type === 'web'" class="mono">{{ stepCount(row) }}</span>
            <span v-else class="mono is-zero">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column label="方法" width="100">
          <template #default="{ row }">
            <span
              v-if="row.type === 'api'"
              class="mono method"
              :style="{ color: METHOD_COLORS[row.method] || '#4a5c64' }"
            >
              {{ row.method }}
            </span>
            <span v-else class="mono is-zero">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="URL" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.type === 'api'" class="mono">{{ row.url || '—' }}</span>
            <span v-else class="is-zero">Web 用例的地址写在步骤里</span>
          </template>
        </el-table-column>
        <el-table-column label="断言" width="76" align="center">
          <template #default="{ row }">
            <span v-if="row.type === 'api'" class="mono">{{ assertionCount(row) }}</span>
            <span v-else class="mono is-zero">—</span>
          </template>
        </el-table-column>
        <el-table-column label="提取" width="76" align="center">
          <template #default="{ row }">
            <span v-if="row.type === 'api'" class="mono" :class="{ 'is-zero': !extractCount(row) }">
              {{ extractCount(row) }}
            </span>
            <span v-else class="mono is-zero">—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.updated_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="176" align="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openRun(row)">执行</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有用例，点击右上角「新建用例」开始" />
        </template>
      </el-table>
    </el-card>

    <CaseEditorDrawer
      v-model="drawerVisible"
      :case-id="editingCaseId"
      :project-id="currentProjectId"
      @saved="loadCases"
    />

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

.method {
  font-weight: 600;
}

.type-chip {
  font-size: 12px;
  color: var(--text-2);
}

.is-zero {
  color: var(--text-3);
}
</style>
