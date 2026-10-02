<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PlanEditorDrawer from '@/components/PlanEditorDrawer.vue'
import RunPlanDialog from '@/components/RunPlanDialog.vue'
import { listProjects } from '@/api/project'
import { deletePlan, listPlans } from '@/api/plan'

const projects = ref([])
const currentProjectId = ref(null)
const plans = ref([])
const loading = ref(false)

const drawerVisible = ref(false)
const editingId = ref(null)

const runVisible = ref(false)
const runningPlan = ref(null)

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function loadProjects() {
  projects.value = await listProjects()
  if (currentProjectId.value == null && projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadPlans() {
  if (currentProjectId.value == null) {
    plans.value = []
    return
  }
  loading.value = true
  try {
    plans.value = await listPlans(currentProjectId.value)
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
  runningPlan.value = row
  runVisible.value = true
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除计划「${row.name}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deletePlan(row.id)
  ElMessage.success('已删除')
  await loadPlans()
}

watch(currentProjectId, loadPlans)

onMounted(async () => {
  await loadProjects()
  await loadPlans()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="测试计划" description="挑一组用例绑定环境，一键批量执行，跑完统计通过情况">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建计划
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ plans.length }} 个计划</span>
        <el-button link :icon="Refresh" @click="loadPlans">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="plans">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="计划名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="用例数" width="90" align="center">
          <template #default="{ row }">
            <span class="mono">{{ row.case_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="默认环境" width="130">
          <template #default="{ row }">
            <span v-if="row.env_name">{{ row.env_name }}</span>
            <span v-else class="muted">—</span>
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
          <el-empty description="还没有测试计划，点击右上角「新建计划」挑几条用例批量跑" />
        </template>
      </el-table>
    </el-card>

    <PlanEditorDrawer
      v-model="drawerVisible"
      :plan-id="editingId"
      :project-id="currentProjectId"
      @saved="loadPlans"
    />

    <RunPlanDialog
      v-model="runVisible"
      :plan-row="runningPlan"
      :project-id="currentProjectId"
    />
  </div>
</template>

<style scoped>
.muted {
  color: var(--text-3);
}
</style>
