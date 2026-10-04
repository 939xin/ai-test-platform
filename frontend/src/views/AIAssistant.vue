<script setup>
/**
 * AI 助手页 —— 用例生成 / 失败分析两个 Tab。
 *
 * 生成的用例不直接入库：先表格预览、勾选后再保存。AI 编出来的用例直接进用例库，
 * 库很快就没法看了。保存走的是既有的用例创建接口 —— 后端 GeneratedCase 的字段
 * 就是照着 TestCaseCreate 设计的，所以这里不需要 AI 专属的保存接口。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { MagicStick, Refresh, Warning } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import { analyzeFailure, generateCases } from '@/api/ai'
import { createCase } from '@/api/case'
import { listExecutions } from '@/api/execution'
import { listProjects } from '@/api/project'

const route = useRoute()
const router = useRouter()

const projects = ref([])
const currentProjectId = ref(null)
const activeTab = ref('generate')

// ---------- Tab 1：用例生成 ----------
const docText = ref('')
const hint = ref('')
const count = ref(5)
const generating = ref(false)
const saving = ref(false)
const generatedCases = ref([])
const selectedCases = ref([])

// ---------- Tab 2：失败分析 ----------
const failedExecutions = ref([])
const loadingExecutions = ref(false)
const executionId = ref('')
const analyzing = ref(false)
const analysisVisible = ref(false)
const analysis = ref(null)

const canGenerate = computed(() => Boolean(docText.value.trim()) && currentProjectId.value != null)
const selectedCount = computed(() => selectedCases.value.length)

function formatTime(value) {
  return value ? value.replace('T', ' ').slice(0, 19) : '—'
}

function assertionCount(row) {
  return (row.assertions_json || []).length
}

function syncProjectToQuery(id) {
  if (id != null) router.replace({ query: { ...route.query, project: id } })
}

async function loadProjects() {
  projects.value = await listProjects()
  const fromQuery = Number(route.query.project)
  if (fromQuery && projects.value.some((p) => p.id === fromQuery)) {
    currentProjectId.value = fromQuery
  } else if (projects.value.length) {
    currentProjectId.value = projects.value[0].id
  }
}

/** 换项目：上一个项目的生成结果与失败列表都不再适用，一并清掉。 */
function onProjectChange(id) {
  syncProjectToQuery(id)
  generatedCases.value = []
  selectedCases.value = []
  failedExecutions.value = []
  executionId.value = ''
  if (activeTab.value === 'analyze') loadFailedExecutions()
}

// ---------- 用例生成 ----------

async function onGenerate() {
  if (!canGenerate.value) return
  generating.value = true
  try {
    const data = await generateCases({
      project_id: currentProjectId.value,
      doc_text: docText.value,
      hint: hint.value,
      count: count.value,
    })
    // _key 给表格的 row-key，_saved 标记是否已入库（已保存的行禁止再勾选）
    generatedCases.value = data.cases.map((item, index) => ({
      ...item,
      _key: `${data.task_id}-${index}`,
      _saved: false,
    }))
    selectedCases.value = []
    ElMessage.success(data.message || `生成 ${data.cases.length} 条用例`)
  } finally {
    generating.value = false
  }
}

function onSelectionChange(rows) {
  selectedCases.value = rows.filter((row) => !row._saved)
}

/** 保存时剔除前端自己加的两个字段，并补上接口用例类型。 */
function toPayload(row) {
  const { _key, _saved, ...rest } = row
  return { ...rest, type: 'api' }
}

async function saveSelected() {
  const rows = selectedCases.value.filter((row) => !row._saved)
  if (!rows.length) return

  saving.value = true
  let saved = 0
  try {
    for (const row of rows) {
      try {
        await createCase(currentProjectId.value, toPayload(row))
        row._saved = true
        saved += 1
      } catch {
        // request.js 已经弹过具体错误，这里只继续保存剩下的，不因一条失败全断
      }
    }
  } finally {
    saving.value = false
  }

  selectedCases.value = []
  if (saved) {
    ElMessage.success(`已保存 ${saved} 条到「${currentProjectName()}」的接口用例`)
  }
  if (saved < rows.length) {
    ElMessage.warning(`另有 ${rows.length - saved} 条保存失败，可重试`)
  }
}

function currentProjectName() {
  const project = projects.value.find((p) => p.id === currentProjectId.value)
  return project ? project.name : '当前项目'
}

// ---------- 失败分析 ----------

async function loadFailedExecutions() {
  if (currentProjectId.value == null) return
  loadingExecutions.value = true
  try {
    // 列表接口默认一页 20 条，显式放大：下拉里只剩 20 条时用户会找不到自己的那条
    const data = await listExecutions({
      project_id: currentProjectId.value,
      status: 'fail',
      limit: 50,
    })
    // 只留接口执行：Web 执行的 result_json 里是 steps 而不是 request/response，
    // 喂给模型只能得到「记录里没有请求响应」这种空话，不如不列出来误导人
    failedExecutions.value = data.items.filter((item) => item.case_type !== 'web')
  } finally {
    loadingExecutions.value = false
  }
}

async function onAnalyze() {
  // 下拉可以手输 ID，所以可能是字符串；非正整数直接拦在本地，不白跑一次请求
  const id = Number(executionId.value)
  if (!Number.isInteger(id) || id <= 0) {
    ElMessage.warning('请选择一条失败执行记录，或填写有效的执行 ID')
    return
  }

  analyzing.value = true
  try {
    analysis.value = await analyzeFailure({ execution_id: id })
    analysisVisible.value = true
  } finally {
    analyzing.value = false
  }
}

watch(activeTab, (tab) => {
  // 失败列表只在真正切到这个 Tab 时拉，避免进页面就多发一个请求
  if (tab === 'analyze' && !failedExecutions.value.length) loadFailedExecutions()
})

onMounted(loadProjects)
</script>

<template>
  <div class="page-stack">
    <PageHeader title="AI 助手" description="接口文档生成用例；失败执行自动分析原因与修复建议">
      <el-select
        v-model="currentProjectId"
        placeholder="选择项目"
        style="width: 190px"
        :no-data-text="'还没有项目，请先到「项目管理」创建'"
        @change="onProjectChange"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
    </PageHeader>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <!-- ---------------- 用例生成 ---------------- -->
        <el-tab-pane label="用例生成" name="generate">
          <div class="form-block">
            <el-input
              v-model="docText"
              type="textarea"
              :rows="8"
              resize="vertical"
              placeholder="粘贴接口文档（Swagger / OpenAPI 片段）或直接用自然语言描述接口，例如：&#10;接口地址：POST http://httpbin.org/post&#10;请求体：{&quot;username&quot;: &quot;字符串&quot;, &quot;password&quot;: &quot;字符串&quot;}&#10;成功：200，响应体 {&quot;code&quot;: 0, &quot;token&quot;: &quot;字符串&quot;}&#10;失败：401，响应体 {&quot;code&quot;: 1001, &quot;msg&quot;: &quot;用户名或密码错误&quot;}"
            />
            <div class="form-actions">
              <el-input
                v-model="hint"
                placeholder="附加要求（可选），如「多覆盖边界值」"
                style="width: 300px"
              />
              <span class="count-label">生成条数</span>
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
          </div>

          <div v-if="generatedCases.length" class="result-block">
            <div class="card-tools">
              <span>
                共 {{ generatedCases.length }} 条，已勾选
                <b class="mono">{{ selectedCount }}</b> 条
              </span>
              <el-button
                type="primary"
                :loading="saving"
                :disabled="!selectedCount"
                @click="saveSelected"
              >
                保存选中用例
              </el-button>
            </div>

            <el-table
              v-loading="generating"
              :data="generatedCases"
              row-key="_key"
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
                        <li v-for="(e, i) in row.extract_json" :key="i">
                          {{ e.name }} = {{ e.expression }}
                        </li>
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
              <el-table-column prop="method" label="方法" width="90">
                <template #default="{ row }"><span class="mono">{{ row.method }}</span></template>
              </el-table-column>
              <el-table-column prop="url" label="URL" min-width="220" show-overflow-tooltip>
                <template #default="{ row }"><span class="mono">{{ row.url || '—' }}</span></template>
              </el-table-column>
              <el-table-column label="断言" width="80" align="center">
                <template #default="{ row }"><span class="mono">{{ assertionCount(row) }}</span></template>
              </el-table-column>
              <el-table-column prop="priority" label="优先级" width="90" />
              <el-table-column prop="tags" label="标签" min-width="140" show-overflow-tooltip>
                <template #default="{ row }">
                  <span v-if="row.tags">{{ row.tags }}</span>
                  <span v-else class="is-zero">—</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <el-empty
            v-else-if="!generating"
            description="粘贴接口文档后点「AI 生成」，结果会在这里预览，勾选后才能存入用例库"
          />
        </el-tab-pane>

        <!-- ---------------- 失败分析 ---------------- -->
        <el-tab-pane label="失败分析" name="analyze">
          <div class="form-block">
            <div class="form-actions">
              <el-select
                v-model="executionId"
                filterable
                allow-create
                default-first-option
                placeholder="选择失败执行记录，或直接输入执行 ID"
                style="width: 420px"
                :loading="loadingExecutions"
                :no-data-text="'当前项目没有失败记录，可直接输入执行 ID'"
              >
                <el-option
                  v-for="e in failedExecutions"
                  :key="e.id"
                  :label="`#${e.id} · ${e.case_name || '已删除用例'} · ${formatTime(e.created_at)}`"
                  :value="e.id"
                />
              </el-select>
              <el-button
                type="primary"
                :icon="Warning"
                :loading="analyzing"
                :disabled="executionId === '' || executionId === null"
                @click="onAnalyze"
              >
                分析
              </el-button>
              <el-button link :icon="Refresh" @click="loadFailedExecutions">刷新列表</el-button>
            </div>
            <p class="form-hint">
              列出当前项目最近 50 条接口执行的失败记录（Web 执行不在其中）；
              要分析的记录不在列表里时，直接输入执行 ID 也可以。
            </p>
          </div>

          <el-table
            v-loading="loadingExecutions"
            :data="failedExecutions"
            @row-click="(row) => (executionId = row.id)"
          >
            <el-table-column prop="id" label="ID" width="90">
              <template #default="{ row }"><span class="mono">#{{ row.id }}</span></template>
            </el-table-column>
            <el-table-column prop="case_name" label="用例" min-width="220">
              <template #default="{ row }">
                {{ row.case_name || '已删除用例' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }"><StatusTag :status="row.status" /></template>
            </el-table-column>
            <el-table-column label="耗时" width="110">
              <template #default="{ row }">
                <span class="mono">{{ row.duration_ms }} ms</span>
              </template>
            </el-table-column>
            <el-table-column label="执行时间" width="180">
              <template #default="{ row }">
                <span class="mono">{{ formatTime(row.created_at) }}</span>
              </template>
            </el-table-column>
            <template #empty>
              <el-empty description="当前项目还没有失败记录，可先执行一条会失败的用例" />
            </template>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="analysisVisible" title="AI 失败分析" width="760px" top="6vh">
      <div v-if="analysis" class="analysis">
        <section class="analysis-section">
          <h4>可能原因</h4>
          <ol v-if="analysis.possible_causes?.length" class="analysis-list">
            <li v-for="(item, i) in analysis.possible_causes" :key="i">{{ item }}</li>
          </ol>
          <p v-else class="analysis-empty">AI 未给出可能原因</p>
        </section>

        <section class="analysis-section">
          <h4>排查步骤</h4>
          <ol v-if="analysis.troubleshooting_steps?.length" class="analysis-list">
            <li v-for="(item, i) in analysis.troubleshooting_steps" :key="i">{{ item }}</li>
          </ol>
          <p v-else class="analysis-empty">AI 未给出排查步骤</p>
        </section>

        <section class="analysis-section analysis-fix">
          <h4>修复建议</h4>
          <p>{{ analysis.fix_suggestion || 'AI 未给出修复建议' }}</p>
        </section>
      </div>
      <template #footer>
        <span class="mono analysis-task">任务 #{{ analysis?.task_id }}</span>
        <el-button @click="analysisVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.form-block {
  margin-bottom: 18px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.count-label {
  font-size: 13px;
  color: var(--text-2);
}

.form-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-3);
}

.result-block {
  margin-top: 6px;
}

.is-zero {
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

.analysis-section {
  margin-bottom: 18px;
}

.analysis-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}

.analysis-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-2);
  line-height: 1.8;
}

.analysis-empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-3);
}

.analysis-fix {
  margin-bottom: 0;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--brand-100);
}

.analysis-fix p {
  margin: 0;
  color: var(--text-2);
  line-height: 1.8;
}

.analysis-task {
  float: left;
  font-size: 12px;
  color: var(--text-3);
  line-height: 32px;
}
</style>
