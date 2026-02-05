<script setup>
defineProps({
  summary: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <section class="section">
    <div class="section-title">TL;DR</div>
    <p>{{ summary }}</p>
  </section>
</template>

<style scoped>
.section {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}
</style>
