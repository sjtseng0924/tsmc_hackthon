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
.solution-block {
  margin-bottom: 12px;
}
p {
  margin: 6px 0 0;
}
</style>