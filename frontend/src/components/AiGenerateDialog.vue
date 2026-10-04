<script setup>
/**
 * 「AI 生成用例」弹窗：输入接口文档 → 生成 → 勾选 → 保存。
 *
 * 生成结果不直接入库，必须勾选后才保存 —— AI 编出来的用例直接进用例库，
 * 库很快就没法看了。保存走的是既有的用例创建接口（后端 GeneratedCase 的字段
 * 就是照着 TestCaseCreate 设计的），所以这里没有 AI 专属的保存接口。
 */
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'

import { generateCases } from '@/api/ai'
import { createCase } from '@/api/case'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const docText = ref('')
const hint = ref('')
const count = ref(5)
const generating = ref(false)
const saving = ref(false)
const cases = ref([])
const selected = ref([])

const canGenerate = computed(() => Boolean(docText.value.trim()) && props.projectId != null)
const selectedCount = computed(() => selected.value.length)

function assertionCount(row) {
  return (row.assertions_json || []).length
}

async function onGenerate() {
  if (!canGenerate.value) return
  generating.value = true
  try {
    const data = await generateCases({
      project_id: props.projectId,
      doc_text: docText.value,
      hint: hint.value,
      count: count.value,
    })
    // _key 给表格的 row-key；_saved 标记是否已入库（已保存的行不能再勾）
    cases.value = data.cases.map((item, index) => ({
      ...item,
      _key: `${data.task_id}-${index}`,
      _saved: false,
    }))
    selected.value = []
    ElMessage.success(data.message || `生成 ${data.cases.length} 条用例`)
  } finally {
    generating.value = false
  }
}

function onSelectionChange(rows) {
  selected.value = rows.filter((row) => !row._saved)
}

/** 保存时剔除前端自己加的两个字段，并补上接口用例类型。 */
function toPayload(row) {
  const { _key, _saved, ...rest } = row
  return { ...rest, type: 'api' }
}

async function saveSelected() {
  const rows = selected.value.filter((row) => !row._saved)
  if (!rows.length) return

  saving.value = true
  let saved = 0
  try {
    for (const row of rows) {
      try {
        await createCase(props.projectId, toPayload(row))
        row._saved = true
        saved += 1
      } catch {
        // request.js 已经弹过具体错误，这里继续保存剩下的，不因一条失败全断
      }
    }
  } finally {
    saving.value = false
  }

  selected.value = []
  if (saved) {
    ElMessage.success(`已保存 ${saved} 条接口用例`)
    emit('saved', saved)
  }
  if (saved < rows.length) {
    ElMessage.warning(`另有 ${rows.length - saved} 条保存失败，可重试`)
  }
}

// 换项目后上一批生成结果不再适用，清掉；否则会稀里糊涂存进另一个项目
watch(
  () => props.projectId,
  () => {
    cases.value = []
    selected.value = []
  },
)
</script>

<template>
  <el-dialog v-model="visible" title="AI 生成用例" width="920px" top="6vh">
    <el-input
      v-model="docText"
      type="textarea"
      :rows="7"
      resize="vertical"
      placeholder="粘贴接口文档（Swagger / OpenAPI 片段）或直接用自然语言描述接口，例如：&#10;接口地址：POST http://httpbin.org/post&#10;请求体：{&quot;username&quot;: &quot;字符串&quot;, &quot;password&quot;: &quot;字符串&quot;}&#10;成功：200，响应体 {&quot;code&quot;: 0, &quot;token&quot;: &quot;字符串&quot;}&#10;失败：401，响应体 {&quot;code&quot;: 1001, &quot;msg&quot;: &quot;用户名或密码错误&quot;}"
    />

    <div class="gen-actions">
      <el-input v-model="hint" placeholder="附加要求（可选），如「多覆盖边界值」" style="width: 280px" />
      <span class="gen-label">生成条数</span>
      <el-input-number v-model="count" :min="1" :max="20" controls-position="right" style="width: 110px" />
      <el-button
        type="primary"
        :icon="MagicStick"
        :loading="generating"
        :disabled="!canGenerate"
        @click="onGenerate"
      >
        AI 生成
      </el-button>
    </div>

    <div v-if="cases.length" class="gen-result">
      <div class="gen-result__head">
        <span>
          共 {{ cases.length }} 条，已勾选 <b class="mono">{{ selectedCount }}</b> 条
        </span>
      </div>

      <el-table
        v-loading="generating"
        :data="cases"
        row-key="_key"
        max-height="360"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="46" :selectable="(row) => !row._saved" />
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="detail">
              <div v-if="row.body_content" class="detail-row">
                <span class="detail-label">请求体</span>
                <pre class="mono detail-pre">{{ row.body_content }}</pre>
              </div>
              <div class="detail-row">
                <span class="detail-label">断言</span>
                <ul class="mono detail-list">
                  <li v-for="(a, i) in row.assertions_json" :key="i">
                    {{ a.assertion_type }} {{ a.operator }} {{ a.expected_value }}
                    <span v-if="a.target"> · {{ a.target }}</span>
                  </li>
                  <li v-if="!row.assertions_json?.length" class="detail-empty">无断言</li>
                </ul>
              </div>
              <div v-if="row.extract_json?.length" class="detail-row">
                <span class="detail-label">提取</span>
                <ul class="mono detail-list">
                  <li v-for="(e, i) in row.extract_json" :key="i">{{ e.name }} = {{ e.expression }}</li>
                </ul>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="用例名称" min-width="220">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row._saved" size="small" type="success" effect="plain">已保存</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="方法" width="86">
          <template #default="{ row }"><span class="mono">{{ row.method }}</span></template>
        </el-table-column>
        <el-table-column prop="url" label="URL" min-width="200" show-overflow-tooltip>
          <template #default="{ row }"><span class="mono">{{ row.url || '—' }}</span></template>
        </el-table-column>
        <el-table-column label="断言" width="76" align="center">
          <template #default="{ row }"><span class="mono">{{ assertionCount(row) }}</span></template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="86" />
      </el-table>
    </div>

    <p v-else-if="!generating" class="gen-empty">
      粘贴接口文档后点「AI 生成」，结果在这里预览，勾选后才能存入用例库
    </p>

    <template #footer>
      <el-button
        type="primary"
        :loading="saving"
        :disabled="!selectedCount"
        @click="saveSelected"
      >
        保存选中用例
      </el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.gen-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.gen-label {
  font-size: 13px;
  color: var(--text-2);
}

.gen-result {
  margin-top: 14px;
}

.gen-result__head {
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-2);
}

.gen-empty {
  margin: 16px 0 0;
  font-size: 13px;
  color: var(--text-3);
}

.detail {
  padding: 4px 8px 4px 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-row {
  display: flex;
  gap: 12px;
}

.detail-label {
  flex-shrink: 0;
  width: 56px;
  font-size: 12px;
  color: var(--text-3);
  padding-top: 2px;
}

.detail-pre {
  margin: 0;
  font-size: 12px;
  color: var(--text-2);
  white-space: pre-wrap;
  word-break: break-all;
}

.detail-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: var(--text-2);
}

.detail-empty {
  list-style: none;
  margin-left: -18px;
  color: var(--text-3);
}
</style>
