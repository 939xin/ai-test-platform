<script setup>
import { computed } from 'vue'

/**
 * 延迟分布直方图（纯 CSS，不引入图表库）。
 *
 * 后端上报的是固定分桶的 counts，桶数约 40 个；这里只渲染有数据的桶，
 * 否则界面会被大量空桶撑满。横向条比竖向柱更好读区间标签。
 */
const props = defineProps({
  bounds: { type: Array, default: () => [] },
  counts: { type: Array, default: () => [] },
})

const bars = computed(() => {
  const list = []
  props.counts.forEach((raw, index) => {
    const count = Number(raw) || 0
    if (!count) return
    const lower = index === 0 ? 0 : props.bounds[index - 1]
    const upper = index < props.bounds.length ? props.bounds[index] : null
    list.push({
      key: index,
      label: upper == null ? `>${lower}` : `${lower}–${upper}`,
      count,
    })
  })
  return list
})

const maxCount = computed(() => Math.max(1, ...bars.value.map((bar) => bar.count)))
const total = computed(() => bars.value.reduce((sum, bar) => sum + bar.count, 0))
</script>

<template>
  <div class="histogram">
    <div v-if="!bars.length" class="empty">暂无延迟数据</div>
    <template v-else>
      <div v-for="bar in bars" :key="bar.key" class="bar-row" :title="`${bar.label} ms：${bar.count} 次`">
        <span class="bar-label mono">{{ bar.label }}</span>
        <span class="bar-track">
          <span class="bar-fill" :style="{ width: `${(bar.count / maxCount) * 100}%` }"></span>
        </span>
        <span class="bar-count mono">{{ bar.count }}</span>
        <span class="bar-pct mono">{{ total ? ((bar.count / total) * 100).toFixed(1) : 0 }}%</span>
      </div>
      <p class="foot mono">共 {{ total }} 个请求 · 区间单位 ms</p>
    </template>
  </div>
</template>

<style scoped>
.histogram {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.empty {
  padding: 24px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
}

.bar-row {
  display: grid;
  grid-template-columns: 92px 1fr 54px 50px;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.bar-label {
  color: var(--text-2);
  text-align: right;
}

.bar-track {
  height: 10px;
  background: var(--bg-sunken);
  border-radius: 5px;
  overflow: hidden;
}

.bar-fill {
  display: block;
  height: 100%;
  min-width: 2px;
  background: var(--brand-500);
  border-radius: 5px;
}

.bar-count {
  color: var(--text-1);
  text-align: right;
}

.bar-pct {
  color: var(--text-3);
  text-align: right;
}

.foot {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: var(--text-3);
  text-align: right;
}
</style>
