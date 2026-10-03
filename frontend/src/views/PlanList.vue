<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import PagePagination from '@/components/PagePagination.vue'
import PlanEditorDrawer from '@/components/PlanEditorDrawer.vue'
import RunPlanDialog from '@/components/RunPlanDialog.vue'
import { listProjects } from '@/api/project'
import { deletePlan, listPlans } from '@/api/plan'

const projects = ref([])
const currentProjectId = ref(null)
const plans = ref([])
const loading = ref(false)

// 分页状态。total 是全部条数，由后端返回，不是 plans.length
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

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
    total.value = 0
    return
  }
  loading.value = true
  try {
    const data = await listPlans(currentProjectId.value, {
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value,
    })
    plans.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

/** 换项目就回到第 1 页 —— 否则可能停在新项目根本没有的页码上，看到一张空表。 */
function search() {
  page.value = 1
  return loadPlans()
}

/** 分页条回调：页码和每页条数由组件一次给全，避免两者先后生效导致多查一次。 */
function onPageChange(payload) {
  page.value = payload.page
  pageSize.value = payload.pageSize
  return loadPlans()
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
  // 删掉的是本页最后一条时往前退一页，否则会停在一张空表上
  if (plans.value.length === 1 && page.value > 1) page.value -= 1
  await loadPlans()
}

// 换项目不走 watch，走 el-select 的 @change（见模板）。
// watch 会在 loadProjects() 给 select 赋初值时也触发一次，加上 onMounted 里
// 那句显式查询，开局就查了两遍 —— 请求面板里能看到两条一模一样的。
// @change 只有用户真的选了才发，程序赋值不发。
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
        @change="search"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建计划
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ total }} 个计划</span>
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

      <PagePagination
        :page="page"
        :page-size="pageSize"
        :total="total"
        @change="onPageChange"
      />
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
