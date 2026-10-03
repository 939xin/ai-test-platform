<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { listCases } from '@/api/case'
import { createScenario, getScenario, updateScenario } from '@/api/scenario'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 传了就是编辑，否则是新建
  scenarioId: { type: Number, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEdit = computed(() => props.scenarioId != null)

/**
 * 下拉一次取多少条用例。
 *
 * 用例列表接口现在分页了（默认 20 条），下拉只取一页的话后面那些用例根本选不到。
 * 直接顶到后端上限（MAX_PAGE_SIZE = 200），取不全时下面会提示。
 */
const PICKER_LIMIT = 200

const cases = ref([])
const caseTotal = ref(0)
const loading = ref(false)
const submitting = ref(false)

const form = reactive({ name: '', description: '', steps: [] })

const FAIL_STRATEGIES = [
  { value: 'stop', label: '中止场景' },
  { value: 'continue', label: '继续执行' },
]

function resetForm() {
  Object.assign(form, { name: '', description: '', steps: [] })
}

async function loadCases() {
  if (props.projectId == null) {
    cases.value = []
    return
  }
  // 只列接口用例：场景串联执行的是 api_executor，Web 用例放进来跑不通。
  // 之前混着列出来，选中之后执行必然失败。
  const data = await listCases(props.projectId, { type: 'api', limit: PICKER_LIMIT })
  cases.value = data.items
  caseTotal.value = data.total
}

async function load() {
  loading.value = true
  try {
    await loadCases()
    if (!isEdit.value) {
      resetForm()
      return
    }
    const data = await getScenario(props.scenarioId)
    Object.assign(form, {
      name: data.name,
      description: data.description,
      steps: (data.steps || []).map((s) => ({
        case_id: s.case_id,
        enabled: s.enabled,
        fail_strategy: s.fail_strategy,
      })),
    })
  } finally {
    loading.value = false
  }
}

function addStep() {
  form.steps.push({ case_id: null, enabled: true, fail_strategy: 'stop' })
}

function removeStep(index) {
  form.steps.splice(index, 1)
}

/** 上移 / 下移：顺序就是执行顺序，改完 step_order 由后端按数组顺序重排。 */
function moveStep(index, offset) {
  const target = index + offset
  if (target < 0 || target >= form.steps.length) return
  const [item] = form.steps.splice(index, 1)
  form.steps.splice(target, 0, item)
}

async function submit() {
  if (!String(form.name).trim()) {
    ElMessage.warning('请填写场景名称')
    return
  }
  if (!form.steps.length) {
    ElMessage.warning('至少添加一个步骤')
    return
  }
  if (form.steps.some((s) => !s.case_id)) {
    ElMessage.warning('有步骤还没选用例')
    return
  }
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      description: form.description,
      steps: form.steps.map((s) => ({
        case_id: s.case_id,
        enabled: s.enabled,
        fail_strategy: s.fail_strategy,
      })),
    }
    if (isEdit.value) {
      await updateScenario(props.scenarioId, payload)
    } else {
      await createScenario(props.projectId, payload)
    }
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
  <el-drawer
    v-model="visible"
    :title="isEdit ? '编辑场景' : '新建场景'"
    size="760px"
  >
    <el-form v-loading="loading" label-width="90px">
      <el-form-item label="场景名称" required>
        <el-input v-model="form.name" placeholder="如：登录 → 下单 → 查询订单" maxlength="128" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>

      <el-form-item label="执行步骤">
        <div class="steps">
          <div v-for="(step, index) in form.steps" :key="index" class="step-row">
            <span class="step-index mono">{{ index + 1 }}</span>
            <el-select v-model="step.case_id" placeholder="选择用例" class="step-case" filterable>
              <el-option v-for="c in cases" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-select v-model="step.fail_strategy" class="step-strategy">
              <el-option v-for="f in FAIL_STRATEGIES" :key="f.value" :label="f.label" :value="f.value" />
            </el-select>
            <el-checkbox v-model="step.enabled">启用</el-checkbox>
            <div class="step-actions">
              <el-button link :disabled="index === 0" @click="moveStep(index, -1)">上移</el-button>
              <el-button link :disabled="index === form.steps.length - 1" @click="moveStep(index, 1)">
                下移
              </el-button>
              <el-button link type="danger" @click="removeStep(index)">移除</el-button>
            </div>
          </div>

          <el-button link type="primary" @click="addStep">+ 添加步骤</el-button>
          <p v-if="caseTotal > cases.length" class="truncated">
            该项目共 {{ caseTotal }} 条接口用例，下拉里只列出前 {{ cases.length }} 条。
          </p>
          <p class="hint">
            按顺序执行；某一步提取到的变量（用例的「提取变量」Tab）可以在后续步骤里用
            <code>${变量名}</code> 引用。
          </p>
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
.steps {
  width: 100%;
}

.step-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.step-index {
  width: 20px;
  flex-shrink: 0;
  font-weight: 600;
  color: var(--text-3);
}

.step-case {
  flex: 1;
  min-width: 0;
}

.step-strategy {
  width: 118px;
  flex-shrink: 0;
}

.step-actions {
  display: flex;
  flex-shrink: 0;
}

.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}

/* 用例被截断时才出现 —— 用告警色，别让它混在下面那行灰字提示里 */
.truncated {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--signal-warn);
  line-height: 1.6;
}
</style>
