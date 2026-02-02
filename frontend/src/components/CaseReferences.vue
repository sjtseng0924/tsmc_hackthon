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