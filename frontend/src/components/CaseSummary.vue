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