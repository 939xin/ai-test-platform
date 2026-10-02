<script setup>
/**
 * UI 用例的专属表单区：浏览器可用性提示 + 步骤编排器。
 *
 * 薄封装的一层，是为了让编辑页对「接口 / UI」两种类型保持同样的用法：
 * 都往表单里塞一个组件，都在提交前调它的 validate()。
 */
import { ref } from 'vue'

import WebStepEditor from '@/components/WebStepEditor.vue'

defineProps({
  form: { type: Object, required: true },
  actions: { type: Array, default: () => [] },
  actionGroups: { type: Array, default: () => [] },
  locators: { type: Array, default: () => [] },
  webInfo: { type: Object, default: null },
})

const stepEditorRef = ref(null)

/** 返回第一条问题说明；全部合法时返回空串 */
function validate() {
  return stepEditorRef.value?.validate() || ''
}

defineExpose({ validate })
</script>

<template>
  <div class="web-steps">
    <el-alert
      v-if="webInfo && !webInfo.available"
      type="warning"
      show-icon
      :closable="false"
      class="web-alert"
      :title="`本机检测不到可用的 Chrome / Edge，用例可以编辑，但执行会失败：${webInfo.error}`"
    />
    <WebStepEditor
      ref="stepEditorRef"
      v-model="form.steps"
      :actions="actions"
      :action-groups="actionGroups"
      :locators="locators"
    />
  </div>
</template>

<style scoped>
.web-alert {
  margin-bottom: 12px;
}
</style>
