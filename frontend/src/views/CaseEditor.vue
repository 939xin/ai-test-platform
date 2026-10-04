<script setup>
/**
 * 用例全屏编辑页（接口 / UI 共用）。
 *
 * 类型由路由 meta.caseType 决定，界面上不再有「类型」下拉 ——
 * 从「接口测试」进来就是接口用例，从「UI 测试」进来就是 Web 用例，
 * 保存后回到各自所属的列表。
 *
 * 类型专属的表单区拆到两个子组件里（ApiCaseForm / WebCaseForm），
 * 本文件只保留两边共用的部分：基本信息、提交、返回。
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'

import AiGenerateDialog from '@/components/AiGenerateDialog.vue'
import ApiCaseForm from '@/components/ApiCaseForm.vue'
import WebCaseForm from '@/components/WebCaseForm.vue'
import DatasetManagerDialog from '@/components/DatasetManagerDialog.vue'
import { createCase, getCase, updateCase } from '@/api/case'
import { listDatasets } from '@/api/dataset'
import { getWebStatus } from '@/api/web'

const route = useRoute()
const router = useRouter()

const caseType = computed(() => route.meta.caseType || 'api')
const isApi = computed(() => caseType.value === 'api')
const caseId = computed(() => (route.params.id ? Number(route.params.id) : null))
const isEdit = computed(() => caseId.value != null)
const listRouteName = computed(() => (isApi.value ? 'api-cases' : 'web-cases'))
const typeLabel = computed(() => (isApi.value ? '接口' : 'UI'))

const loading = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const apiFormRef = ref(null)
const webFormRef = ref(null)

// 编辑已有用例时以用例自身的 project_id 为准，新建时用列表页带过来的 query
const loadedProjectId = ref(null)
const projectId = computed(() => {
  if (loadedProjectId.value != null) return loadedProjectId.value
  const fromQuery = Number(route.query.project)
  return Number.isFinite(fromQuery) && fromQuery > 0 ? fromQuery : null
})

const datasets = ref([])
const datasetDialogVisible = ref(false)

// AI 生成用例弹窗（仅接口用例）：生成的结果勾选后存进当前项目，不影响正在编辑的这条
const aiVisible = ref(false)

// 浏览器探测结果与枚举：{ available, error, actions, locators }
const webInfo = ref(null)
const webActions = computed(() => webInfo.value?.actions || [])
const webActionGroups = computed(() => webInfo.value?.action_groups || [])
const webLocators = computed(() => webInfo.value?.locators || [])

const form = reactive({
  name: '',
  priority: 'P1',
  tags: '',
  enabled: true,
  method: 'GET',
  url: '',
  headers: [],
  body_type: 'none',
  body_content: '',
  auth_type: 'none',
  auth_value: '',
  assertions: [],
  extracts: [],
  data_file: '',
  steps: [],
})

const rules = computed(() => {
  const base = { name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }] }
  // Web 用例的地址写在步骤里，主表单的 url 不参与校验
  if (isApi.value) base.url = [{ required: true, message: '请输入请求 URL', trigger: 'blur' }]
  return base
})

function resetForm() {
  Object.assign(form, {
    name: '',
    priority: 'P1',
    tags: '',
    enabled: true,
    method: 'GET',
    url: '',
    headers: [],
    body_type: 'none',
    body_content: '',
    auth_type: 'none',
    auth_value: '',
    // 接口用例默认给一条状态码 200 的断言，省得每次手加
    assertions: isApi.value
      ? [{ assertion_type: 'status_code', operator: 'eq', target: '', expected_value: '200' }]
      : [],
    extracts: [],
    data_file: '',
    steps: [],
  })
}

async function loadDatasets() {
  if (projectId.value == null) {
    datasets.value = []
    return
  }
  datasets.value = await listDatasets(projectId.value)
}

async function ensureWebInfo() {
  if (webInfo.value) return
  webInfo.value = await getWebStatus()
}

async function load() {
  loading.value = true
  try {
    loadedProjectId.value = null
    resetForm()
    formRef.value?.clearValidate()

    if (isApi.value) await loadDatasets()
    else await ensureWebInfo()

    if (!isEdit.value) {
      if (projectId.value == null) {
        ElMessage.warning('请先从列表页选择项目，再新建用例')
        router.replace({ name: listRouteName.value })
      }
      return
    }

    const data = await getCase(caseId.value)
    loadedProjectId.value = data.project_id
    Object.assign(form, {
      name: data.name,
      priority: data.priority,
      tags: data.tags,
      enabled: data.enabled,
      method: data.method,
      url: data.url,
      headers: Object.entries(data.headers_json || {}).map(([key, value]) => ({ key, value })),
      body_type: data.body_type,
      body_content: data.body_content,
      auth_type: data.auth_type,
      auth_value: data.auth_value,
      assertions: (data.assertions_json || []).map((a) => ({ ...a })),
      extracts: (data.extract_json || []).map((e) => ({ ...e })),
      data_file: data.data_file || '',
      // 老数据里没有新增的槽位字段，补上默认值，否则 v-model 绑到 undefined
      steps: (data.steps_json || []).map((s) => ({
        input_value: '',
        input_value2: '',
        wait_seconds: 0,
        description: '',
        locator_type: '',
        locator_value: '',
        target_locator_type: '',
        target_locator_value: '',
        ...s,
      })),
    })
    if (isApi.value) await loadDatasets()
  } finally {
    loading.value = false
  }
}

function rowsToObject(rows) {
  const obj = {}
  for (const row of rows) {
    const key = (row.key || '').trim()
    if (key) obj[key] = row.value ?? ''
  }
  return obj
}

/**
 * 把编辑器里的步骤整理成后端 WebStep 认识的形状。
 * step_order 按数组下标重排 —— 用户上下移之后，序号必须跟着位置走。
 */
function normalizeStep(step, index) {
  return {
    step_order: index + 1,
    enabled: step.enabled !== false,
    action_type: step.action_type,
    input_value: String(step.input_value ?? ''),
    input_value2: String(step.input_value2 ?? ''),
    wait_seconds: Number(step.wait_seconds) || 0,
    description: String(step.description ?? ''),
    locator_type: String(step.locator_type ?? ''),
    locator_value: String(step.locator_value ?? ''),
    target_locator_type: String(step.target_locator_type ?? ''),
    target_locator_value: String(step.target_locator_value ?? ''),
  }
}

function buildPayload() {
  return {
    name: form.name,
    type: caseType.value,
    priority: form.priority,
    tags: form.tags,
    enabled: form.enabled,
    method: form.method,
    url: form.url,
    headers_json: rowsToObject(form.headers),
    body_type: form.body_type,
    body_content: form.body_content,
    auth_type: form.auth_type,
    auth_value: form.auth_value,
    // 空期望值的断言后端会跳过，这里先过滤掉，避免存脏数据
    assertions_json: form.assertions
      .filter((a) => String(a.expected_value ?? '').trim())
      .map((a) => ({
        assertion_type: a.assertion_type,
        operator: a.operator,
        target: a.target || '',
        expected_value: String(a.expected_value),
      })),
    // 变量名为空的提取规则没意义，直接丢掉
    extract_json: form.extracts
      .filter((e) => String(e.name ?? '').trim())
      .map((e) => ({
        name: String(e.name).trim(),
        source: e.source || 'body',
        expression: e.source === 'status' ? '' : String(e.expression ?? '').trim(),
      })),
    steps_json: isApi.value ? [] : form.steps.map(normalizeStep),
    // 数据驱动目前只走接口执行器，Web 用例不带数据文件
    data_file: isApi.value ? form.data_file || '' : '',
  }
}

function goBack() {
  router.push({ name: listRouteName.value, query: { project: projectId.value } })
}

async function submit() {
  await formRef.value.validate()
  // UI 用例缺定位信息后端会 422，在前端就拦下来并说清是第几步
  if (!isApi.value) {
    const problem = webFormRef.value?.validate()
    if (problem) {
      ElMessage.warning(problem)
      return
    }
  }
  submitting.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await updateCase(caseId.value, payload)
      ElMessage.success('已更新')
    } else {
      await createCase(projectId.value, payload)
      ElMessage.success('已创建')
    }
    goBack()
  } finally {
    submitting.value = false
  }
}

watch(() => route.fullPath, load)
onMounted(load)
</script>

<template>
  <div v-loading="loading" class="case-editor">
    <el-card shadow="never" class="editor-card">
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="86px"
        label-position="left"
      >
        <div class="basic-grid">
          <el-form-item label="用例名称" prop="name" class="span-2">
            <el-input
              v-model="form.name"
              :placeholder="isApi ? '例如：GET /get 连通性验证' : '例如：登录流程'"
              maxlength="128"
            />
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option v-for="p in ['P0', 'P1', 'P2']" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="form.tags" placeholder="逗号分隔，如 smoke,order" />
          </el-form-item>
          <el-form-item label="启用">
            <el-switch v-model="form.enabled" />
          </el-form-item>
        </div>

        <ApiCaseForm
          v-if="isApi"
          ref="apiFormRef"
          :form="form"
          :datasets="datasets"
          @manage-datasets="datasetDialogVisible = true"
        />
        <WebCaseForm
          v-else
          ref="webFormRef"
          :form="form"
          :actions="webActions"
          :action-groups="webActionGroups"
          :locators="webLocators"
          :web-info="webInfo"
        />
      </el-form>
    </el-card>

    <div class="editor-foot">
      <el-button
        v-if="isApi"
        class="foot-ai"
        :icon="MagicStick"
        :disabled="projectId == null"
        @click="aiVisible = true"
      >
        AI 生成用例
      </el-button>
      <el-button @click="goBack">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">
        {{ isEdit ? '保存修改' : `创建${typeLabel}用例` }}
      </el-button>
    </div>

    <DatasetManagerDialog
      v-model="datasetDialogVisible"
      :project-id="projectId"
      @pick="(filename) => (form.data_file = filename)"
    />

    <AiGenerateDialog v-model="aiVisible" :project-id="projectId" />
  </div>
</template>

<style scoped>
.case-editor {
  padding-bottom: 68px;
}

.editor-card {
  max-width: 1100px;
}

.basic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 16px;
}

.span-2 {
  grid-column: span 2;
}

/* 保存条固定在底部：表单再长也不用滚回顶部找按钮 */
.editor-foot {
  position: fixed;
  left: var(--sider-width);
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 24px;
  background: var(--bg-surface);
  border-top: 1px solid var(--border);
}

/* AI 生成放在最左，与「取消 / 保存」拉开距离，避免误点 */
.foot-ai {
  margin-right: auto;
}
</style>
