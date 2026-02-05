<script setup>
defineProps({
  references: {
    type: Array,
    default: () => [],
  },
})
</script>

<template>
  <section class="section">
    <div class="section-title">References</div>
    <ul>
      <li v-for="item in references" :key="item.url">
        <a :href="item.url" target="_blank" rel="noreferrer">{{ item.label }}</a>
      </li>
    </ul>
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

ul {
  margin: 0;
  padding-left: 18px;
}
li {
  margin-bottom: 6px;
}
a {
  color: #2563eb;
}
</style>
