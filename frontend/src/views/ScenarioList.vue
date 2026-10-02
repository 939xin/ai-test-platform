<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import ScenarioEditorDrawer from '@/components/ScenarioEditorDrawer.vue'
import RunScenarioDialog from '@/components/RunScenarioDialog.vue'
import { listProjects } from '@/api/project'
import { deleteScenario, listScenarios } from '@/api/scenario'

const projects = ref([])
const currentProjectId = ref(null)
const scenarios = ref([])
const loading = ref(false)

const drawerVisible = ref(false)
const editingId = ref(null)

const runVisible = ref(false)
const runningScenario = ref(null)

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function loadProjects() {
  projects.value = await listProjects()
  if (currentProjectId.value == null && projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadScenarios() {
  if (currentProjectId.value == null) {
    scenarios.value = []
    return
  }
  loading.value = true
  try {
    scenarios.value = await listScenarios(currentProjectId.value)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  drawerVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  drawerVisible.value = true
}

function openRun(row) {
  runningScenario.value = row
  runVisible.value = true
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除场景「${row.name}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deleteScenario(row.id)
  ElMessage.success('已删除')
  await loadScenarios()
}

watch(currentProjectId, loadScenarios)

onMounted(async () => {
  await loadProjects()
  await loadScenarios()
})
</script>

<template>
  <div>
    <PageHeader title="场景测试" description="把多条用例串成链路，上一步提取的变量传给下一步">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建场景
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="scenarios" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="场景名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="步骤数" width="90" align="center">
          <template #default="{ row }">
            <span class="mono">{{ row.step_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" align="right">
          <template #default="{ row }">
            <el-button link type="success" @click="openRun(row)">执行</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有场景，点击右上角「新建场景」把用例串起来" />
        </template>
      </el-table>
    </el-card>

    <ScenarioEditorDrawer
      v-model="drawerVisible"
      :scenario-id="editingId"
      :project-id="currentProjectId"
      @saved="loadScenarios"
    />

    <RunScenarioDialog
      v-model="runVisible"
      :scenario-row="runningScenario"
      :project-id="currentProjectId"
    />
  </div>
</template>

<style scoped>
.muted {
  color: var(--text-3);
}
</style>
