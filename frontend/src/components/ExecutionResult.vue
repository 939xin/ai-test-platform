<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, Warning } from '@element-plus/icons-vue'

import AiAnalysisDialog from '@/components/AiAnalysisDialog.vue'
import StatusTag from '@/components/StatusTag.vue'
import { analyzeFailure } from '@/api/ai'
import { createDefectFromExecution } from '@/api/defect'

const props = defineProps({
  // 一次执行记录（ExecutionOut）：{ status, duration_ms, result_json }
  execution: { type: Object, required: true },
})

// 提完缺陷后由父组件负责跳转到缺陷页
const emit = defineEmits(['goto-defect'])

const defectSubmitting = ref(false)

// 只有失败 / 错误才值得提缺陷，通过的执行记录后端也会拒
const canRaiseDefect = computed(
  () => props.execution.status === 'fail' || props.execution.status === 'error',
)

async function raiseDefect() {
  if (defectSubmitting.value) return
  defectSubmitting.value = true
  try {
    const defect = await createDefectFromExecution(props.execution.id)
    ElMessage.success(`已创建缺陷 #${defect.id}`)
    emit('goto-defect', defect.id)
  } catch (error) {
    // 409：这条执行已经提过缺陷，后端把已有缺陷 id 放在 detail 里，直接跳过去
    const detail = error.response?.data?.detail
    if (error.response?.status === 409 && detail?.defect_id) {
      emit('goto-defect', detail.defect_id)
    }
  } finally {
    defectSubmitting.value = false
  }
}

// 提取到的变量：{变量名: 值}，没配提取规则时为空
const extracted = computed(() => props.execution.result_json?.extracted || {})
const extractErrors = computed(() => props.execution.result_json?.extract_errors || [])
const hasExtract = computed(
  () => Object.keys(extracted.value).length > 0 || extractErrors.value.length > 0,
)

// Web 用例的结果里是 steps（步骤级明细），接口用例是 request/response/assertions
const steps = computed(() => props.execution.result_json?.steps || [])
const isWeb = computed(() => steps.value.length > 0)

// ---------- AI 失败分析 ----------
const analyzing = ref(false)
const analysisVisible = ref(false)
const analysis = ref(null)

/**
 * 是否接口执行。优先用后端按 case_id 回查的 case_type；
 * 拿不到这个字段时（刚跑完用例的接口直接返回 ORM 记录，没有该属性）
 * 退回上面那个启发式判断 —— 这两种场景下 steps 的有无正好等价于类型。
 */
const isApiExecution = computed(() => {
  if (props.execution.case_type) return props.execution.case_type === 'api'
  return !isWeb.value
})

// ---------- 登录态 ----------
// 只有 Web 执行会有这一段；改造之前的历史执行记录里没有这个键。
// 后端总是给同一副骨架（各字段都有默认值），所以判断"要不要提示"看的是值，
// 不是键在不在。
const sessionInfo = computed(() => props.execution.result_json?.session || null)

/** 返回 null 表示这次执行跟登录态无关，不必占版面 */
const sessionNote = computed(() => {
  const s = sessionInfo.value
  if (!s) return null

  if (s.error) {
    return {
      type: 'error',
      title: '登录态处理失败',
      text: `${s.error}（本次按「未登录」继续执行，下面的步骤结果仅供参考）`,
    }
  }
  if (s.missing) {
    return {
      type: 'warning',
      title: '没有可用的登录态',
      text: '本项目还没有保存过登录态，或者刚被清除。把一条用例勾上「作为登录用例」跑一次，再重跑本条。',
    }
  }
  if (s.captured) {
    return {
      type: 'success',
      title: '已保存登录态',
      text: `导出 cookie ${s.cookies_total} 项、localStorage ${s.local_storage} 项、`
        + `sessionStorage ${s.session_storage} 项，本项目其他用例可直接复用。`,
    }
  }
  if (s.used) {
    const detail = `cookie ${s.cookies_added}/${s.cookies_total} 项、`
      + `localStorage ${s.local_storage} 项、sessionStorage ${s.session_storage} 项`
    return {
      type: s.expired ? 'warning' : 'info',
      title: '已注入登录态',
      text: `注入 ${detail}。`
        + (s.expired ? '这个登录态的 cookie 已过期，本条若失败建议重跑登录用例。' : ''),
    }
  }
  return null
})

// 对通过的执行分析「失败原因」没有意义，所以条件与旁边的「提缺陷」保持一致
const canAnalyzeFailure = computed(
  () =>
    isApiExecution.value &&
    (props.execution.status === 'fail' || props.execution.status === 'error'),
)

async function analyzeFailureNow() {
  if (analyzing.value) return
  analyzing.value = true
  try {
    analysis.value = await analyzeFailure({ execution_id: props.execution.id })
    analysisVisible.value = true
  } finally {
    analyzing.value = false
  }
}

/**
 * 截图存的是相对 report_dir 的路径（screenshots/execution_12/step_01_xxx.png），
 * /api 已被 vite 代理到后端，拼出来的 URL 正好命中截图路由。
 */
function screenshotUrl(path) {
  return `/api/reports/${path}`
}

function prettyJson(value) {
  if (value == null || value === '') return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <div class="exec-result">
    <div class="result-summary">
      <StatusTag :status="execution.status" />
      <span class="mono summary-item">耗时 {{ execution.duration_ms }} ms</span>
      <span v-if="execution.result_json?.error_msg" class="mono error">
        {{ execution.result_json.error_msg }}
      </span>
      <el-button
        v-if="canAnalyzeFailure"
        class="summary-actions"
        plain
        size="small"
        :icon="MagicStick"
        :loading="analyzing"
        @click="analyzeFailureNow"
      >
        AI 分析失败
      </el-button>
      <el-button
        v-if="canRaiseDefect"
        class="summary-actions"
        type="primary"
        plain
        size="small"
        :icon="Warning"
        :loading="defectSubmitting"
        @click="raiseDefect"
      >
        提缺陷
      </el-button>
    </div>

    <el-tabs>
      <!-- Web 用例：逐步列出执行过程，失败步骤带自动截图 -->
      <el-tab-pane v-if="isWeb" :label="`执行步骤 (${steps.length})`">
        <el-alert
          v-if="sessionNote"
          :type="sessionNote.type"
          :title="sessionNote.title"
          :description="sessionNote.text"
          show-icon
          :closable="false"
          class="session-alert"
        />

        <div
          v-for="step in steps"
          :key="step.step_order"
          class="step-item"
          :class="step.status === 'pass' ? 'is-pass' : 'is-fail'"
        >
          <div class="step-line">
            <span class="mono step-order">{{ step.step_order }}</span>
            <StatusTag :status="step.status" />
            <span class="step-desc">{{ step.desc }}</span>
            <span class="mono step-duration">{{ step.duration_ms }} ms</span>
          </div>
          <div v-if="step.message" class="mono step-message">{{ step.message }}</div>
          <div v-if="step.screenshots?.length" class="shot-list">
            <a
              v-for="shot in step.screenshots"
              :key="shot"
              :href="screenshotUrl(shot)"
              target="_blank"
              class="shot-link"
            >
              <img :src="screenshotUrl(shot)" class="shot-img" alt="步骤截图" />
            </a>
          </div>
        </div>
      </el-tab-pane>

      <!-- 接口用例：请求 / 响应 / 断言 -->
      <template v-else>
        <el-tab-pane label="请求">
          <div class="mono block">
            {{ execution.result_json?.request?.method }} {{ execution.result_json?.request?.url }}
          </div>
          <div class="label">请求头</div>
          <pre class="mono pre">{{ prettyJson(execution.result_json?.request?.headers) }}</pre>
          <template v-if="execution.result_json?.request?.body">
            <div class="label">请求体</div>
            <pre class="mono pre">{{ execution.result_json.request.body }}</pre>
          </template>
        </el-tab-pane>

        <el-tab-pane label="响应">
          <div class="label">状态码</div>
          <div class="mono block">{{ execution.result_json?.response?.status }}</div>
          <div class="label">响应体</div>
          <pre class="mono pre tall">{{ prettyJson(execution.result_json?.response?.body) }}</pre>
        </el-tab-pane>

        <el-tab-pane :label="`断言 (${execution.result_json?.assertions?.length || 0})`">
          <div
            v-for="(a, i) in execution.result_json?.assertions || []"
            :key="i"
            class="assert-item"
            :class="a.passed ? 'is-pass' : 'is-fail'"
          >
            <span class="assert-mark">{{ a.passed ? '✓' : '✗' }}</span>
            <span class="mono assert-text">{{ a.message }}</span>
          </div>
          <el-empty
            v-if="!execution.result_json?.assertions?.length"
            description="该用例没有断言条件"
            :image-size="60"
          />
        </el-tab-pane>
      </template>

      <el-tab-pane v-if="hasExtract" :label="`变量 (${Object.keys(extracted).length})`">
        <div
          v-for="(value, name) in extracted"
          :key="name"
          class="extract-item"
          :class="value === null ? 'is-missing' : 'is-found'"
        >
          <span class="mono extract-name">{{ name }}</span>
          <span class="mono extract-value">{{ value === null ? '未匹配到值' : value }}</span>
        </div>
        <div v-for="(err, i) in extractErrors" :key="`e${i}`" class="extract-error">
          <span class="mono">{{ err }}</span>
        </div>
        <p class="extract-hint">
          这些变量可在后续用例里用 <code>${变量名}</code> 引用；提取失败不影响用例结果。
        </p>
      </el-tab-pane>
    </el-tabs>

    <AiAnalysisDialog v-model="analysisVisible" :analysis="analysis" />
  </div>
</template>

<style scoped>
.session-alert {
  margin-bottom: 12px;
}

.result-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.summary-item {
  font-size: 13px;
  color: var(--text-2);
}

/* 按钮推到最右，与左侧状态 / 耗时拉开 */
.summary-actions {
  margin-left: auto;
}

.error {
  font-size: 12px;
  color: var(--signal-fail);
}

.label {
  margin: 10px 0 4px;
  font-size: 12px;
  color: var(--text-3);
}

.block {
  font-size: 13px;
  color: var(--text-1);
  word-break: break-all;
}

.pre {
  margin: 0;
  padding: 10px;
  max-height: 200px;
  overflow: auto;
  font-size: 12.5px;
  line-height: 1.55;
  background: #f7f9fa;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  white-space: pre-wrap;
  word-break: break-all;
}

.pre.tall {
  max-height: 300px;
}

/* ---------- Web 执行步骤 ---------- */
.step-item {
  padding: 8px 10px;
  margin-bottom: 6px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  font-size: 12.5px;
}

.step-item.is-pass {
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.step-item.is-fail {
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
}

.step-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-order {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  font-size: 11.5px;
  font-weight: 600;
  color: #fff;
  background: var(--brand-700);
  border-radius: 50%;
}

.step-desc {
  flex: 1;
  min-width: 0;
  color: var(--text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-duration {
  flex-shrink: 0;
  color: var(--text-3);
}

.step-message {
  margin: 6px 0 0 28px;
  color: var(--signal-fail);
  word-break: break-all;
}

.shot-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0 0 28px;
}

.shot-link {
  display: block;
  line-height: 0;
}

.shot-img {
  max-width: 220px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: zoom-in;
}

.assert-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  padding: 7px 10px;
  margin-bottom: 6px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 12.5px;
}

.assert-item.is-pass {
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
  color: #1f6d4a;
}

.assert-item.is-fail {
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
  color: #a12f2f;
}

.assert-mark {
  font-weight: 700;
}

.extract-item {
  display: flex;
  gap: 10px;
  align-items: baseline;
  padding: 7px 10px;
  margin-bottom: 6px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 12.5px;
}

.extract-item.is-found {
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.extract-item.is-missing {
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

.extract-name {
  font-weight: 600;
  color: var(--text-1);
  flex-shrink: 0;
}

.extract-value {
  color: var(--text-2);
  word-break: break-all;
}

.extract-error {
  padding: 6px 10px;
  margin-bottom: 4px;
  font-size: 12px;
  color: var(--signal-warn);
}

.extract-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
}
</style>
