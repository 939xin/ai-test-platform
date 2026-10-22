<script setup>
import { computed } from 'vue'

/**
 * 极简 SVG 折线图（纯自绘，不引入图表库）。
 *
 * 只做一件事：把 1 秒时间线画成一条线。TPS 与延迟各用一张图，
 * 刻意不做双 Y 轴 —— 两个量纲叠在一起最容易误读。
 */
const props = defineProps({
  points: { type: Array, default: () => [] },
  xKey: { type: String, default: 'sec' },
  yKey: { type: String, default: 'tps' },
  label: { type: String, default: '' },
  unit: { type: String, default: '' },
  color: { type: String, default: '#16697a' },
})

const W = 640
const H = 180
const PAD_L = 48
const PAD_R = 14
const PAD_T = 14
const PAD_B = 26

const values = computed(() => props.points.map((point) => Number(point[props.yKey]) || 0))
const maxValue = computed(() => Math.max(1, ...values.value))
const lastValue = computed(() => (values.value.length ? values.value[values.value.length - 1] : 0))

const innerW = W - PAD_L - PAD_R
const innerH = H - PAD_T - PAD_B

const coords = computed(() => {
  const list = values.value
  const count = list.length
  if (!count) return []
  return list.map((value, index) => {
    const x = PAD_L + (count === 1 ? innerW / 2 : (index / (count - 1)) * innerW)
    const y = PAD_T + innerH - (value / maxValue.value) * innerH
    return [Number(x.toFixed(1)), Number(y.toFixed(1))]
  })
})

const polyline = computed(() => coords.value.map(([x, y]) => `${x},${y}`).join(' '))

const gridLines = computed(() =>
  [0, 0.25, 0.5, 0.75, 1].map((ratio) => ({
    y: PAD_T + innerH * (1 - ratio),
    value: Math.round(maxValue.value * ratio),
  })),
)

const xLabels = computed(() => {
  const count = coords.value.length
  if (!count) return []
  if (count === 1) return [{ x: coords.value[0][0], text: props.points[0]?.[props.xKey] ?? 1 }]
  return [
    { x: coords.value[0][0], text: props.points[0]?.[props.xKey] ?? 1, anchor: 'start' },
    { x: coords.value[count - 1][0], text: props.points[count - 1]?.[props.xKey] ?? count, anchor: 'end' },
  ]
})

const showDots = computed(() => coords.value.length <= 60)
</script>

<template>
  <div class="chart">
    <div class="chart-head">
      <span class="chart-label">{{ label }}</span>
      <span class="chart-last mono">{{ lastValue }}{{ unit }}</span>
    </div>

    <svg v-if="coords.length" :viewBox="`0 0 ${W} ${H}`" class="chart-svg" role="img" :aria-label="label">
      <line
        v-for="grid in gridLines"
        :key="grid.y"
        :x1="PAD_L"
        :x2="W - PAD_R"
        :y1="grid.y"
        :y2="grid.y"
        class="grid"
      />
      <text
        v-for="grid in gridLines"
        :key="`t-${grid.y}`"
        :x="PAD_L - 6"
        :y="grid.y + 3"
        text-anchor="end"
        class="axis-text"
      >{{ grid.value }}</text>

      <polyline :points="polyline" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" />
      <circle
        v-for="(point, index) in coords"
        v-show="showDots"
        :key="index"
        :cx="point[0]"
        :cy="point[1]"
        r="2.2"
        :fill="color"
      />

      <text
        v-for="item in xLabels"
        :key="`x-${item.x}-${item.text}`"
        :x="item.x"
        :y="H - 8"
        :text-anchor="item.anchor"
        class="axis-text"
      >{{ item.text }}s</text>
    </svg>

    <div v-else class="empty">暂无时间线数据</div>
  </div>
</template>

<style scoped>
.chart {
  min-width: 0;
}

.chart-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 6px;
}

.chart-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-2);
}

.chart-last {
  font-size: 13px;
  color: var(--text-1);
}

.chart-svg {
  display: block;
  width: 100%;
  height: auto;
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
}

.grid {
  stroke: var(--border);
  stroke-width: 1;
}

.axis-text {
  fill: var(--text-3);
  font-size: 10px;
  font-family: var(--font-mono);
}

.empty {
  padding: 30px 0;
  text-align: center;
  color: var(--text-3);
  font-size: 13px;
  background: var(--bg-sunken);
  border-radius: var(--radius-sm);
}
</style>
