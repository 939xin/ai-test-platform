<script setup>
/**
 * 用例列表的批量操作条（接口 / UI 两个列表共用）。
 *
 * 只负责展示与派发 action，真正的请求、二次确认、刷新留在页面里 ——
 * 这样两条线路的清理逻辑（删完最后一条要退页）不用挤进组件。
 *
 * ⚠️ 文案必须写明「当前页」：表格的多选只在当前页生效，翻页后勾选就没了。
 * 不写清楚，用户会以为跨页勾了 40 条，实际只改了 20 条。
 */
import { computed } from 'vue'
import { CircleCheck, CircleClose, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  selectedIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['action'])

const count = computed(() => props.selectedIds.length)
</script>

<template>
  <div v-if="count" class="batch-bar">
    <span class="batch-count">
      已选 <b class="mono">{{ count }}</b> 条（当前页）
    </span>
    <el-button
      size="small"
      type="success"
      :icon="CircleCheck"
      :loading="loading"
      @click="emit('action', 'enable')"
    >
      批量启用
    </el-button>
    <el-button
      size="small"
      type="warning"
      :icon="CircleClose"
      :loading="loading"
      @click="emit('action', 'disable')"
    >
      批量停用
    </el-button>
    <el-button
      size="small"
      type="danger"
      :icon="Delete"
      :loading="loading"
      @click="emit('action', 'delete')"
    >
      批量删除
    </el-button>
  </div>
</template>

<style scoped>
.batch-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: var(--bg-sunken);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.batch-count {
  margin-right: 4px;
  font-size: 13px;
  color: var(--text-2);
}

.batch-count b {
  color: var(--text-1);
}
</style>
