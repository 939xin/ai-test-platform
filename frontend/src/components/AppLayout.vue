<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Calendar, Connection, DataAnalysis, Document, Folder, MagicStick,
  Monitor, Setting, Tools, VideoPlay, Warning,
} from '@element-plus/icons-vue'

import { fetchHealth } from '@/api/health'

const route = useRoute()

// 侧栏导航 —— 与 router/index.js 的 name 一一对应
const navItems = [
  { name: 'projects', title: '项目管理', icon: Folder },
  { name: 'api-cases', title: '接口测试', icon: Document },
  { name: 'web-cases', title: 'UI 测试', icon: Monitor },
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
const parentTitle = computed(() => route.meta?.parent || '')

// 编辑页（/cases/api/new 等）不是列表页的子路由，靠 router-link-active 判不出高亮，
// 所以按路径前缀自己算，避免侧栏在编辑页整片熄灭。
const activeNav = computed(() => {
  if (route.path.startsWith('/cases/api')) return 'api-cases'
  if (route.path.startsWith('/cases/web')) return 'web-cases'
  return route.name
})

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
        <span class="brand-mark">鑫</span>
        <span class="brand-text">鑫测试平台</span>
      </div>

      <nav class="nav">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="{ name: item.name }"
          class="nav-item"
          :class="{ 'nav-active': item.name === activeNav }"
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
        <el-breadcrumb separator="/" class="crumb">
          <el-breadcrumb-item :to="{ name: 'projects' }">鑫测试平台</el-breadcrumb-item>
          <el-breadcrumb-item v-if="parentTitle">{{ parentTitle }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
        </el-breadcrumb>
        <div class="topbar-right">
          <el-avatar :size="28" class="avatar">鑫</el-avatar>
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

/* ---------- 侧栏：品牌深青蓝，整页的颜色锚点 ---------- */
.sider {
  width: var(--sider-width);
  flex-shrink: 0;
  background: linear-gradient(180deg, var(--sider-bg-top), var(--sider-bg));
  display: flex;
  flex-direction: column;
}

.brand {
  height: var(--header-height);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 18px;
  border-bottom: 1px solid var(--sider-divider);
}

.brand-mark {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
}

.brand-text {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
}

.nav {
  flex: 1;
  padding: 12px 12px;
  overflow-y: auto;
}

/* 深底上的滚动条用全局那根浅灰会很突兀 */
.nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.16);
}

.nav::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.28);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  margin-bottom: 3px;
  border-radius: 8px;
  color: var(--sider-text);
  font-size: 13.5px;
  text-decoration: none;
  transition: background 0.14s ease, color 0.14s ease;
}

.nav-item:hover {
  background: var(--sider-hover);
  color: #fff;
}

/* 选中项：品牌青底 + 白字，在深侧栏上是「亮起来」而不是「压下去」 */
.nav-item.router-link-active,
.nav-item.nav-active {
  background: var(--sider-active-bg);
  color: #fff;
  font-weight: 600;
}

.sider-foot {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--sider-divider);
}

.conn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 9px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--sider-text);
  font-family: var(--font-ui);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.14s ease;
}

.conn:hover {
  background: var(--sider-hover);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--signal-skip);
}

/* 深底上信号色要提亮一档，否则 #2e9e6b 这种深绿几乎看不见 */
.conn--ok .dot { background: #4fc48d; }
.conn--warn .dot { background: #e8ab4d; }
.conn--down .dot { background: #e87373; }
.conn--ok { color: #7fd0a6; }

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

.crumb :deep(.el-breadcrumb__inner) {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-2);
}

.crumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  font-weight: 600;
  color: var(--text-1);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}

.avatar {
  background: var(--brand-700);
  font-size: 13px;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px 32px;
}
</style>
