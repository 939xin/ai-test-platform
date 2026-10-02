<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { listCases } from '@/api/case'
import { listEnvironments } from '@/api/environment'
import { createPlan, getPlan, updatePlan } from '@/api/plan'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  // 传了就是编辑，否则是新建
  planId: { type: Number, default: null },
  projectId: { type: Number, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEdit = computed(() => props.planId != null)

const cases = ref([])
const environments = ref([])
const loading = ref(false)
const submitting = ref(false)

const form = reactive({ name: '', description: '', env_id: null })

// 选中的用例 id。自己维护而不是用 el-table 的 selection：
// 表格在筛选/翻页重渲染时内置勾选会丢，用数组更稳，也方便回填。
const selectedIds = ref([])

const keyword = ref('')
const typeFilter = ref('')

const filteredCases = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return cases.value.filter((c) => {
    if (typeFilter.value && c.type !== typeFilter.value) return false
    if (kw && !c.name.toLowerCase().includes(kw)) return false
    return true
  })
})

const selectedCount = computed(() => selectedIds.value.length)
const allFilteredSelected = computed(
  () => filteredCases.value.length > 0
    && filteredCases.value.every((c) => selectedIds.value.includes(c.id)),
)

function isSelected(id) {
  return selectedIds.value.includes(id)
}

function toggle(id) {
  const index = selectedIds.value.indexOf(id)
  if (index >= 0) selectedIds.value.splice(index, 1)
  else selectedIds.value.push(id)
}

/** 全选 / 取消全选只作用于当前筛选出来的用例，不碰被筛掉的那些。 */
function toggleAll() {
  if (allFilteredSelected.value) {
    const filtered = new Set(filteredCases.value.map((c) => c.id))
    selectedIds.value = selectedIds.value.filter((id) => !filtered.has(id))
  } else {
    const merged = new Set(selectedIds.value)
    filteredCases.value.forEach((c) => merged.add(c.id))
    selectedIds.value = [...merged]
  }
}

function typeLabel(type) {
  return type === 'web' ? 'Web' : '接口'
}

async function load() {
  loading.value = true
  try {
    const [caseList, envList] = await Promise.all([
      listCases(props.projectId),
      listEnvironments(props.projectId),
    ])
    cases.value = caseList
    environments.value = envList
    keyword.value = ''
    typeFilter.value = ''

    if (!isEdit.value) {
      Object.assign(form, { name: '', description: '', env_id: null })
      selectedIds.value = []
      return
    }
    const data = await getPlan(props.planId)
    Object.assign(form, { name: data.name, description: data.description, env_id: data.env_id })
    selectedIds.value = data.cases.map((c) => c.case_id)
  } finally {
    loading.value = false
  }
}

async function submit() {
  if (!String(form.name).trim()) {
    ElMessage.warning('请填写计划名称')
    return
  }
  if (!selectedIds.value.length) {
    ElMessage.warning('至少选择一条用例')
    return
  }
  submitting.value = true
  try {
    // 按用例列表的原有顺序提交，顺序稳定（计划本身不依赖顺序）
    const payload = {
      name: form.name,
      description: form.description,
      env_id: form.env_id,
      cases: cases.value
        .filter((c) => selectedIds.value.includes(c.id))
        .map((c) => ({ case_id: c.id })),
    }
    if (isEdit.value) await updatePlan(props.planId, payload)
    else await createPlan(props.projectId, payload)
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
  <el-drawer v-model="visible" :title="isEdit ? '编辑计划' : '新建计划'" size="820px">
    <el-form v-loading="loading" label-width="90px">
      <el-form-item label="计划名称" required>
        <el-input v-model="form.name" placeholder="如：每日冒烟 · 核心接口 + 登录流程" maxlength="128" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="选填" />
      </el-form-item>
      <el-form-item label="默认环境">
        <el-select v-model="form.env_id" placeholder="不使用环境" clearable style="width: 240px">
          <el-option v-for="e in environments" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
      </el-form-item>

      <el-form-item label="用例清单">
        <div class="picker">
          <div class="picker-bar">
            <el-input v-model="keyword" placeholder="按名称搜索" clearable style="width: 190px" />
            <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 130px">
              <el-option label="接口" value="api" />
              <el-option label="Web" value="web" />
            </el-select>
            <el-button link type="primary" @click="toggleAll">
              {{ allFilteredSelected ? '取消全选' : '全选当前筛选' }}
            </el-button>
            <span class="picker-count">
              已选 <b class="mono">{{ selectedCount }}</b> 条
            </span>
          </div>

          <el-table :data="filteredCases" max-height="330" size="small" stripe>
            <el-table-column label="选择" width="58">
              <template #default="{ row }">
                <el-checkbox :model-value="isSelected(row.id)" @change="toggle(row.id)" />
              </template>
            </el-table-column>
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="用例名称" min-width="220" show-overflow-tooltip />
            <el-table-column label="类型" width="70">
              <template #default="{ row }">{{ typeLabel(row.type) }}</template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="78" />
            <template #empty>
              <el-empty description="没有符合条件的用例" :image-size="60" />
            </template>
          </el-table>

          <p class="hint">
            计划里的用例各跑各的、互不影响。需要「上一步提取的变量传给下一步」请用「场景测试」。
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
.picker {
  width: 100%;
}

.picker-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.picker-count {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--text-3);
}

.picker-count b {
  color: var(--brand-700);
}

.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.6;
}
</style>
