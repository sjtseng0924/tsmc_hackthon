<script setup>
import { computed } from 'vue'

const props = defineProps({
  caseItem: {
    type: Object,
    required: true,
  },
})

const severityClass = computed(() => props.caseItem.severity?.toLowerCase())
</script>

<template>
  <RouterLink :to="`/cases/${caseItem.id}`" class="case-card">
    <div class="severity" :class="severityClass">
      {{ caseItem.severity.toUpperCase() }}
    </div>
    <div>
      <div class="section-title">{{ caseItem.title }}</div>
      <div class="subtitle">{{ caseItem.id }}</div>
      <div class="meta">Category: {{ caseItem.category }}</div>
    </div>
    <div>
      <strong>Root Cause:</strong>
      <span>{{ caseItem.rootCause }}</span>
    </div>
    <div>
      <span v-for="tag in caseItem.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </RouterLink>
</template>

<style scoped>
.subtitle {
  color: #64748b;
  font-size: 13px;
}

.meta {
  color: #475569;
  font-size: 13px;
  margin-top: 4px;
}
</style>