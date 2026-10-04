<script setup>
/**
 * 设置页 —— 三块：账号安全 / 浏览器驱动 / 系统参数。
 *
 * 旧桌面版的设置页是「环境 + 全局变量 + 驱动」三个 Tab，但前两个在新平台
 * 各有自己的页面（/environments），所以这里只保留驱动，并补上账号与本机参数。
 *
 * 只读面板的数据全部来自 GET /system/info 一次请求 —— 这些都是「本机当前状态」，
 * 分开取会出现互相矛盾的组合（比如数据库刚断，一半卡片说好一半说坏）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import PageHeader from '@/components/PageHeader.vue'
import { changePassword } from '@/api/auth'
import { getSystemInfo } from '@/api/system'

const ROLE_LABELS = { admin: '管理员', tester: '测试人员' }
const BROWSER_LABELS = { chrome: 'Chrome', edge: 'Edge' }

const loading = ref(false)
const info = ref(null)

async function load() {
  loading.value = true
  try {
    info.value = await getSystemInfo()
  } finally {
    loading.value = false
  }
}

onMounted(load)

const driverRows = computed(() =>
  Object.entries(info.value?.drivers || {}).map(([name, d]) => ({
    name,
    label: BROWSER_LABELS[name] || name,
    available: d.available,
    detail: d.detail,
  })),
)

/** 数据库地址（拼给用户看的）。后端不下发密码，这里也拼不出密码来。 */
const dbUrl = computed(() => {
  const d = info.value?.database
  if (!d) return '—'
  const auth = d.user ? `${d.user}@` : ''
  const port = d.port ? `:${d.port}` : ''
  return `${d.scheme}://${auth}${d.host}${port}/${d.database}`
})

// ---------- 账号：改密码 ----------
const formRef = ref(null)
const saving = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' })

const rules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位（后端同口径）', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再输入一次新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) =>
        value === form.newPassword ? callback() : callback(new Error('两次输入的新密码不一致')),
      trigger: 'blur',
    },
  ],
}

async function submitPassword() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return // 校验没过时字段下面已经有红字了，不必再弹提示
  }
  saving.value = true
  try {
    await changePassword(form.oldPassword, form.newPassword)
    formRef.value.resetFields()
    // 刻意不登出：当前 token 还有效（后端的取舍），把正在干活的人踢下线更糟
    ElMessage.success('密码已修改，下次登录请使用新密码')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <PageHeader title="设置" description="账号安全、浏览器驱动与本机运行参数">
      <el-button :icon="Refresh" :loading="loading" @click="load">重新检测</el-button>
    </PageHeader>

    <!-- ---------- 账号 ---------- -->
    <el-card shadow="never" class="section">
      <div class="card-tools">
        <span class="section-title">账号</span>
        <span v-if="info?.user" class="mono current-user">
          {{ info.user.username }}（{{ ROLE_LABELS[info.user.role] || info.user.role }}）
        </span>
      </div>

      <!-- 104px：要装得下「确认新密码」5 个汉字加必填星号，窄了会折成两行 -->
      <el-form ref="formRef" :model="form" :rules="rules" label-width="104px"
               class="pwd-form" @submit.prevent="submitPassword">
        <el-form-item label="原密码" prop="oldPassword">
          <el-input v-model="form.oldPassword" type="password" show-password
                    autocomplete="current-password" />
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="form.newPassword" type="password" show-password
                    autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input v-model="form.confirmPassword" type="password" show-password
                    autocomplete="new-password" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="submitPassword">保存</el-button>
          <span class="hint">改完不用重新登录，当前登录态继续有效。</span>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- ---------- 浏览器驱动 ---------- -->
    <el-card shadow="never" class="section">
      <div class="card-tools">
        <span class="section-title">浏览器驱动</span>
        <span class="mono hint">
          缓存目录 {{ info?.paths?.driver_cache_dir || '—' }}
        </span>
      </div>

      <el-table v-loading="loading" :data="driverRows">
        <el-table-column prop="label" label="浏览器" width="120" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.available ? 'success' : 'danger'" effect="light" size="small">
              {{ row.available ? '可用' : '未检测到' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="360">
          <template #default="{ row }">
            <span class="mono detail" :class="{ 'is-bad': !row.available }">{{ row.detail }}</span>
          </template>
        </el-table-column>
      </el-table>

      <p class="hint foot-hint">
        只做廉价探测（浏览器装没装、驱动缓存目录能不能写），不启动浏览器也不下载驱动 ——
        否则这一页首次打开就要卡几十秒。驱动在真正执行 Web 用例时才按需下载。
      </p>
    </el-card>

    <!-- ---------- 系统参数 ---------- -->
    <el-card shadow="never" class="section">
      <div class="card-tools">
        <span class="section-title">系统参数</span>
        <span class="hint">只读，改这些要去 backend/.env</span>
      </div>

      <el-descriptions v-loading="loading" :column="1" border>
        <el-descriptions-item label="后端版本">
          <span class="mono">v{{ info?.version || '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="数据库">
          <span class="mono">{{ dbUrl }}</span>
          <span class="hint db-note">密码不下发</span>
        </el-descriptions-item>
        <el-descriptions-item label="数据库连接">
          <el-tag :type="info?.database_ok ? 'success' : 'danger'" effect="light" size="small">
            {{ info?.database_ok ? '正常' : '连不上' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="AI 配置">
          <el-tag v-if="info?.ai_configured" type="success" effect="light" size="small">已配置</el-tag>
          <template v-else>
            <el-tag type="warning" effect="light" size="small">未配置</el-tag>
            <span class="hint db-note">在 backend/.env 里填 DEEPSEEK_API_KEY 后重启后端</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="报告目录">
          <span class="mono">{{ info?.paths?.report_dir || '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="数据集目录">
          <span class="mono">{{ info?.paths?.dataset_dir || '—' }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="驱动缓存目录">
          <span class="mono">{{ info?.paths?.driver_cache_dir || '—' }}</span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<style scoped>
.section {
  margin-bottom: 16px;
}

.card-tools {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}

.current-user {
  font-size: 13px;
  color: var(--text-2);
}

.pwd-form {
  max-width: 420px;
}

.hint {
  font-size: 12px;
  color: var(--text-3);
}

/* 表单那一行里，"保存" 与右侧说明并排，说明贴着按钮往右排 */
.pwd-form .hint {
  margin-left: 12px;
}

.foot-hint {
  margin: 12px 0 0;
  line-height: 1.7;
}

.detail {
  font-size: 12.5px;
  color: var(--text-2);
  word-break: break-all;
}

.detail.is-bad {
  color: var(--signal-fail);
}

.db-note {
  margin-left: 10px;
}
</style>
