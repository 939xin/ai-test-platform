<script setup>
/**
 * UI（Web）测试用例列表。
 *
 * 与接口测试列表是两条独立线路：列按 Web 用例的实际关注点来定
 * （步骤数、启用状态），没有方法 / URL / 断言这些接口专属列。
 */
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import RunCaseDialog from '@/components/RunCaseDialog.vue'
import { listProjects } from '@/api/project'
import { deleteCase, listCases } from '@/api/case'
import { clearWebSession, getWebSession } from '@/api/webSession'

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

const filters = reactive({ priority: '', keyword: '' })

const runVisible = ref(false)
const runningCase = ref(null)

// 本项目当前的登录态（后端没存过就是 null）。只在**项目变化**时查 ——
// 换筛选条件、翻页都不会让它变，跟着查就是白发请求。
const webSession = ref(null)

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

async function loadWebSession() {
  if (currentProjectId.value == null) {
    webSession.value = null
    return
  }
  // 没有登录态时后端回 null，不是错误 —— 那是新项目的正常状态
  webSession.value = await getWebSession(currentProjectId.value)
}

async function clearSession() {
  await ElMessageBox.confirm(
    '清除后，「需要登录态」的用例会跑不通，直到重跑一次登录用例。确定清除？',
    '清除登录态',
    { type: 'warning', confirmButtonText: '清除', cancelButtonText: '取消' },
  )
  const { deleted } = await clearWebSession(currentProjectId.value)
  ElMessage.success(`已清除 ${deleted} 份登录态`)
  await loadWebSession()
}

async function loadCases() {
  if (currentProjectId.value == null) {
    cases.value = []
    total.value = 0
    return
  }
  loading.value = true
  try {
    const params = {
      type: 'web',
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    }
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
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
  search()
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
  search()
  loadWebSession()  // 登录态是按项目存的，换项目必须重查
}

onMounted(async () => {
  await loadProjects()
  await loadCases()
  await loadWebSession()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="UI 测试" description="Web 用例：按步骤编排浏览器操作，支持变量传递与失败自动截图">
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
        新建 UI 用例
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
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ total }} 条 UI 用例</span>
        <el-button link :icon="Refresh" @click="loadCases">刷新</el-button>
      </div>

      <!-- 登录态状态条：勾了「需要登录态」的用例跑不通时，第一件要看的就是这里 -->
      <div v-if="currentProjectId != null" class="session-bar">
        <span class="session-label">登录态</span>
        <template v-if="webSession">
          <span class="mono session-text">
            来自「{{ webSession.source_case_name || '已删除的用例' }}」·
            cookie {{ webSession.cookie_count }} 项 ·
            localStorage {{ webSession.local_storage_keys.length }} 个键 ·
            更新于 {{ formatTime(webSession.updated_at) }}
          </span>
          <el-tag v-if="webSession.expired" type="warning" size="small" effect="light">
            cookie 已过期，建议重跑登录用例
          </el-tag>
          <el-button link type="danger" size="small" @click="clearSession">清除</el-button>
        </template>
        <span v-else class="session-text is-empty">
          本项目还没有登录态 —— 把一条用例勾上「作为登录用例」跑一次就会生成
        </span>
      </div>

      <el-table v-loading="loading" :data="cases">
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
        <el-table-column label="登录态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.login_case" type="warning" size="small" effect="light">登录用例</el-tag>
            <el-tag v-else-if="row.needs_login" type="success" size="small" effect="light">需登录态</el-tag>
            <span v-else class="is-zero">—</span>
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
.is-zero {
  color: var(--text-3);
}

.session-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.session-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}

.session-text {
  font-size: 12.5px;
  color: var(--text-2);
}

.session-text.is-empty {
  color: var(--text-3);
}
</style>
