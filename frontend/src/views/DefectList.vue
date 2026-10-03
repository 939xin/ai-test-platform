<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import DefectEditorDrawer from '@/components/DefectEditorDrawer.vue'
import { listProjects } from '@/api/project'
import {
  DEFECT_STATUS_OPTIONS,
  deleteDefect,
  listDefects,
  SEVERITY_OPTIONS,
} from '@/api/defect'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const defects = ref([])
const loading = ref(false)

const filters = reactive({ status: '', severity: '', keyword: '' })

const drawerVisible = ref(false)
const editingId = ref(null)

// 严重程度 / 状态各给一套配色，色值全部取自设计令牌
const SEVERITY_CLASS = {
  致命: 'sev-fatal',
  严重: 'sev-major',
  一般: 'sev-normal',
  轻微: 'sev-minor',
}

const STATUS_CLASS = {
  新建: 'st-new',
  处理中: 'st-doing',
  已修复: 'st-fixed',
  已关闭: 'st-closed',
  重新打开: 'st-reopen',
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function loadProjects() {
  projects.value = await listProjects()
  // 从执行中心跳过来时会带上 ?project=<id>，优先用它
  const wanted = Number(route.query.project)
  if (wanted && projects.value.some((p) => p.id === wanted)) {
    currentProjectId.value = wanted
  } else if (currentProjectId.value == null && projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadDefects() {
  if (currentProjectId.value == null) {
    defects.value = []
    return
  }
  loading.value = true
  try {
    const params = {}
    if (filters.status) params.status = filters.status
    if (filters.severity) params.severity = filters.severity
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    defects.value = await listDefects(currentProjectId.value, params)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.status = ''
  filters.severity = ''
  filters.keyword = ''
  loadDefects()
}

function openCreate() {
  editingId.value = null
  drawerVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  drawerVisible.value = true
}

function gotoExecution(row) {
  if (!row.execution_id) return
  router.push({ name: 'executions', query: { open: row.execution_id } })
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除缺陷「${row.title}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deleteDefect(row.id)
  ElMessage.success('已删除')
  await loadDefects()
}

/** 从执行中心「提缺陷」跳过来时带 ?open=<id>&project=<pid>，直接打开那条缺陷。 */
function openFromQuery() {
  const openId = Number(route.query.open)
  if (!openId) return
  editingId.value = openId
  drawerVisible.value = true

  // 清掉 open，免得用户关掉抽屉后一刷新又弹出来；project 保留
  const query = {}
  if (currentProjectId.value != null) query.project = String(currentProjectId.value)
  router.replace({ query })
}

watch(currentProjectId, loadDefects)

onMounted(async () => {
  await loadProjects()
  await loadDefects()
  openFromQuery()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader
      title="缺陷管理"
      description="失败用例一键转缺陷，支持严重程度、优先级与状态流转"
    >
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建缺陷
      </el-button>
    </PageHeader>

    <el-card class="card-filter" shadow="never">
      <div class="filter-bar">
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
          <el-option v-for="s in DEFECT_STATUS_OPTIONS" :key="s" :label="s" :value="s" />
        </el-select>
        <el-select v-model="filters.severity" placeholder="全部严重程度" clearable style="width: 160px">
          <el-option v-for="s in SEVERITY_OPTIONS" :key="s" :label="s" :value="s" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          placeholder="按标题搜索"
          clearable
          style="width: 220px"
          @keyup.enter="loadDefects"
        />
        <el-button type="primary" :icon="Search" @click="loadDefects">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ defects.length }} 条缺陷</span>
        <el-button link :icon="Refresh" @click="loadDefects">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="defects">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column label="严重程度" width="110">
          <template #default="{ row }">
            <span class="tag" :class="SEVERITY_CLASS[row.severity]">{{ row.severity }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="84" align="center">
          <template #default="{ row }">
            <span class="mono">{{ row.priority }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="106">
          <template #default="{ row }">
            <span class="tag" :class="STATUS_CLASS[row.status]">{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="关联用例" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.case_name">{{ row.case_name }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" align="right" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.execution_id" link type="info" @click="gotoExecution(row)">
              执行
            </el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有缺陷。执行失败后可在「执行中心」的详情里一键提缺陷" />
        </template>
      </el-table>
    </el-card>

    <DefectEditorDrawer
      v-model="drawerVisible"
      :defect-id="editingId"
      :project-id="currentProjectId"
      @saved="loadDefects"
    />
  </div>
</template>

<style scoped>
.muted {
  color: var(--text-3);
}

.tag {
  display: inline-block;
  padding: 1px 7px;
  border: 1px solid transparent;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

/* 严重程度：越严重越红 */
.sev-fatal {
  color: #fff;
  background: var(--signal-fail);
  border-color: var(--signal-fail);
}

.sev-major {
  color: var(--signal-fail);
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
}

.sev-normal {
  color: var(--signal-warn);
  background: var(--signal-warn-bg);
  border-color: #eed9b0;
}

.sev-minor {
  color: var(--signal-skip);
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

/* 状态：蓝=进行中，绿=已收敛，灰=关闭，红=又打开了 */
.st-new,
.st-closed {
  color: var(--signal-skip);
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

.st-doing {
  color: var(--brand-700);
  background: var(--brand-100);
  border-color: #b3d6dd;
}

.st-fixed {
  color: var(--signal-pass);
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.st-reopen {
  color: var(--signal-fail);
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
}
</style>
