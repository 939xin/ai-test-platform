<script setup>
import { onMounted, ref } from 'vue'

import { fetchHealth } from '@/api/health'
import PageHeader from '@/components/PageHeader.vue'

const health = ref(null)
const healthError = ref(false)
const loading = ref(true)

async function loadHealth() {
  loading.value = true
  healthError.value = false
  try {
    health.value = await fetchHealth()
  } catch {
    healthError.value = true
    health.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadHealth)
</script>

<template>
  <div>
    <PageHeader
      title="项目管理"
      description="创建和管理测试项目，查看用例数、执行数与通过率"
    >
      <el-button type="primary">新建项目</el-button>
    </PageHeader>

    <!-- Day 1 的基线验证点：后端与数据库是否真的通了 -->
    <el-card shadow="never" class="status-card">
      <div class="status-card__head">
        <span class="status-card__label">平台状态</span>
        <el-button link type="primary" :loading="loading" @click="loadHealth">重新检测</el-button>
      </div>

      <div class="status-grid">
        <div class="status-item">
          <span class="status-item__key">后端服务</span>
          <span class="status-item__val mono" :class="health ? 'ok' : 'bad'">
            {{ health ? '已连通' : '未连通' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-item__key">数据库</span>
          <span
            class="status-item__val mono"
            :class="health?.database === 'connected' ? 'ok' : 'bad'"
          >
            {{ health?.database === 'connected' ? '已连接' : '未连接' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-item__key">服务标识</span>
          <span class="status-item__val mono">{{ health?.service || '—' }}</span>
        </div>
      </div>

      <p v-if="healthError" class="status-card__err mono">
        无法访问 /api/health —— 确认后端已在 127.0.0.1:8000 启动
      </p>
    </el-card>

    <el-empty description="项目列表将在 Day 2 实现：项目 CRUD + 用例数/执行数/通过率统计" />
  </div>
</template>

<style scoped>
.status-card {
  margin-bottom: 16px;
}

.status-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.status-card__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-app);
}

.status-item__key {
  font-size: 12px;
  color: var(--text-3);
}

.status-item__val {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-2);
}

.status-item__val.ok { color: var(--signal-pass); }
.status-item__val.bad { color: var(--signal-fail); }

.status-card__err {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--signal-fail);
}
</style>
