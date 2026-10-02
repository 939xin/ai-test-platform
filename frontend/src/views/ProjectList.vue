<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import { createProject, deleteProject, listProjects, updateProject } from '@/api/project'

const loading = ref(false)
const projects = ref([])

const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const form = reactive({ name: '', description: '' })

const rules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
}

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

async function load() {
  loading.value = true
  try {
    projects.value = await listProjects()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.description = ''
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.description = row.description
  dialogVisible.value = true
}

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = { name: form.name, description: form.description }
    if (editingId.value) {
      await updateProject(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createProject(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(
    `确定删除项目「${row.name}」？其下的环境与用例会一并删除，不可撤销。`,
    '删除确认',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await deleteProject(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page-stack">
    <PageHeader title="项目管理" description="创建和管理测试项目，查看用例数、执行数与通过率">
      <el-button type="primary" :icon="Plus" @click="openCreate">新建项目</el-button>
    </PageHeader>

    <el-card shadow="never">
      <div class="card-tools">
        <span>共 {{ projects.length }} 个项目</span>
        <el-button link :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <el-table v-loading="loading" :data="projects">
        <el-table-column prop="id" label="ID" width="72" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'text-muted': !row.description }">{{ row.description || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">
            <span class="mono">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" align="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="还没有项目，点击右上角「新建项目」开始" />
        </template>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑项目' : '新建项目'"
      width="480px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：电商平台接口测试" maxlength="128" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="3"
            placeholder="选填"
            maxlength="1000"
          />
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
.text-muted {
  color: var(--text-3);
}
</style>
