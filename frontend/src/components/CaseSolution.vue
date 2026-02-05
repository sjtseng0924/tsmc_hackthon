<script setup>
defineProps({
  immediate: {
    type: String,
    required: true,
  },
  longTerm: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <section class="section">
    <div class="section-title">Solution</div>
    <div class="solution-block">
      <strong>Immediate:</strong>
      <p>{{ immediate }}</p>
    </div>
    <div class="solution-block">
      <strong>Long-term:</strong>
      <p>{{ longTerm }}</p>
    </div>
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

.solution-block {
  margin-bottom: 12px;
}
p {
  margin: 6px 0 0;
}
</style>
