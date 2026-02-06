<script setup>
import { onMounted, ref, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { getCaseByFilename } from '../api/cases'

const route = useRoute()
const caseItem = ref(null)
const loading = ref(true)
const error = ref('')

const loadCase = async (id) => {
  loading.value = true
  error.value = ''
  caseItem.value = null
  try {
    caseItem.value = await getCaseByFilename(id)
  } catch (err) {
    error.value = err?.message || 'Failed to load case.'
  } finally {
    loading.value = false
  }
}

onMounted(() => loadCase(route.params.id))
watch(() => route.params.id, (newId) => loadCase(newId))

// Helpers
const formatDate = (ds) => {
  if (!ds) return '-'
  return new Date(ds).toLocaleString('zh-TW', { hour12: false })
}

const severityClass = computed(() => caseItem.value?.severity?.toLowerCase())
</script>

<template>
  <div class="case-detail-page">
    <RouterLink to="/cases" class="back-link">
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
        <path fill-rule="evenodd" d="M15 8a.5.5 0 0 0-.5-.5H2.707l3.147-3.146a.5.5 0 1 0-.708-.708l-4 4a.5.5 0 0 0 0 .708l4 4a.5.5 0 0 0 .708-.708L2.707 8.5H14.5A.5.5 0 0 0 15 8z"/>
      </svg>
      Back to list
    </RouterLink>

    <div v-if="loading" class="loading-state">Loading report...</div>
    <div v-else-if="error" class="error-state">{{ error }}</div>

    <div v-else-if="caseItem" class="report-container">
      
      <!-- Header Section -->
      <header class="report-header">
        <div class="header-top">
          <div class="meta-badges">
            <span class="badge severity" :class="severityClass">
              {{ caseItem.severity.toUpperCase() }}
            </span>
            <span class="badge id">{{ caseItem.filename }}</span>
          </div>
          <div class="report-date">Report Date: {{ formatDate(caseItem.reportDate) }}</div>
        </div>
        
        <h1 class="report-title">{{ caseItem.title }}</h1>
        
        <div class="time-grid">
          <div class="time-item">
            <span class="label">Occurred At</span>
            <span class="value">{{ formatDate(caseItem.occurredAt) }}</span>
          </div>
          <div class="time-item">
            <span class="label">Resolved At</span>
            <span class="value">{{ formatDate(caseItem.resolvedAt) }}</span>
          </div>
          <div class="time-item">
            <span class="label">Duration</span>
            <span class="value" v-if="caseItem.occurredAt && caseItem.resolvedAt">
              {{ ((new Date(caseItem.resolvedAt) - new Date(caseItem.occurredAt)) / 3600000).toFixed(1) }} Hours
            </span>
            <span class="value" v-else>-</span>
          </div>
        </div>
      </header>

      <!-- Section 1: Problem & Impact -->
      <section class="report-section">
        <h2 class="section-heading">Reported Problem</h2>
        <div class="content-block primary">
          {{ caseItem.reportProblem }}
        </div>

        <h3 class="sub-heading">Impact Analysis</h3>
        <div class="impact-grid">
          <div class="impact-card service">
            <div class="icon">S</div>
            <div class="title">Service Impact</div>
            <div class="desc">{{ caseItem.impactService || 'None' }}</div>
          </div>
          <div class="impact-card user">
            <div class="icon">U</div>
            <div class="title">User Impact</div>
            <div class="desc">{{ caseItem.impactUser || 'None' }}</div>
          </div>
          <div class="impact-card data">
            <div class="icon">D</div>
            <div class="title">Data Impact</div>
            <div class="desc">{{ caseItem.impactData || 'None' }}</div>
          </div>
        </div>
      </section>

      <!-- Section 2: Deep Dive -->
      <section class="report-section">
        <h2 class="section-heading">Incident Deep Dive</h2>
        
        <div class="deep-dive-grid">
          <div class="dd-item">
            <h3>Root Cause</h3>
            <div class="content-text">{{ caseItem.rootCause }}</div>
          </div>
          
          <div class="dd-item full-width" v-if="caseItem.eventDetails">
            <h3>Event Details</h3>
            <div class="content-text">{{ caseItem.eventDetails }}</div>
          </div>

          <div class="dd-item full-width bg-highlight" v-if="caseItem.inferenceProcess">
             <h3>🤖 AI Inference Process</h3>
             <div class="content-text">{{ caseItem.inferenceProcess }}</div>
          </div>
        </div>
      </section>

      <!-- Section 3: Timeline -->
      <section class="report-section">
        <h2 class="section-heading">Timeline</h2>
        <div class="timeline-container">
          <div v-for="(event, index) in caseItem.timeline" :key="index" class="timeline-event">
            <div class="marker"></div>
            <div class="event-content">{{ event }}</div>
          </div>
        </div>
      </section>

      <!-- Section 4: Solution -->
      <section class="report-section solution-bg">
        <h2 class="section-heading">Solution</h2>
        <div class="content-text large-text">
          {{ caseItem.solution }}
        </div>
      </section>

      <!-- Section 5: Prevention -->
      <section class="report-section">
        <h2 class="section-heading">Prevention & Risks</h2>
        
        <h3 class="sub-heading" v-if="caseItem.preventiveMeasures?.length">Preventive Measures</h3>
        <div class="measures-grid" v-if="caseItem.preventiveMeasures?.length">
          <div v-for="(pm, idx) in caseItem.preventiveMeasures" :key="idx" class="measure-card">
            <div class="pm-header">
              <span class="pm-title">{{ pm.title }}</span>
              <span class="pm-owner">{{ pm.owner }}</span>
            </div>
            <div class="pm-content">{{ pm.content }}</div>
            <a v-if="pm.link" :href="pm.link" target="_blank" class="pm-link">Reference Link →</a>
          </div>
        </div>

        <h3 class="sub-heading" v-if="caseItem.hiddenRisks?.length" style="margin-top:24px; color:#c2410c;">⚠️ Hidden Risks & Optimizations</h3>
        <div class="risks-list" v-if="caseItem.hiddenRisks?.length">
          <div v-for="(risk, idx) in caseItem.hiddenRisks" :key="idx" class="risk-item">
            <div class="risk-title">{{ risk.title }}</div>
            <div class="risk-content">{{ risk.content }}</div>
            <a v-if="risk.link" :href="risk.link" target="_blank" class="risk-link">Risk Reference</a>
          </div>
        </div>
      </section>

    </div>
  </div>
</template>

<style scoped>
/* Page Layout */
.case-detail-page {
  max-width: 900px;
  margin: 0 auto;
  padding-bottom: 60px;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-weight: 500;
  text-decoration: none;
  margin-bottom: 24px;
  transition: color 0.2s;
}
.back-link:hover { color: #3b82f6; }

.loading-state, .error-state {
  text-align: center;
  padding: 40px;
  font-size: 16px;
  color: #64748b;
}

/* Report Container */
.report-container {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

/* Header */
.report-header {
  padding: 40px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.meta-badges {
  display: flex;
  gap: 12px;
}

.badge {
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.badge.id {
  background: #e2e8f0;
  color: #475569;
}

.badge.severity.critical { background: #fee2e2; color: #991b1b; }
.badge.severity.high { background: #ffedd5; color: #9a3412; }
.badge.severity.medium { background: #fef9c3; color: #854d0e; }
.badge.severity.low { background: #dcfce7; color: #166534; }

.report-date {
  color: #64748b;
  font-size: 14px;
}

.report-title {
  font-size: 28px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
  margin-bottom: 24px;
}

.time-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.time-item {
  display: flex;
  flex-direction: column;
}

.time-item .label {
  font-size: 12px;
  text-transform: uppercase;
  color: #64748b;
  font-weight: 600;
  margin-bottom: 4px;
}

.time-item .value {
  font-size: 15px;
  color: #334155;
  font-weight: 500;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

/* Generic Section Styles */
.report-section {
  padding: 40px;
  border-bottom: 1px solid #e2e8f0;
}
.report-section:last-child { border-bottom: none; }

.section-heading {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
}
.section-heading::before {
  content: '';
  display: block;
  width: 6px;
  height: 24px;
  background: #3b82f6;
  margin-right: 12px;
  border-radius: 3px;
}

.sub-heading {
  font-size: 16px;
  font-weight: 600;
  color: #334155;
  margin: 32px 0 16px 0;
}

.content-block.primary {
  font-size: 16px;
  line-height: 1.7;
  color: #334155;
  background: #f1f5f9;
  padding: 24px;
  border-radius: 12px;
}

/* Impact Grid */
.impact-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.impact-card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  background: #fff;
}
.impact-card .icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-bottom: 12px;
}
.impact-card.service .icon { background: #dbeafe; color: #1e40af; }
.impact-card.user .icon { background: #fae8ff; color: #86198f; }
.impact-card.data .icon { background: #fee2e2; color: #991b1b; }

.impact-card .title {
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.impact-card .desc {
  font-size: 14px;
  color: #475569;
  line-height: 1.5;
}

/* Deep Dive */
.deep-dive-grid {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.dd-item h3 {
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 8px;
}

.content-text {
  font-size: 15px;
  line-height: 1.7;
  color: #334155;
  white-space: pre-wrap;
}

.bg-highlight {
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  padding: 20px;
  border-radius: 12px;
}

/* Timeline */
.timeline-container {
  border-left: 2px solid #e2e8f0;
  margin-left: 10px;
  padding-left: 24px;
}

.timeline-event {
  position: relative;
  margin-bottom: 20px;
}

.timeline-event:last-child { margin-bottom: 0; }

.timeline-event .marker {
  position: absolute;
  left: -31px; /* 24px padding + 2px border + 5px center */
  top: 6px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #3b82f6;
  border: 2px solid #fff;
  box-shadow: 0 0 0 2px #dbeafe;
}

.timeline-event .event-content {
  font-size: 15px;
  color: #334155;
  line-height: 1.6;
}

/* Solution */
.solution-bg {
  background: #f8fafc;
}
.large-text {
  font-size: 16px;
}

/* Measures */
.measures-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.measure-card {
  background: #fff;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 20px;
  transition: transform 0.2s;
}
.measure-card:hover { transform: translateY(-2px); border-color: #3b82f6; }

.pm-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  align-items: center;
}
.pm-title {
  font-weight: 600;
  color: #0f172a;
}
.pm-owner {
  font-size: 12px;
  background: #e2e8f0;
  padding: 2px 8px;
  border-radius: 4px;
  color: #475569;
}
.pm-content {
  font-size: 14px;
  color: #475569;
  margin-bottom: 16px;
}
.pm-link {
  font-size: 13px;
  color: #3b82f6;
  text-decoration: none;
  font-weight: 500;
}
.pm-link:hover { text-decoration: underline; }

/* Risks */
.risks-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-item {
  background: #fff7ed;
  border-left: 4px solid #f97316;
  padding: 16px;
  border-radius: 0 8px 8px 0;
}
.risk-title {
  font-weight: 700;
  color: #9a3412;
  margin-bottom: 4px;
}
.risk-content {
  font-size: 14px;
  color: #9a3412;
}
.risk-link {
  display: inline-block;
  margin-top: 8px;
  font-size: 13px;
  color: #ea580c;
  text-decoration: underline;
}

@media (max-width: 768px) {
  .impact-grid, .time-grid {
    grid-template-columns: 1fr;
  }
}
</style>
