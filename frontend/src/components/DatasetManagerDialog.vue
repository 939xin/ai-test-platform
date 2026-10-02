<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'

import { deleteDataset, listDatasets, previewDataset, uploadDataset } from '@/api/dataset'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'pick'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const datasets = ref([])
const loading = ref(false)
const uploading = ref(false)
const preview = ref(null)
const previewLoading = ref(false)
const fileInput = ref(null)

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  if (props.projectId == null) {
    datasets.value = []
    return
  }
  loading.value = true
  try {
    datasets.value = await listDatasets(props.projectId)
    if (preview.value) preview.value = null
  } finally {
    loading.value = false
  }
}

function pickFile() {
  fileInput.value?.click()
}

async function onFileChange(event) {
  const file = event.target.files?.[0]
  event.target.value = '' // 允许重复选同一个文件
  if (!file) return
  uploading.value = true
  try {
    const info = await uploadDataset(props.projectId, file)
    ElMessage.success(`已上传：${info.filename}（${info.rows} 行）`)
    await load()
  } finally {
    uploading.value = false
  }
}

async function showPreview(row) {
  previewLoading.value = true
  try {
    preview.value = await previewDataset(props.projectId, row.filename)
  } finally {
    previewLoading.value = false
  }
}

async function remove(row) {
  await ElMessageBox.confirm(`确定删除数据文件「${row.filename}」？`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  await deleteDataset(props.projectId, row.filename)
  ElMessage.success('已删除')
  if (preview.value?.filename === row.filename) preview.value = null
  await load()
}

function pick(row) {
  emit('pick', row.filename)
  visible.value = false
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-dialog v-model="visible" title="数据文件" width="780px" top="8vh">
    <div class="toolbar">
      <span class="hint">支持 CSV / XLSX，首行为表头，每行数据执行一次用例</span>
      <div>
        <input
          ref="fileInput"
          type="file"
          accept=".csv,.xlsx,.xlsm"
          class="file-input"
          @change="onFileChange"
        />
        <el-button type="primary" :icon="Upload" :loading="uploading" @click="pickFile">
          上传文件
        </el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="datasets" stripe max-height="240">
      <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono">{{ row.filename }}</span>
        </template>
      </el-table-column>
      <el-table-column label="数据行" width="90" align="right">
        <template #default="{ row }">
          <span class="mono">{{ row.rows }}</span>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100" align="right">
        <template #default="{ row }">
          <span class="mono">{{ formatSize(row.size) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="列名" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="mono muted">{{ (row.columns || []).join(', ') || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="pick(row)">选用</el-button>
          <el-button link @click="showPreview(row)">预览</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="还没有数据文件，点右上角「上传文件」" :image-size="70" />
      </template>
    </el-table>

    <div v-if="preview" class="preview">
      <div class="preview-head">
        <span class="mono">{{ preview.filename }}</span>
        <span class="muted">共 {{ preview.rows }} 行，预览前 {{ preview.sample.length }} 行</span>
      </div>
      <el-table :data="preview.sample" size="small" border>
        <el-table-column
          v-for="col in preview.columns"
          :key="col"
          :prop="col"
          :label="col"
          min-width="120"
        />
      </el-table>
    </div>
  </el-dialog>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.hint {
  font-size: 12.5px;
  color: var(--text-3);
}

.file-input {
  display: none;
}

.muted {
  color: var(--text-3);
}

.preview {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}

.preview-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
</style>
