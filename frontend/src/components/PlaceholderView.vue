<script setup>
import PageHeader from '@/components/PageHeader.vue'

defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  todo: { type: String, default: '待实现' },
})
</script>

<template>
  <div>
    <PageHeader :title="title" :description="description">
      <slot />
    </PageHeader>
    <el-empty :description="todo" />
  </div>
</template>
