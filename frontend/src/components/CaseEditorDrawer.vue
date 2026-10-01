<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { createCase, getCase, updateCase } from '@/api/case'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  caseId: { type: Number, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEdit = computed(() => props.caseId != null)

const loading = ref(false)
const submitting = ref(false)
const formRef = ref(null)
const activeTab = ref('request')

const METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
const BODY_TYPES = [
  { value: 'none', label: '无请求体' },
  { value: 'json', label: 'JSON' },
  { value: 'form', label: 'Form Data' },
  { value: 'xml', label: 'XML' },
  { value: 'raw', label: 'Raw' },
]
const AUTH_TYPES = [
  { value: 'none', label: '无认证' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'apikey', label: 'API Key' },
]
const ASSERTION_TYPES = [
  { value: 'status_code', label: '状态码' },
  { value: 'response_body', label: '响应体 (JSONPath)' },
  { value: 'response_time', label: '响应时间 (ms)' },
]
const OPERATORS = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'contains', label: '包含' },
  { value: 'regex', label: '正则匹配' },
  { value: 'lt', label: '小于' },
  { value: 'gt', label: '大于' },
]

const form = reactive({
  name: '',
  type: 'api',
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
})

const rules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入请求 URL', trigger: 'blur' }],
}

function resetForm() {
  Object.assign(form, {
    name: '',
    type: 'api',
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
    assertions: [{ assertion_type: 'status_code', operator: 'eq', target: '', expected_value: '200' }],
  })
  activeTab.value = 'request'
}

async function load() {
  if (!isEdit.value) {
    resetForm()
    return
  }
  loading.value = true
  try {
    const data = await getCase(props.caseId)
    Object.assign(form, {
      name: data.name,
      type: data.type,
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
    })
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

async function submit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      type: form.type,
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
    }
    if (isEdit.value) {
      await updateCase(props.caseId, payload)
      ElMessage.success('已更新')
    } else {
      await createCase(props.projectId, payload)
      ElMessage.success('已创建')
    }
    visible.value = false
    emit('saved')
  } finally {
    submitting.value = false
  }
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-drawer v-model="visible" :title="isEdit ? '编辑用例' : '新建用例'" size="720px">
    <el-form
      ref="formRef"
      v-loading="loading"
      :model="form"
      :rules="rules"
      label-width="76px"
      label-position="left"
    >
      <div class="basic-grid">
        <el-form-item label="用例名称" prop="name" class="span-2">
          <el-input v-model="form.name" placeholder="例如：GET /get 连通性验证" maxlength="128" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type">
            <el-option label="接口" value="api" />
            <el-option label="Web UI" value="web" disabled />
          </el-select>
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

      <el-tabs v-model="activeTab" class="editor-tabs">
        <!-- ============ 请求配置 ============ -->
        <el-tab-pane label="请求配置" name="request">
          <el-form-item label="请求" prop="url">
            <div class="method-url">
              <el-select v-model="form.method" class="method-select">
                <el-option v-for="m in METHODS" :key="m" :label="m" :value="m" />
              </el-select>
              <el-input v-model="form.url" placeholder="支持 ${base_url} 变量，如 ${base_url}/users" />
            </div>
          </el-form-item>

          <el-form-item label="请求头">
            <div class="rows-editor">
              <div v-for="(row, index) in form.headers" :key="index" class="kv-row">
                <el-input v-model="row.key" placeholder="Header 名" />
                <el-input v-model="row.value" placeholder="值" />
                <el-button link type="danger" @click="form.headers.splice(index, 1)">移除</el-button>
              </div>
              <el-button link type="primary" @click="form.headers.push({ key: '', value: '' })">
                + 添加请求头
              </el-button>
            </div>
          </el-form-item>

          <el-form-item label="认证">
            <div class="auth-row">
              <el-select v-model="form.auth_type" class="auth-select">
                <el-option v-for="a in AUTH_TYPES" :key="a.value" :label="a.label" :value="a.value" />
              </el-select>
              <el-input
                v-if="form.auth_type !== 'none'"
                v-model="form.auth_value"
                :placeholder="form.auth_type === 'basic' ? '用户名:密码' : 'Token / Key 值，支持 ${变量}'"
              />
            </div>
          </el-form-item>

          <el-form-item label="请求体">
            <div class="body-editor">
              <el-select v-model="form.body_type">
                <el-option v-for="b in BODY_TYPES" :key="b.value" :label="b.label" :value="b.value" />
              </el-select>
              <el-input
                v-if="form.body_type !== 'none'"
                v-model="form.body_content"
                type="textarea"
                :rows="6"
                class="mono-input"
                placeholder='{"key": "value"}'
              />
            </div>
          </el-form-item>
        </el-tab-pane>

        <!-- ============ 断言条件 ============ -->
        <el-tab-pane label="断言条件" name="assertions">
          <div class="rows-editor">
            <div v-for="(row, index) in form.assertions" :key="index" class="assert-row">
              <el-select v-model="row.assertion_type" class="assert-type">
                <el-option v-for="t in ASSERTION_TYPES" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
              <el-input
                v-model="row.target"
                class="assert-target"
                :disabled="row.assertion_type !== 'response_body'"
                :placeholder="row.assertion_type === 'response_body' ? 'JSONPath，如 $.data.token' : '目标(仅 JSONPath 用)'"
              />
              <el-select v-model="row.operator" class="assert-op">
                <el-option v-for="o in OPERATORS" :key="o.value" :label="o.label" :value="o.value" />
              </el-select>
              <el-input v-model="row.expected_value" class="assert-expect" placeholder="期望值" />
              <el-button link type="danger" @click="form.assertions.splice(index, 1)">移除</el-button>
            </div>
            <el-button
              link
              type="primary"
              @click="form.assertions.push({ assertion_type: 'status_code', operator: 'eq', target: '', expected_value: '' })"
            >
              + 添加断言
            </el-button>
            <p class="hint">期望值留空的断言会被后端静默跳过。</p>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.basic-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 16px;
}

.span-2 {
  grid-column: span 2;
}

.editor-tabs {
  margin-top: 4px;
}

.method-url,
.auth-row,
.body-editor {
  display: flex;
  gap: 8px;
  width: 100%;
}

.method-select {
  width: 110px;
  flex-shrink: 0;
}

.auth-select {
  width: 150px;
  flex-shrink: 0;
}

.body-editor {
  flex-direction: column;
  align-items: stretch;
}

.rows-editor {
  width: 100%;
}

.kv-row,
.assert-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.assert-type {
  width: 150px;
  flex-shrink: 0;
}

.assert-target {
  width: 190px;
  flex-shrink: 0;
}

.assert-op {
  width: 110px;
  flex-shrink: 0;
}

.assert-expect {
  width: 130px;
  flex-shrink: 0;
}

.mono-input :deep(textarea) {
  font-family: var(--font-mono);
  font-size: 13px;
}

.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-3);
}
</style>
