<script setup>
/**
 * Web 用例的步骤编排器。
 *
 * 字段渲染完全由后端下发的 action.fields 驱动 —— 哪些操作需要定位、需要几个输入框，
 * 前端一概不判断（此前用 NO_INPUT_ACTIONS / WAIT_ACTIONS 两个 Set 硬编码，
 * 与后端各管一摊，是「前后端字段认知漂移」的温床）。
 *
 * 字段槽位（后端 field.name → 步骤字段）：
 *   locator        → locator_type / locator_value
 *   target_locator → target_locator_type / target_locator_value
 *   value          → input_value
 *   value2         → input_value2
 *   wait           → wait_seconds
 */
import { computed, ref } from 'vue'
import { Rank, ArrowDown, ArrowUp, CopyDocument, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  actions: { type: Array, default: () => [] },
  actionGroups: { type: Array, default: () => [] },
  locators: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const SLOT_KEYS = {
  locator: ['locator_type', 'locator_value'],
  target_locator: ['target_locator_type', 'target_locator_value'],
  value: ['input_value'],
  value2: ['input_value2'],
  wait: ['wait_seconds'],
}

const actionMap = computed(() =>
  Object.fromEntries(props.actions.map((a) => [a.value, a])),
)

function metaOf(step) {
  return actionMap.value[step.action_type] || {}
}

function fieldsOf(step) {
  return metaOf(step).fields || []
}

function labelOf(step) {
  return metaOf(step).label || step.action_type
}

/** 按下拉的分组把操作排好，供「添加步骤」面板渲染 */
const groupedActions = computed(() => {
  const order = props.actionGroups.length
    ? props.actionGroups
    : [...new Set(props.actions.map((a) => a.group).filter(Boolean))]
  return order
    .map((group) => ({ group, items: props.actions.filter((a) => a.group === group) }))
    .filter((g) => g.items.length)
})

// ---------- 步骤身份与折叠 ----------
// 用对象本身的稳定 id 作 v-for 的 key：上下移之后输入框焦点、折叠状态都跟着步骤走，
// 不会像用 index 作 key 那样「内容跟着位置跑」。
let seq = 0
const keyMap = new WeakMap()
function keyOf(step) {
  if (!keyMap.has(step)) keyMap.set(step, `step-${seq++}`)
  return keyMap.get(step)
}

const collapsed = ref(new Set())
function isCollapsed(step) {
  return collapsed.value.has(keyOf(step))
}
function toggleCollapse(step) {
  const next = new Set(collapsed.value)
  const key = keyOf(step)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  collapsed.value = next
}

// ---------- 校验高亮 ----------
// 记 key 而不是往 step 上写标记 —— step 是要存库的，不能混进 UI 状态
const problemKeys = ref(new Set())
function isProblem(step) {
  return problemKeys.value.has(keyOf(step))
}
function markProblem(step) {
  const next = new Set(problemKeys.value)
  next.add(keyOf(step))
  problemKeys.value = next
  collapsed.value = (() => {
    const s = new Set(collapsed.value)
    s.delete(keyOf(step))  // 出问题的步骤自动展开
    return s
  })()
}
function clearProblems() {
  problemKeys.value = new Set()
}

// ---------- 增删改 ----------
function blankStep(actionType) {
  return {
    step_order: 0,
    enabled: true,
    action_type: actionType,
    input_value: '',
    input_value2: '',
    wait_seconds: 0,
    description: '',
    locator_type: '',
    locator_value: '',
    target_locator_type: '',
    target_locator_value: '',
  }
}

function update(steps) {
  // step_order 只用来展示，真正的顺序由数组下标决定（提交时后端/编辑器会重排）
  emit('update:modelValue', steps.map((s, i) => ({ ...s, step_order: i + 1 })))
}

function addStep(actionType) {
  clearProblems()
  update([...props.modelValue, blankStep(actionType)])
}

function addAfter(index, actionType = 'open_url') {
  clearProblems()
  const next = props.modelValue.slice()
  next.splice(index + 1, 0, blankStep(actionType))
  update(next)
}

function duplicate(index) {
  clearProblems()
  const next = props.modelValue.slice()
  next.splice(index + 1, 0, { ...next[index] })
  update(next)
}

function removeStep(index) {
  clearProblems()
  const next = props.modelValue.slice()
  next.splice(index, 1)
  update(next)
}

function move(index, offset) {
  const target = index + offset
  if (target < 0 || target >= props.modelValue.length) return
  clearProblems()
  const next = props.modelValue.slice()
  ;[next[index], next[target]] = [next[target], next[index]]
  update(next)
}

/** 切换操作类型时清掉新操作不用的槽位，避免脏数据随步骤存进库里 */
function onActionChange(step) {
  clearProblems()
  const used = new Set(fieldsOf(step).map((f) => f.name))
  for (const [name, keys] of Object.entries(SLOT_KEYS)) {
    if (used.has(name)) continue
    if (name === 'wait') step.wait_seconds = 0
    else for (const key of keys) step[key] = ''
  }
  // 换成下拉选择时给个默认选择方式，省得用户还要手选
  if (used.has('value') && fieldsOf(step).find((f) => f.name === 'value')?.type === 'select') {
    step.input_value = step.input_value || 'label'
  }
}

// ---------- 拖拽排序 ----------
const dragIndex = ref(null)
const dropIndex = ref(null)

function onDragStart(index) {
  dragIndex.value = index
}

function onDragOver(index) {
  if (dragIndex.value === null) return
  dropIndex.value = index
}

function onDrop(index) {
  const from = dragIndex.value
  dragIndex.value = null
  dropIndex.value = null
  if (from === null || from === index) return
  clearProblems()
  const next = props.modelValue.slice()
  const [moved] = next.splice(from, 1)
  next.splice(index, 0, moved)
  update(next)
}

function onDragEnd() {
  dragIndex.value = null
  dropIndex.value = null
}

// ---------- 校验 ----------
/**
 * 某个字段此刻是否必填。
 * switch_iframe 填 default 表示退回主文档 —— 这一条例外与后端 validator 保持一致。
 */
function isRequired(step, field) {
  if (!field.required) return false
  if (field.name === 'locator' && step.action_type === 'switch_iframe') {
    return String(step.input_value || '').trim() !== 'default'
  }
  return true
}

function isFilled(step, field) {
  const keys = SLOT_KEYS[field.name]
  if (!keys) return true
  if (field.name === 'wait') return true  // 秒数留空按默认处理
  return keys.every((k) => String(step[k] ?? '').trim() !== '')
}

/**
 * 提交前校验启用中的步骤。返回第一条问题说明，全部合法时返回空串。
 * 挡的是「后端必然 422」的情况，让用户在前端就看到原因并定位到具体那一步。
 */
function validate() {
  clearProblems()
  for (let index = 0; index < props.modelValue.length; index += 1) {
    const step = props.modelValue[index]
    if (step.enabled === false) continue
    for (const field of fieldsOf(step)) {
      if (!isRequired(step, field) || isFilled(step, field)) continue
      markProblem(step)
      return `第 ${index + 1} 步「${labelOf(step)}」的「${field.label}」没有填写`
    }
  }
  return ''
}

defineExpose({ validate })
</script>

<template>
  <div class="step-editor">
    <div
      v-for="(step, index) in modelValue"
      :key="keyOf(step)"
      class="step-card"
      :class="{
        'is-collapsed': isCollapsed(step),
        'is-problem': isProblem(step),
        'is-dragging': dragIndex === index,
        'is-drop-target': dropIndex === index && dragIndex !== null && dragIndex !== index,
      }"
      @dragover.prevent="onDragOver(index)"
      @drop.prevent="onDrop(index)"
    >
      <div class="step-head">
        <span
          class="drag-handle"
          draggable="true"
          title="拖动排序"
          @dragstart="onDragStart(index)"
          @dragend="onDragEnd"
        >
          <el-icon><Rank /></el-icon>
        </span>

        <span class="step-no mono">{{ index + 1 }}</span>

        <el-select
          v-model="step.action_type"
          class="action-select"
          @change="onActionChange(step)"
        >
          <el-option-group
            v-for="g in groupedActions"
            :key="g.group"
            :label="g.group"
          >
            <el-option v-for="a in g.items" :key="a.value" :label="a.label" :value="a.value" />
          </el-option-group>
        </el-select>

        <el-checkbox v-model="step.enabled" class="step-enabled">启用</el-checkbox>

        <div class="step-ops">
          <el-tooltip content="折叠 / 展开" placement="top">
            <el-button link :icon="isCollapsed(step) ? ArrowDown : ArrowUp" @click="toggleCollapse(step)" />
          </el-tooltip>
          <el-tooltip content="复制到下方" placement="top">
            <el-button link :icon="CopyDocument" @click="duplicate(index)" />
          </el-tooltip>
          <el-button link :disabled="index === 0" @click="move(index, -1)">上移</el-button>
          <el-button link :disabled="index === modelValue.length - 1" @click="move(index, 1)">下移</el-button>
          <el-button link type="danger" :icon="Delete" @click="removeStep(index)" />
        </div>
      </div>

      <div v-show="!isCollapsed(step)" class="step-body">
        <div
          v-for="field in fieldsOf(step)"
          :key="field.name"
          class="field"
          :class="`field--${field.type}`"
        >
          <span class="field-label">{{ field.label }}</span>

          <!-- 元素定位：定位方式 + 定位值成对出现 -->
          <template v-if="field.type === 'locator'">
            <el-select v-model="step[SLOT_KEYS[field.name][0]]" class="locator-type" placeholder="定位方式">
              <el-option v-for="l in locators" :key="l.value" :label="l.label" :value="l.value" />
            </el-select>
            <el-input
              v-model="step[SLOT_KEYS[field.name][1]]"
              class="locator-value"
              placeholder="定位值，如 login-btn"
            />
          </template>

          <el-select
            v-else-if="field.type === 'select'"
            v-model="step[SLOT_KEYS[field.name][0]]"
            class="field-select"
          >
            <el-option
              v-for="opt in field.options || []"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>

          <el-input-number
            v-else-if="field.type === 'number'"
            v-model="step.wait_seconds"
            class="wait-input"
            :min="0"
            :max="300"
            :step="0.5"
            controls-position="right"
          />

          <el-input
            v-else
            v-model="step[SLOT_KEYS[field.name][0]]"
            :type="field.type === 'textarea' ? 'textarea' : 'text'"
            :rows="3"
            :placeholder="field.placeholder || ''"
            :class="{ 'input-value': field.type !== 'textarea', 'mono-input': field.type === 'textarea' }"
          />
        </div>

        <p v-if="!fieldsOf(step).length" class="no-field">这个操作不需要额外参数</p>
      </div>

      <div v-show="isCollapsed(step)" class="step-summary">
        <span v-for="field in fieldsOf(step)" :key="field.name" class="chip">
          {{ field.label }}：
          <b v-if="field.type === 'locator'" class="mono">
            {{ step[SLOT_KEYS[field.name][0]] || '—' }} = {{ step[SLOT_KEYS[field.name][1]] || '—' }}
          </b>
          <b v-else-if="field.type === 'number'" class="mono">{{ step.wait_seconds }}s</b>
          <b v-else class="mono">{{ step[SLOT_KEYS[field.name][0]] || '—' }}</b>
        </span>
        <span v-if="!fieldsOf(step).length" class="chip muted">无需参数</span>
      </div>
    </div>

    <div class="add-bar">
      <el-popover placement="top-start" trigger="click" :width="460">
        <template #reference>
          <el-button type="primary" plain>+ 添加步骤</el-button>
        </template>
        <div class="picker">
          <div v-for="g in groupedActions" :key="g.group" class="picker-group">
            <div class="picker-group__label">{{ g.group }}</div>
            <div class="picker-group__items">
              <el-button
                v-for="a in g.items"
                :key="a.value"
                size="small"
                class="picker-item"
                @click="addStep(a.value)"
              >
                {{ a.label }}
              </el-button>
            </div>
          </div>
        </div>
      </el-popover>

      <span class="add-hint">也可以点某一步上的复制按钮，在它下方插入一条同类型步骤</span>
    </div>

    <p class="hint">
      步骤按顺序执行，只有勾选「启用」的才会跑；拖动手柄可调整顺序。URL、输入值、定位值都支持
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
  transition: border-color 0.15s ease, opacity 0.15s ease;
}

.step-card.is-problem {
  border-color: var(--signal-fail);
  background: var(--signal-fail-bg);
}

.step-card.is-dragging {
  opacity: 0.4;
}

.step-card.is-drop-target {
  border-color: var(--brand-500);
  border-style: dashed;
}

.step-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drag-handle {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  color: var(--text-3);
  cursor: grab;
}

.drag-handle:active {
  cursor: grabbing;
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
  width: 168px;
  flex-shrink: 0;
}

.step-enabled {
  flex-shrink: 0;
}

.step-ops {
  margin-left: auto;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
}

.step-body {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
  margin-top: 10px;
  padding-left: 30px;
}

.field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-2);
  white-space: nowrap;
}

.field--locator {
  flex-wrap: wrap;
}

.locator-type {
  width: 148px;
  flex-shrink: 0;
}

.locator-value {
  width: 210px;
  flex-shrink: 0;
}

.field-select {
  width: 160px;
}

.wait-input {
  width: 138px;
}

.input-value {
  width: 300px;
}

.mono-input {
  flex: 1;
  min-width: 260px;
}

.mono-input :deep(textarea) {
  font-family: var(--font-mono);
  font-size: 13px;
}

.no-field {
  margin: 0;
  font-size: 12px;
  color: var(--text-3);
}

.step-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  padding-left: 30px;
}

.chip {
  font-size: 12px;
  color: var(--text-2);
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1px 9px;
}

.chip.muted {
  color: var(--text-3);
}

.add-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 2px;
}

.add-hint {
  font-size: 12px;
  color: var(--text-3);
}

.picker {
  max-height: 380px;
  overflow-y: auto;
}

.picker-group {
  margin-bottom: 12px;
}

.picker-group:last-child {
  margin-bottom: 0;
}

.picker-group__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-3);
  margin-bottom: 6px;
}

.picker-group__items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.picker-item {
  margin: 0;
}

.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
}
</style>
