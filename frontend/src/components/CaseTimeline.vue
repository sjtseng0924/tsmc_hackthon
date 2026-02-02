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
ol {
  margin: 0;
  padding-left: 18px;
}
li {
  margin-bottom: 6px;
}
</style>