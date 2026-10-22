<script setup>
import { computed } from 'vue'

// 压测运行的状态机与功能执行不同，单独一套映射；
// 视觉沿用 StatusTag 的类名与设计令牌，不另造配色。
const props = defineProps({
  // queued / running / stopping / completed / stopped / aborted / failed
  status: { type: String, required: true },
})

const STATUS_MAP = {
  queued: { label: '排队中', cls: 'is-queued' },
  running: { label: '运行中', cls: 'is-running' },
  stopping: { label: '停止中', cls: 'is-stopping' },
  completed: { label: '已完成', cls: 'is-completed' },
  stopped: { label: '已停止', cls: 'is-stopped' },
  aborted: { label: '已熔断', cls: 'is-aborted' },
  failed: { label: '失败', cls: 'is-failed' },
}

const info = computed(() => STATUS_MAP[props.status] || { label: props.status, cls: 'is-queued' })
</script>

<template>
  <span class="status-tag" :class="info.cls">{{ info.label }}</span>
</template>

<style scoped>
.status-tag {
  display: inline-block;
  padding: 1px 7px;
  border: 1px solid transparent;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.is-queued,
.is-stopped {
  color: var(--signal-skip);
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

.is-running,
.is-stopping {
  color: var(--brand-700);
  background: var(--brand-100);
  border-color: #b3d6dd;
}

.is-completed {
  color: var(--signal-pass);
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.is-aborted {
  color: var(--signal-warn);
  background: var(--signal-warn-bg);
  border-color: #eed9b0;
}

.is-failed {
  color: var(--signal-fail);
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
}
</style>
