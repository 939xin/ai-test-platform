<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  createDefect,
  DEFECT_STATUS_OPTIONS,
  getDefect,
  PRIORITY_OPTIONS,
  SEVERITY_OPTIONS,
  updateDefect,
} from '@/api/defect'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 传了就是编辑，否则是新建
  defectId: { type: Number, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEdit = computed(() => props.defectId != null)

const loading = ref(false)
const submitting = ref(false)
// 编辑态加载到的完整缺陷（含关联执行信息），新建态为 null
const defect = ref(null)

const form = reactive({
  title: '',
  description: '',
  severity: '一般',
  priority: 'P1',
  status: '新建',
})

async function load() {
  if (!isEdit.value) {
    defect.value = null
    Object.assign(form, {
      title: '', description: '', severity: '一般', priority: 'P1', status: '新建',
    })
    return
  }
  loading.value = true
  try {
    const data = await getDefect(props.defectId)
    defect.value = data
    Object.assign(form, {
      title: data.title,
      description: data.description,
      severity: data.severity,
      priority: data.priority,
      status: data.status,
    })
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!String(form.title).trim()) {
    ElMessage.warning('请填写缺陷标题')
    return
  }
  submitting.value = true
  try {
    const payload = {
      title: form.title,
      description: form.description,
      severity: form.severity,
      priority: form.priority,
    }
    if (isEdit.value) {
      payload.status = form.status
      await updateDefect(props.defectId, payload)
    } else {
      await createDefect(props.projectId, payload)
    }
    ElMessage.success(isEdit.value ? '已保存' : '已创建')
    emit('saved')
    visible.value = false
  } finally {
    submitting.value = false
  }
}

/** 跳到执行中心并打开来源执行记录（执行中心支持 ?open=<id>）。 */
function gotoExecution() {
  const executionId = defect.value?.execution_id
  if (!executionId) return
  visible.value = false
  router.push({ name: 'executions', query: { open: executionId } })
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-drawer v-model="visible" :title="isEdit ? '编辑缺陷' : '新建缺陷'" size="620px">
    <el-form v-loading="loading" label-width="90px">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" placeholder="一句话说清问题现象" maxlength="255" />
      </el-form-item>

      <el-form-item label="严重程度">
        <el-select v-model="form.severity" style="width: 160px">
          <el-option v-for="s in SEVERITY_OPTIONS" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>

      <el-form-item label="优先级">
        <el-select v-model="form.priority" style="width: 160px">
          <el-option v-for="p in PRIORITY_OPTIONS" :key="p" :label="p" :value="p" />
        </el-select>
      </el-form-item>

      <!-- 新建的缺陷状态由后端固定为「新建」，所以只在编辑时给选 -->
      <el-form-item v-if="isEdit" label="状态">
        <el-select v-model="form.status" style="width: 160px">
          <el-option v-for="s in DEFECT_STATUS_OPTIONS" :key="s" :label="s" :value="s" />
        </el-select>
      </el-form-item>

      <el-form-item label="描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="10"
          placeholder="复现步骤、期望结果、实际结果"
        />
      </el-form-item>

      <el-form-item v-if="defect?.execution_id" label="关联执行">
        <div class="link-row">
          <span class="mono">#{{ defect.execution_id }}</span>
          <span class="link-case">{{ defect.case_name || '已删除用例' }}</span>
          <el-button link type="primary" @click="gotoExecution">查看执行</el-button>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.link-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: var(--text-2);
}

.link-case {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
