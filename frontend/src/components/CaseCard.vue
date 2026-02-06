<script setup>
import { computed } from 'vue'

const props = defineProps({
  caseItem: {
    type: Object,
    required: true,
  },
})

const severityClass = computed(() => props.caseItem.severity?.toLowerCase())

// Use reportProblem as the main summary, fallback to summary or rootCause
const snippet = computed(() => {
  const text = props.caseItem.reportProblem || props.caseItem.summary || props.caseItem.rootCause || ''
  return text.length > 120 ? text.slice(0, 120) + '...' : text
})

const displayDate = computed(() => {
  if (props.caseItem.reportDate) {
    return new Date(props.caseItem.reportDate).toLocaleDateString()
  }
  return 'Unknown Date'
})
</script>

<template>
  <RouterLink :to="`/cases/${caseItem.filename}`" class="case-card">
    <div class="card-header">
      <div class="severity" :class="severityClass">
        {{ caseItem.severity.toUpperCase() }}
      </div>
      <span class="date">{{ displayDate }}</span>
    </div>
    
    <div class="card-body">
      <div class="section-title">{{ caseItem.title }}</div>
      <div class="subtitle">{{ caseItem.filename }}</div>
      
      <div class="snippet">
        {{ snippet }}
      </div>
    </div>
    
  </RouterLink>
</template>

<style scoped>
.case-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
  text-decoration: none;
  color: inherit;
  height: 100%;
}

.case-card:hover {
  border-color: #94a3b8;
  transform: translateY(-2px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.date {
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
  line-height: 1.4;
}

.subtitle {
  color: #64748b;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.snippet {
  margin-top: 12px;
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.severity {
  font-weight: 700;
  font-size: 11px;
  letter-spacing: 0.5px;
  padding: 4px 10px;
  border-radius: 9999px;
  display: inline-flex;
  text-transform: uppercase;
}

.severity.critical {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #fecaca;
}

.severity.high {
  background: #ffedd5;
  color: #9a3412;
  border: 1px solid #fed7aa;
}

.severity.medium {
  background: #fef9c3;
  color: #854d0e;
  border: 1px solid #fde047;
}

.severity.low {
  background: #dcfce7;
  color: #166534;
  border: 1px solid #bbf7d0;
}
</style>
