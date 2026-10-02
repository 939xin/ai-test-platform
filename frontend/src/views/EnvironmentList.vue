<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import { listProjects } from '@/api/project'
import {
  createEnvironment, deleteEnvironment, listEnvironments, updateEnvironment,
} from '@/api/environment'

const projects = ref([])
const currentProjectId = ref(null)
const environments = ref([])
const loading = ref(false)

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const formRef = ref(null)
// variables 用数组行编辑，提交时转回 {key: value}
const form = reactive({ name: '', base_url: '', variables: [] })

const rules = {
  name: [{ required: true, message: '请输入环境名，如 dev / test / prod', trigger: 'blur' }],
}

async function loadProjects() {
  projects.value = await listProjects()
  if (currentProjectId.value == null && projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

async function loadEnvironments() {
  if (currentProjectId.value == null) {
    environments.value = []
    return
  }
  loading.value = true
  try {
    environments.value = await listEnvironments(currentProjectId.value)
  } finally {
    loading.value = false
  }
}

function toRows(obj) {
  const rows = Object.entries(obj || {}).map(([key, value]) => ({ key, value: String(value) }))
  return rows.length ? rows : [{ key: '', value: '' }]
}

function rowsToObject(rows) {
  const obj = {}
  for (const row of rows) {
    const key = (row.key || '').trim()
    if (key) obj[key] = row.value ?? ''
  }
  return obj
}

function varCount(row) {
  return Object.keys(row.variables_json || {}).length
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.base_url = ''
  form.variables = [{ key: '', value: '' }]
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.base_url = row.base_url
  form.variables = toRows(row.variables_json)
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      base_url: form.base_url,
      variables_json: rowsToObject(form.variables),
    }
    if (editingId.value) {
      await updateEnvironment(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createEnvironment(currentProjectId.value, payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadEnvironments()
  } finally {
    submitting.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除环境「${row.name}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deleteEnvironment(row.id)
  ElMessage.success('已删除')
  await loadEnvironments()
}

watch(currentProjectId, loadEnvironments)

onMounted(async () => {
  await loadProjects()
  await loadEnvironments()
})
</script>

<template>
  <div class="page-stack">
    <PageHeader title="环境变量" description="每个项目下的 dev / test / prod 环境，配置 Base URL 与全局变量">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 200px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :icon="Plus" :disabled="currentProjectId == null" @click="openCreate">
        新建环境
      </el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ environments.length }} 个环境</span>
        <el-button link :icon="Refresh" @click="loadEnvironments">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="environments">
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="name" label="环境名" width="140" />
        <el-table-column prop="base_url" label="Base URL" min-width="280">
          <template #default="{ row }">
            <span class="mono">{{ row.base_url || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="全局变量" width="120" align="center">
          <template #default="{ row }">
            <span class="mono">{{ varCount(row) }} 个</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="该项目下还没有环境" />
        </template>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑环境' : '新建环境'"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item label="环境名" prop="name">
          <el-input v-model="form.name" placeholder="dev / test / prod" maxlength="64" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://api.example.com" maxlength="255" />
        </el-form-item>
        <el-form-item label="全局变量">
          <div class="var-editor">
            <div v-for="(row, index) in form.variables" :key="index" class="var-row">
              <el-input v-model="row.key" placeholder="变量名，如 token" />
              <span class="var-eq">=</span>
              <el-input v-model="row.value" placeholder="变量值" />
              <el-button link type="danger" @click="form.variables.splice(index, 1)">移除</el-button>
            </div>
            <el-button link type="primary" @click="form.variables.push({ key: '', value: '' })">
              + 添加变量
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.var-editor {
  width: 100%;
}

.var-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.var-eq {
  color: var(--text-3);
  font-family: var(--font-mono);
}
</style>
