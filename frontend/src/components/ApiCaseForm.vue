<script setup>
/**
 * 接口用例的专属表单区：请求配置 / 断言条件 / 提取变量。
 *
 * form 是从编辑页传下来的同一个 reactive 对象，这里直接改它的字段 ——
 * 保存逻辑统一在 views/CaseEditor.vue，本组件只负责界面。
 */
import { ref } from 'vue'
import { Files } from '@element-plus/icons-vue'

const activeTab = ref('request')

defineProps({
  form: { type: Object, required: true },
  datasets: { type: Array, default: () => [] },
})
defineEmits(['manage-datasets'])

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

// 变量提取来源：从响应体（JSONPath）/ 响应头 / 状态码取值，供后续步骤用 ${变量名} 引用
const EXTRACT_SOURCES = [
  { value: 'body', label: '响应体 (JSONPath)' },
  { value: 'header', label: '响应头' },
  { value: 'status', label: '状态码' },
]
</script>

<template>
  <el-form-item label="数据文件">
    <div class="data-file-row">
      <el-select
        v-model="form.data_file"
        placeholder="不使用（单次执行）"
        clearable
        filterable
        class="data-file-select"
      >
        <el-option
          v-for="d in datasets"
          :key="d.filename"
          :label="`${d.filename}（${d.rows} 行）`"
          :value="d.filename"
        />
      </el-select>
      <el-button :icon="Files" @click="$emit('manage-datasets')">管理数据文件</el-button>
    </div>
  </el-form-item>

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

    <!-- ============ 提取变量 ============ -->
    <el-tab-pane label="提取变量" name="extracts">
      <div class="rows-editor">
        <div v-for="(row, index) in form.extracts" :key="index" class="assert-row">
          <el-input v-model="row.name" class="assert-type" placeholder="变量名，如 token" />
          <el-select v-model="row.source" class="assert-op">
            <el-option v-for="s in EXTRACT_SOURCES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-input
            v-model="row.expression"
            class="assert-target"
            :disabled="row.source === 'status'"
            :placeholder="
              row.source === 'body'
                ? 'JSONPath，如 $.token'
                : row.source === 'header'
                  ? '响应头名，如 Content-Type'
                  : '状态码无需填写'
            "
          />
          <el-button link type="danger" @click="form.extracts.splice(index, 1)">移除</el-button>
        </div>
        <el-button link type="primary" @click="form.extracts.push({ name: '', source: 'body', expression: '' })">
          + 添加提取规则
        </el-button>
        <p class="hint">
          提取到的变量在后续用例里用 <code>${变量名}</code> 引用（场景串联时传给下一步）。提取失败不影响用例结果。
        </p>
      </div>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.span-2 {
  grid-column: span 2;
}

.data-file-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.data-file-select {
  flex: 1;
  min-width: 0;
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
