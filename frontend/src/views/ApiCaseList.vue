<script setup>
/**
 * 接口测试用例列表。
 *
 * 与 UI 测试列表（WebCaseList.vue）是两条独立线路：各有自己的菜单、筛选与新建入口，
 * 表格列也各按类型定制 —— 不再混排后用 v-if 挑列显示。
 * 新建/编辑跳转到全屏编辑页，项目 id 走 query 带过去，刷新页面也不丢。
 */
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

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

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

/** 项目 id 跟着 URL 走，从编辑页返回时能回到同一个项目 */
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
    const params = { type: 'api' }
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
  router.push({ name: 'api-case-new', query: { project: currentProjectId.value } })
}

function openEdit(row) {
  router.push({
    name: 'api-case-edit',
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
  <div class="page-stack">
    <PageHeader title="接口测试" description="接口用例：请求配置、断言、变量提取与数据驱动">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建接口用例
      </el-button>
    </PageHeader>

    <el-card class="card-filter" shadow="never">
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
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ cases.length }} 条接口用例</span>
        <el-button link :icon="Refresh" @click="loadCases">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="cases">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="用例名称" min-width="200" />
        <el-table-column prop="priority" label="优先级" width="90" />
        <el-table-column label="方法" width="100">
          <template #default="{ row }">
            <span class="mono method" :style="{ color: METHOD_COLORS[row.method] || '#4a5c64' }">
              {{ row.method }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="url" label="URL" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.url || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="断言" width="76" align="center">
          <template #default="{ row }">
            <span class="mono">{{ assertionCount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提取" width="76" align="center">
          <template #default="{ row }">
            <span class="mono" :class="{ 'is-zero': !extractCount(row) }">{{ extractCount(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数据文件" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.data_file" class="mono">{{ row.data_file }}</span>
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
          <el-empty description="还没有接口用例，点击右上角「新建接口用例」开始" />
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
.method {
  font-weight: 600;
}

.is-zero {
  color: var(--text-3);
}
</style>
