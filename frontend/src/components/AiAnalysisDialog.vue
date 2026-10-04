<script setup>
/**
 * AI 失败分析结果弹窗（纯展示）。
 *
 * 只负责把 { possible_causes, troubleshooting_steps, fix_suggestion } 排版出来，
 * 调接口的活儿留在调用方 —— 执行详情里是「点按钮 → 请求 → 打开弹窗」，
 * 弹窗本身不关心数据从哪来。
 */
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  analysis: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
</script>

<template>
  <el-dialog v-model="visible" title="AI 失败分析" width="760px" top="6vh">
    <div v-if="analysis" class="analysis">
      <section class="analysis-section">
        <h4>可能原因</h4>
        <ol v-if="analysis.possible_causes?.length" class="analysis-list">
          <li v-for="(item, i) in analysis.possible_causes" :key="i">{{ item }}</li>
        </ol>
        <p v-else class="analysis-empty">AI 未给出可能原因</p>
      </section>

      <section class="analysis-section">
        <h4>排查步骤</h4>
        <ol v-if="analysis.troubleshooting_steps?.length" class="analysis-list">
          <li v-for="(item, i) in analysis.troubleshooting_steps" :key="i">{{ item }}</li>
        </ol>
        <p v-else class="analysis-empty">AI 未给出排查步骤</p>
      </section>

      <section class="analysis-section analysis-fix">
        <h4>修复建议</h4>
        <p>{{ analysis.fix_suggestion || 'AI 未给出修复建议' }}</p>
      </section>
    </div>

    <el-empty v-else description="暂无分析结果" />

    <template #footer>
      <span class="mono analysis-task">任务 #{{ analysis?.task_id }}</span>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.analysis-section {
  margin-bottom: 18px;
}

.analysis-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}

.analysis-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-2);
  line-height: 1.8;
}

.analysis-empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-3);
}

.analysis-fix {
  margin-bottom: 0;
  padding: 12px 14px;
  border-radius: var(--radius);
  background: var(--brand-100);
}

.analysis-fix p {
  margin: 0;
  color: var(--text-2);
  line-height: 1.8;
}

.analysis-task {
  float: left;
  font-size: 12px;
  color: var(--text-3);
  line-height: 32px;
}
</style>
