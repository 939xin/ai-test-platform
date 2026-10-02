<script setup>
/**
 * Web 用例的步骤编排器。
 *
 * 每个步骤一张卡片：第一行是「序号 + 操作类型 + 启用 + 排序」，第二行按操作类型
 * 动态显示需要的字段 —— 要不要显示定位方式由后端下发的 needs_locator 决定，
 * 前端不自己判断（操作与定位的枚举定义在 services/web_executor.py）。
 */
const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  actions: { type: Array, default: () => [] },
  locators: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

/** 这几种操作不看「输入值」，界面上不显示该输入框 */
const NO_INPUT_ACTIONS = new Set(['click', 'clear', 'scroll_to', 'force_wait'])
/** 这两种操作用「等待秒数」，而不是「输入值」 */
const WAIT_ACTIONS = new Set(['force_wait', 'smart_wait'])

const INPUT_PLACEHOLDERS = {
  open_url: '完整 URL，可含 ${变量}，如 ${base_url}/login',
  input: '要输入的文本，可含 ${变量}',
  switch_window: '窗口序号（从 0 开始）或标题关键字',
  switch_iframe: '填 default 退回主文档；留空则按下方定位切换',
  execute_js: '要执行的 JS，如 window.scrollTo(0, 0);',
  screenshot: '截图文件名（可选）',
  assert_text_contains: '期望包含的文本，可含 ${变量}',
  assert_visible: 'true / false（留空按 true）',
  assert_exists: 'true / false（留空按 true）',
  extract_variable: '变量名，如 welcome_text',
}

function actionMeta(step) {
  return props.actions.find((a) => a.value === step.action_type) || {}
}

function needsLocator(step) {
  return Boolean(actionMeta(step).needs_locator)
}

function needsWait(step) {
  return WAIT_ACTIONS.has(step.action_type)
}

function needsInput(step) {
  return !NO_INPUT_ACTIONS.has(step.action_type)
}

/** switch_iframe 的输入值填 default 表示退回主文档，此时不需要定位信息（与后端一致） */
function isBackToDefaultFrame(step) {
  return step.action_type === 'switch_iframe' && String(step.input_value || '').trim() === 'default'
}

function showLocator(step) {
  return needsLocator(step) && !isBackToDefaultFrame(step)
}

/** 切换操作类型时清掉该操作不用的字段，避免把用不上的值存进库里 */
function onActionChange(step) {
  if (!needsLocator(step)) {
    step.locator_type = ''
    step.locator_value = ''
  }
  if (!needsWait(step)) step.wait_seconds = 0
  if (!needsInput(step)) step.input_value = ''
}

function addStep() {
  emit('update:modelValue', [
    ...props.modelValue,
    {
      step_order: props.modelValue.length + 1,
      enabled: true,
      action_type: 'open_url',
      input_value: '',
      wait_seconds: 0,
      description: '',
      locator_type: '',
      locator_value: '',
    },
  ])
}

function removeStep(index) {
  const next = props.modelValue.slice()
  next.splice(index, 1)
  emit('update:modelValue', next)
}

function move(index, offset) {
  const next = props.modelValue.slice()
  const target = index + offset
  const current = next[index]
  next[index] = next[target]
  next[target] = current
  emit('update:modelValue', next)
}

/**
 * 提交前校验启用中的步骤。返回第一条问题说明，全部合法时返回空串。
 * 挡的是「后端必然 422」的两种情况，让用户在前端就看到原因。
 */
function validate() {
  for (let index = 0; index < props.modelValue.length; index += 1) {
    const step = props.modelValue[index]
    if (step.enabled === false) continue
    const label = actionMeta(step).label || step.action_type
    if (showLocator(step) && !(step.locator_type && String(step.locator_value || '').trim())) {
      return `第 ${index + 1} 步「${label}」缺少元素定位信息`
    }
    if (step.action_type === 'open_url' && !String(step.input_value || '').trim()) {
      return `第 ${index + 1} 步「打开 URL」没有填写 URL`
    }
  }
  return ''
}

defineExpose({ validate })
</script>

<template>
  <div class="step-editor">
    <div v-for="(step, index) in modelValue" :key="index" class="step-card">
      <div class="step-head">
        <span class="step-no mono">{{ index + 1 }}</span>
        <el-select v-model="step.action_type" class="action-select" @change="onActionChange(step)">
          <el-option v-for="a in actions" :key="a.value" :label="a.label" :value="a.value" />
        </el-select>
        <el-checkbox v-model="step.enabled" class="step-enabled">启用</el-checkbox>
        <div class="step-ops">
          <el-button link :disabled="index === 0" @click="move(index, -1)">上移</el-button>
          <el-button link :disabled="index === modelValue.length - 1" @click="move(index, 1)">
            下移
          </el-button>
          <el-button link type="danger" @click="removeStep(index)">删除</el-button>
        </div>
      </div>

      <div class="step-body">
        <template v-if="showLocator(step)">
          <el-select v-model="step.locator_type" class="locator-type" placeholder="定位方式">
            <el-option v-for="l in locators" :key="l.value" :label="l.label" :value="l.value" />
          </el-select>
          <el-input
            v-model="step.locator_value"
            class="locator-value"
            placeholder="定位值，如 login-btn"
          />
        </template>

        <el-input-number
          v-if="needsWait(step)"
          v-model="step.wait_seconds"
          class="wait-input"
          :min="0"
          :max="300"
          :step="0.5"
          controls-position="right"
        />

        <el-input
          v-if="needsInput(step)"
          v-model="step.input_value"
          :type="step.action_type === 'execute_js' ? 'textarea' : 'text'"
          :rows="2"
          class="input-value"
          :placeholder="INPUT_PLACEHOLDERS[step.action_type] || '输入值'"
        />
      </div>
    </div>

    <el-button link type="primary" class="add-step" @click="addStep">+ 添加步骤</el-button>
    <p class="hint">
      步骤按顺序执行，只有勾选「启用」的才会跑。URL、输入值、定位值都支持
      <code>${变量名}</code>（环境变量或上一步提取的变量）。
    </p>
  </div>
</template>

<style scoped>
.step-editor {
  width: 100%;
}

.step-card {
  padding: 10px 12px;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #fafcfc;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-no {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  line-height: 22px;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: var(--brand-700);
  border-radius: 50%;
}

.action-select {
  width: 150px;
  flex-shrink: 0;
}

.step-enabled {
  flex-shrink: 0;
}

.step-ops {
  margin-left: auto;
  flex-shrink: 0;
}

.step-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.locator-type {
  width: 150px;
  flex-shrink: 0;
}

.locator-value {
  width: 220px;
  flex-shrink: 0;
}

.wait-input {
  width: 140px;
  flex-shrink: 0;
}

.input-value {
  flex: 1;
  min-width: 200px;
}

.add-step {
  margin-top: 2px;
}

.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
}
</style>
