<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Calendar, Connection, DataAnalysis, Document, Folder, MagicStick,
  Setting, Tools, VideoPlay, Warning,
} from '@element-plus/icons-vue'

import { fetchHealth } from '@/api/health'

const route = useRoute()

// 侧栏导航 —— 与 router/index.js 的 name 一一对应
const navItems = [
  { name: 'projects', title: '项目管理', icon: Folder },
  { name: 'cases', title: '用例管理', icon: Document },
  { name: 'scenarios', title: '场景测试', icon: Connection },
  { name: 'plans', title: '测试计划', icon: Calendar },
  { name: 'executions', title: '执行中心', icon: VideoPlay },
  { name: 'reports', title: '测试报告', icon: DataAnalysis },
  { name: 'defects', title: '缺陷管理', icon: Warning },
  { name: 'environments', title: '环境变量', icon: Setting },
  { name: 'ai', title: 'AI 助手', icon: MagicStick },
  { name: 'settings', title: '设置', icon: Tools },
]

const pageTitle = computed(() => route.meta?.title || '')

// 后端连通状态：工程工具就该随时显示系统状态
const health = ref({ state: 'checking', text: '检查中…' })

async function checkHealth() {
  try {
    const data = await fetchHealth()
    if (data.database === 'connected') {
      health.value = { state: 'ok', text: '后端已连通' }
    } else {
      health.value = { state: 'warn', text: '数据库未连接' }
    }
  } catch {
    health.value = { state: 'down', text: '后端未连通' }
  }
}

onMounted(checkHealth)
</script>

<template>
  <div class="app-shell">
    <aside class="sider">
      <div class="brand">
        <span class="brand-mark">AT</span>
        <span class="brand-text">AI 测试平台</span>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="{ name: item.name }"
          class="nav-item"
        >
          <el-icon :size="15"><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </router-link>
      </nav>

      <div class="sider-foot">
        <button class="conn" :class="`conn--${health.state}`" @click="checkHealth">
          <span class="dot" />
          <span>{{ health.text }}</span>
        </button>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="topbar-title">{{ pageTitle }}</div>
        <div class="topbar-right">
          <span class="topbar-hint">AI 辅助软件测试平台</span>
          <el-avatar :size="28" class="avatar">A</el-avatar>
        </div>
      </header>

      <main class="content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ---------- 侧栏：深色控制台 ---------- */
.sider {
  width: var(--sider-width);
  flex-shrink: 0;
  background: var(--bg-sider);
  display: flex;
  flex-direction: column;
}

.brand {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.07);
}

.brand-mark {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background: var(--brand-700);
  color: #fff;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.brand-text {
  color: #e8eef0;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.nav {
  flex: 1;
  padding: 10px 8px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  margin-bottom: 2px;
  border-radius: var(--radius);
  color: #9fb0b7;
  font-size: 13.5px;
  text-decoration: none;
  /* 左侧竖条是选中指示，比整块高亮更克制 */
  border-left: 2px solid transparent;
  transition: background 0.14s ease, color 0.14s ease;
}

.nav-item:hover {
  background: var(--bg-sider-hover);
  color: #e8eef0;
}

.nav-item.router-link-active {
  background: var(--bg-sider-hover);
  color: #fff;
  border-left-color: var(--brand-500);
}

.sider-foot {
  padding: 10px 12px 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.conn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 8px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: #8a9ba3;
  font-family: var(--font-ui);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.14s ease;
}

.conn:hover {
  background: var(--bg-sider-hover);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--signal-skip);
}

.conn--ok .dot { background: var(--signal-pass); }
.conn--warn .dot { background: var(--signal-warn); }
.conn--down .dot { background: var(--signal-fail); }
.conn--ok { color: #7fc4a3; }

/* ---------- 主区 ---------- */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: var(--header-height);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
}

.topbar-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-1);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.topbar-hint {
  font-size: 12px;
  color: var(--text-3);
}

.avatar {
  background: var(--brand-700);
  font-family: var(--font-mono);
  font-size: 13px;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
</style>
