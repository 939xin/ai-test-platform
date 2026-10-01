<script setup>
import { computed } from 'vue'

const props = defineProps({
  // pass / fail / error / skip / running / pending
  status: { type: String, required: true },
})

const STATUS_MAP = {
  pass: { label: '通过', cls: 'is-pass' },
  fail: { label: '失败', cls: 'is-fail' },
  error: { label: '错误', cls: 'is-error' },
  skip: { label: '跳过', cls: 'is-skip' },
  pending: { label: '排队中', cls: 'is-skip' },
  running: { label: '运行中', cls: 'is-running' },
}

const info = computed(() => STATUS_MAP[props.status] || { label: props.status, cls: 'is-skip' })
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

.is-pass {
  color: var(--signal-pass);
  background: var(--signal-pass-bg);
  border-color: #bfe3d1;
}

.is-fail {
  color: var(--signal-fail);
  background: var(--signal-fail-bg);
  border-color: #f0c2c2;
}

.is-error {
  color: var(--signal-warn);
  background: var(--signal-warn-bg);
  border-color: #eed9b0;
}

.is-skip {
  color: var(--signal-skip);
  background: var(--signal-skip-bg);
  border-color: #d5dde1;
}

.is-running {
  color: var(--brand-700);
  background: var(--brand-100);
  border-color: #b3d6dd;
}
</style>
