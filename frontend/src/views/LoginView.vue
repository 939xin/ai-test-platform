<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Lock, User } from '@element-plus/icons-vue'

import { login } from '@/api/auth'
import { saveSession } from '@/api/session'

const route = useRoute()
const router = useRouter()

const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

/** 只接受站内路径，挡掉 //evil.com 这类开放重定向。 */
function safeRedirect() {
  const target = route.query.redirect
  if (typeof target !== 'string') return '/projects'
  return target.startsWith('/') && !target.startsWith('//') ? target : '/projects'
}

async function onSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const data = await login(form.username.trim(), form.password)
    // 会话先落盘再跳转：进到首页时 axios 拦截器才拿得到 token
    saveSession(data.access_token, data.username)
    router.replace(safeRedirect())
  } catch {
    // 密码错（401）和网络异常都已经在 request.js 里统一提示过，这里不重复弹
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <span class="brand-mark">鑫</span>
        <div class="brand-text">
          <h1 class="brand-title">鑫测试平台</h1>
          <p class="brand-sub">接口测试 + Web UI 测试</p>
        </div>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="onSubmit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" :prefix-icon="User" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            :prefix-icon="Lock"
            placeholder="请输入密码"
            show-password
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="submit"
          :loading="loading"
          native-type="submit"
        >
          登录
        </el-button>
      </el-form>

      <p class="hint">默认账号 <span class="mono">admin</span> / <span class="mono">admin123</span></p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: grid;
  place-items: center;
  min-height: 100vh;
  background: linear-gradient(160deg, var(--brand-900), var(--sider-bg) 55%, var(--brand-700));
  padding: 24px;
}

.login-card {
  width: 380px;
  max-width: 100%;
  padding: 32px 32px 24px;
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  box-shadow: var(--shadow-pop);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 26px;
}

.brand-mark {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background: var(--brand-700);
  color: #fff;
  font-size: 20px;
  font-weight: 700;
}

.brand-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-1);
}

.brand-sub {
  margin: 3px 0 0;
  font-size: 12.5px;
  color: var(--text-3);
}

.submit {
  width: 100%;
  margin-top: 4px;
}

.hint {
  margin: 20px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 12.5px;
  color: var(--text-3);
}

.hint .mono {
  color: var(--text-2);
}
</style>
