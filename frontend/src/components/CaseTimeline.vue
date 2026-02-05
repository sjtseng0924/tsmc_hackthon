<script setup>
defineProps({
  steps: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="section">
    <div class="section-title">Step-by-step reasoning</div>
    <ol>
      <li v-for="step in steps" :key="step">{{ step }}</li>
    </ol>
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

ol {
  margin: 0;
  padding-left: 18px;
}
li {
  margin-bottom: 6px;
}
</style>
