<script setup>
defineProps({
  rootCause: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <section class="section">
    <div class="section-title">Root Cause</div>
    <div class="root-cause">{{ rootCause }}</div>
  </section>
</template>

<style scoped>
.root-cause {
  padding: 12px;
  border-radius: 8px;
  background: #fee2e2;
  color: #b91c1c;
  font-weight: 600;
}
</style>