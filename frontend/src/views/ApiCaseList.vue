<script setup>
/**
 * 接口测试用例列表。
 *
 * 与 UI 测试列表（WebCaseList.vue）是两条独立线路：各有自己的菜单、筛选与新建入口，
 * 表格列也各按类型定制 —— 不再混排后用 v-if 挑列显示。
 * 新建/编辑跳转到全屏编辑页，项目 id 走 query 带过去，刷新页面也不丢。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

import CaseBatchActions from '@/components/CaseBatchActions.vue'
import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import RunCaseDialog from '@/components/RunCaseDialog.vue'
import { listProjects } from '@/api/project'
import { batchCases, cloneCase, deleteCase, listCaseTags, listCases } from '@/api/case'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const cases = ref([])
const loading = ref(false)

// 分页状态。total 是「筛选后的全部条数」，由后端返回，不是 cases.length
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// enabled 用 '' / true / false 三态：'' 表示「全部」，不要用 false 兼职表示「全部」
const filters = reactive({ priority: '', keyword: '', tag: [], enabled: '' })

// 标签候选按项目拉，只来自后端（当前页只有 20 条，从页面上凑不全）
const tagOptions = ref([])

// 批量操作：勾选只在当前页生效，翻页后 el-table 会自动清空
const selectedIds = ref([])
const batchLoading = ref(false)

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

/** 标签候选：跟项目绑定，换项目要重拉；筛选条件变化不影响它。 */
async function loadTags() {
  tagOptions.value = currentProjectId.value == null
    ? []
    : await listCaseTags(currentProjectId.value, 'api')
}

async function loadCases() {
  // 列表重查后勾选就没有意义了（旧 id 可能已经不在结果里），直接清空
  selectedIds.value = []
  if (currentProjectId.value == null) {
    cases.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params = {
      type: 'api',
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    }
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.enabled !== '') params.enabled = filters.enabled
    if (filters.tag.length) params.tag = filters.tag
    const data = await listCases(currentProjectId.value, params)
    cases.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

/** 筛选条件或项目变了就回到第 1 页，再查。
 *
 * 不重置页码的话，可能停在一个新条件下根本不存在的页上（比如原来在第 5 页、
 * 筛选后只剩 3 条），用户看到的是一张空表，会以为没数据。
 */
function search() {
  page.value = 1
  return loadCases()
}

/** 分页条回调：页码和每页条数由组件一次给全，避免两者先后生效导致多查一次。 */
function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadCases()
}

function resetFilters() {
  filters.priority = ''
  filters.keyword = ''
  filters.tag = []
  filters.enabled = ''
  search()
}

function onSelectionChange(rows) {
  selectedIds.value = rows.map((row) => row.id)
}

/** 批量操作：整批成功或整批不动，后端已拒绝跨项目。 */
async function runBatch(action) {
  const label = { enable: '启用', disable: '停用', delete: '删除' }[action]
  if (action === 'delete') {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 条用例？删除后不可恢复。`,
      '批量删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  }
  batchLoading.value = true
  try {
    const { affected } = await batchCases({ action, case_ids: selectedIds.value })
    ElMessage.success(`已${label} ${affected} 条用例`)
    // 删的正好是本页最后几条时往前退一页，否则会停在一张空表上
    if (action === 'delete' && affected >= cases.value.length && page.value > 1) {
      page.value -= 1
    }
    await loadCases()
    // 状态变了，标签候选本身不变，但条数会变；顺带刷新成本很低
    await loadTags()
  } finally {
    batchLoading.value = false
  }
}

/** 克隆：副本是停用状态，避免被计划误跑。 */
async function cloneRow(row) {
  await cloneCase(row.id)
  ElMessage.success(`已克隆「${row.name}」，副本默认停用`)
  await loadCases()
  await loadTags()
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
  // 删掉的是本页最后一条时往前退一页，否则会停在一张空表上
  if (cases.value.length === 1 && page.value > 1) page.value -= 1
  await loadCases()
}

/** 换项目：把项目 id 同步到 URL（从编辑页返回时能回到同一个项目），再回第 1 页查。
 *
 * 不走 watch(currentProjectId)：loadProjects() 给 select 赋初值时也会触发 watch，
 * 加上 onMounted 里那句显式查询，开局就查了两遍（请求面板里两条一模一样）。
 * el-select 的 @change 只有用户真的选了才发，程序赋值不发。
 */
function onProjectChange(id) {
  syncProjectToQuery(id)
  // 标签候选是按项目取的，换项目必须重拉，否则筛选器里还留着上一个项目的标签
  loadTags()
  search()
}

onMounted(async () => {
  await loadProjects()
  await Promise.all([loadCases(), loadTags()])
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
        @change="onProjectChange"
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
          @keyup.enter="search"
        />
        <el-select
          v-model="filters.tag"
          multiple
          collapse-tags
          collapse-tags-tooltip
          filterable
          clearable
          placeholder="全部标签（可多选）"
          style="width: 220px"
          :no-data-text="'本项目还没有标签'"
        >
          <el-option v-for="t in tagOptions" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select v-model="filters.enabled" placeholder="全部状态" clearable style="width: 130px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ total }} 条接口用例</span>
        <el-button link :icon="Refresh" @click="loadCases">刷新</el-button>
      </div>

      <CaseBatchActions
        :selected-ids="selectedIds"
        :loading="batchLoading"
        @action="runBatch"
      />

      <el-table v-loading="loading" :data="cases" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="46" />
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
        <el-table-column prop="tags" label="标签" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.tags">{{ row.tags }}</span>
            <span v-else class="is-zero">—</span>
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
        <el-table-column label="操作" width="220" align="right" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openRun(row)">执行</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link @click="cloneRow(row)">克隆</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有接口用例，点击右上角「新建接口用例」开始" />
        </template>
      </el-table>

      <PagePagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @change="onPageChange"
      />
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
