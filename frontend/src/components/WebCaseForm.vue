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
    <el-card shadow="never" class="auth-card">
      <div class="card-tools">
        <span class="section-title">登录态</span>
        <span class="hint">给需要登录的站点用，省掉每条用例重复登录</span>
      </div>

      <div class="switch-row">
        <el-switch v-model="form.login_case" />
        <div class="switch-text">
          <div class="switch-label">作为登录用例</div>
          <div class="hint">
            这条用例执行并且整条通过后，会把浏览器里的 cookie 与
            localStorage / sessionStorage 存成本项目的登录态，供其他用例复用。
            没通过就不存 —— 半登录的残次品留给别人用，只会制造更难查的失败。
          </div>
        </div>
      </div>

      <div class="switch-row">
        <el-switch v-model="form.needs_login" />
        <div class="switch-text">
          <div class="switch-label">需要登录态</div>
          <div class="hint">
            执行前先注入本项目最近保存的登录态，再跑下面的步骤。
            还没有登录态时会照常执行、并在执行详情里明确提示，而不是直接报错。
          </div>
        </div>
      </div>

      <p class="auth-foot">
        登录态按站点（域名 + 端口）保存：用例第一步如果跳到别的域名，注入不会生效 ——
        这是浏览器的同源规则，不是工具的毛病。
      </p>
    </el-card>

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

.auth-card {
  margin-bottom: 12px;
}

.card-tools {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-1);
}

.switch-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 8px 0;
}

/* 开关顶部与标题那行对齐：标题是 14px 单行，约 10px 的顶偏移 */
.switch-row .el-switch {
  margin-top: 4px;
  flex: none;
}

.switch-label {
  font-size: 13.5px;
  color: var(--text-1);
  margin-bottom: 2px;
}

.hint {
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.7;
}

.auth-foot {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-3);
  line-height: 1.7;
}
</style>
