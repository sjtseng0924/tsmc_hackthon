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
.case-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.case-card:hover {
  border-color: #94a3b8;
  box-shadow: 0 6px 20px rgba(15, 23, 42, 0.08);
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
}

.tag {
  display: inline-flex;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 999px;
  background: #e2e8f0;
  margin-right: 6px;
  margin-bottom: 6px;
}

.severity {
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.5px;
  padding: 4px 8px;
  border-radius: 6px;
  display: inline-flex;
  width: fit-content;
}

.severity.critical {
  background: #fee2e2;
  color: #b91c1c;
}

.severity.high {
  background: #ffedd5;
  color: #c2410c;
}

.severity.medium {
  background: #fef3c7;
  color: #b45309;
}

.severity.low {
  background: #dcfce7;
  color: #15803d;
}

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
