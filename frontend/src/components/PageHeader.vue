<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="page-header">
    <div class="page-header__text">
      <h2 class="page-header__title">{{ title }}</h2>
      <p v-if="description" class="page-header__desc">{{ description }}</p>
    </div>
    <div class="page-header__actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header__title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.2px;
  color: var(--text-1);
}

.page-header__desc {
  margin: 5px 0 0;
  font-size: 13px;
  color: var(--text-3);
}

.page-header__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
</style>
