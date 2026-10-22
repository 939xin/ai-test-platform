<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { getCase, listCases } from '@/api/case'
import { listEnvironments } from '@/api/environment'
import {
  createPerfTask, getPerfLimits, getPerfTask, updatePerfTask,
} from '@/api/perf'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 传了就是编辑，否则是新建
  taskId: { type: Number, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
const isEdit = computed(() => props.taskId != null)

const limits = ref({
  max_concurrency: 50,
  max_total_requests: 200000,
  max_duration_seconds: 600,
  max_rps: 2000,
  max_warmup_seconds: 10,
  max_request_timeout: 120,
  max_active_runs: 1,
  hard_wall_seconds: 900,
})

const environments = ref([])
const cases = ref([])
const caseTotal = ref(0)
const caseKeyword = ref('')
const loading = ref(false)
const submitting = ref(false)

const form = reactive({
  name: '',
  description: '',
  case_id: null,
  env_id: null,
  load_mode: 'count',
  total_requests: 1000,
  duration_seconds: 60,
  concurrency: 10,
  target_rps: null,
  warmup_seconds: 0,
  request_timeout: 10,
  verify_ssl: true,
  error_rate_threshold: 50,
  min_requests_before_abort: 20,
})

// 熔断关闭时提交 null（后端用 NULL 表示关闭），界面不必让用户记住这个约定
const throttleEnabled = ref(true)

// 用例选择器一次取 100 条；搜索时按关键字重新查，避免只列出头一页
const CASE_LIMIT = 100

let searchTimer = null

function resetForm() {
  Object.assign(form, {
    name: '',
    description: '',
    case_id: null,
    env_id: null,
    load_mode: 'count',
    total_requests: 1000,
    duration_seconds: 60,
    concurrency: 10,
    target_rps: null,
    warmup_seconds: 0,
    request_timeout: 10,
    verify_ssl: true,
    error_rate_threshold: 50,
    min_requests_before_abort: 20,
  })
  throttleEnabled.value = true
  caseKeyword.value = ''
}

function caseLabel(c) {
  return `${c.name}（${c.method} ${c.url || '未填 URL'}）`
}

async function searchCases(keyword = '') {
  if (props.projectId == null) return
  const data = await listCases(props.projectId, {
    type: 'api',
    keyword: keyword || undefined,
    limit: CASE_LIMIT,
  })
  cases.value = data.items
  caseTotal.value = data.total
}

/** 输入防抖：远程搜索没必要每敲一个字都打后端 */
function onCaseSearch(keyword) {
  caseKeyword.value = keyword
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => searchCases(keyword), 300)
}

async function ensureSelectedCase(caseId) {
  if (!caseId || cases.value.some((item) => item.id === caseId)) return
  // 编辑旧任务时，绑定的用例可能不在首页 100 条里，单独补进来
  try {
    const current = await getCase(caseId)
    cases.value = [current, ...cases.value]
  } catch {
    // 用例已被删除：保留空选中，提交时会被拦下
  }
}

function pickFields(task) {
  return {
    name: task.name,
    description: task.description,
    case_id: task.case_id,
    env_id: task.env_id,
    load_mode: task.load_mode,
    total_requests: task.total_requests,
    duration_seconds: task.duration_seconds,
    concurrency: task.concurrency,
    target_rps: task.target_rps,
    warmup_seconds: task.warmup_seconds,
    request_timeout: task.request_timeout,
    verify_ssl: task.verify_ssl,
    error_rate_threshold: task.error_rate_threshold ?? 50,
    min_requests_before_abort: task.min_requests_before_abort,
  }
}

async function load() {
  loading.value = true
  try {
    const [limitsData, envList] = await Promise.all([
      getPerfLimits(),
      listEnvironments(props.projectId),
    ])
    limits.value = limitsData
    environments.value = envList

    if (isEdit.value) {
      const task = await getPerfTask(props.taskId)
      Object.assign(form, pickFields(task))
      throttleEnabled.value = task.error_rate_threshold != null
      caseKeyword.value = ''
      await searchCases('')
      await ensureSelectedCase(task.case_id)
    } else {
      resetForm()
      await searchCases('')
    }
  } finally {
    loading.value = false
  }
}

function validate() {
  if (!String(form.name).trim()) {
    ElMessage.warning('请填写任务名称')
    return false
  }
  if (!form.case_id) {
    ElMessage.warning('请选择要压测的接口用例')
    return false
  }
  if (!form.concurrency || form.concurrency < 1) {
    ElMessage.warning('并发数至少为 1')
    return false
  }
  if (form.load_mode === 'count' && (!form.total_requests || form.total_requests < 1)) {
    ElMessage.warning('总请求数至少为 1')
    return false
  }
  if (form.load_mode === 'duration' && (!form.duration_seconds || form.duration_seconds < 1)) {
    ElMessage.warning('持续时长至少为 1 秒')
    return false
  }
  if (form.load_mode === 'duration' && form.warmup_seconds >= form.duration_seconds) {
    ElMessage.warning('预热时长必须小于压测持续时长')
    return false
  }
  if (
    form.load_mode === 'count'
    && form.target_rps
    && form.total_requests / form.target_rps > limits.value.max_duration_seconds
  ) {
    ElMessage.warning(
      `按目标 RPS=${form.target_rps} 跑 ${form.total_requests} 个请求会超过`
      + ` ${limits.value.max_duration_seconds} 秒上限`,
    )
    return false
  }
  return true
}

async function submit() {
  if (!validate()) return
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      case_id: form.case_id,
      env_id: form.env_id,
      load_mode: form.load_mode,
      total_requests: form.total_requests,
      duration_seconds: form.duration_seconds,
      concurrency: form.concurrency,
      target_rps: form.target_rps || null,
      warmup_seconds: form.warmup_seconds,
      request_timeout: form.request_timeout,
      verify_ssl: form.verify_ssl,
      error_rate_threshold: throttleEnabled.value ? form.error_rate_threshold : null,
      min_requests_before_abort: form.min_requests_before_abort,
    }
    if (isEdit.value) await updatePerfTask(props.taskId, payload)
    else await createPerfTask(props.projectId, payload)
    ElMessage.success(isEdit.value ? '已保存' : '已创建')
    emit('saved')
    visible.value = false
  } finally {
    submitting.value = false
  }
}

watch(visible, (open) => {
  if (open) load()
})
</script>

<template>
  <el-drawer v-model="visible" :title="isEdit ? '编辑压测任务' : '新建压测任务'" size="720px">
    <el-form v-loading="loading" label-width="110px">
      <el-form-item label="任务名称" required>
        <el-input v-model="form.name" placeholder="如：订单查询接口 · 50 并发基线" maxlength="128" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>

      <el-form-item label="接口用例" required>
        <el-select
          v-model="form.case_id"
          filterable
          remote
          :remote-method="onCaseSearch"
          :loading="loading"
          placeholder="搜索并选择一条接口用例"
          style="width: 100%"
          :no-data-text="caseKeyword ? '没有匹配的接口用例' : '该项目还没有接口用例'"
        >
          <el-option v-for="c in cases" :key="c.id" :label="caseLabel(c)" :value="c.id" />
        </el-select>
        <p v-if="caseTotal > cases.length" class="hint warn">
          该项目共 {{ caseTotal }} 条接口用例，当前只列出 {{ cases.length }} 条，请用关键字继续搜索。
        </p>
      </el-form-item>

      <el-form-item label="环境">
        <el-select v-model="form.env_id" placeholder="不使用环境" clearable style="width: 260px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <span class="hint inline">用于解析 URL 与请求头里的 ${变量}</span>
      </el-form-item>

      <el-form-item label="负载模式">
        <el-radio-group v-model="form.load_mode">
          <el-radio-button value="count">按总请求数</el-radio-button>
          <el-radio-button value="duration">按持续时长</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="form.load_mode === 'count'" label="总请求数">
        <el-input-number
          v-model="form.total_requests"
          :min="1"
          :max="limits.max_total_requests"
          :step="100"
          controls-position="right"
        />
        <span class="hint inline">上限 {{ limits.max_total_requests }}</span>
      </el-form-item>

      <el-form-item v-else label="持续时长">
        <el-input-number
          v-model="form.duration_seconds"
          :min="1"
          :max="limits.max_duration_seconds"
          :step="10"
          controls-position="right"
        />
        <span class="hint inline">秒，上限 {{ limits.max_duration_seconds }}</span>
      </el-form-item>

      <el-form-item label="并发数">
        <el-input-number
          v-model="form.concurrency"
          :min="1"
          :max="limits.max_concurrency"
          controls-position="right"
        />
        <span class="hint inline">上限 {{ limits.max_concurrency }}</span>
      </el-form-item>

      <el-form-item label="目标 RPS">
        <el-input-number
          v-model="form.target_rps"
          :min="1"
          :max="limits.max_rps"
          controls-position="right"
          placeholder="不限速"
        />
        <span class="hint inline">留空表示不限速；这是请求发起速率上限，实际 TPS 还受并发与延迟限制</span>
      </el-form-item>

      <el-collapse class="advanced">
        <el-collapse-item title="高级参数" name="advanced">
          <el-form-item label="预热时长">
            <el-input-number
              v-model="form.warmup_seconds"
              :min="0"
              :max="limits.max_warmup_seconds"
              controls-position="right"
            />
            <span class="hint inline">秒；预热请求不计入正式指标，用于建立连接</span>
          </el-form-item>
          <el-form-item label="单请求超时">
            <el-input-number
              v-model="form.request_timeout"
              :min="1"
              :max="limits.max_request_timeout"
              controls-position="right"
            />
            <span class="hint inline">秒，上限 {{ limits.max_request_timeout }}</span>
          </el-form-item>
          <el-form-item label="校验 SSL">
            <el-switch v-model="form.verify_ssl" />
          </el-form-item>
          <el-form-item label="错误率熔断">
            <el-switch v-model="throttleEnabled" />
            <el-input-number
              v-if="throttleEnabled"
              v-model="form.error_rate_threshold"
              :min="0"
              :max="100"
              :step="5"
              controls-position="right"
              style="margin-left: 12px"
            />
            <span class="hint inline">%；超过阈值会自动停止，避免继续冲击已故障的系统</span>
          </el-form-item>
          <el-form-item v-if="throttleEnabled" label="熔断生效请求数">
            <el-input-number
              v-model="form.min_requests_before_abort"
              :min="1"
              :max="10000"
              controls-position="right"
            />
            <span class="hint inline">至少跑这么多请求后，熔断才会生效（避免前几个偶发失败误停）</span>
          </el-form-item>
        </el-collapse-item>
      </el-collapse>

      <p class="hint note">
        压测只校验 HTTP 状态码，不执行响应体断言 —— JSONPath 解析会污染延迟指标。
        需要验证返回值，请先在「接口测试」里执行一次该用例。
      </p>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-3);
}

.hint.inline {
  margin: 0 0 0 10px;
  display: inline;
}

.hint.warn {
  color: var(--signal-warn);
}

.hint.note {
  margin-top: 14px;
  padding: 10px 12px;
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
}

.advanced {
  margin-top: 4px;
  border-top: 1px solid var(--border);
}
</style>
