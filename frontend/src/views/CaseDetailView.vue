<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getCaseById } from '../api/cases'
import CaseSummary from '../components/CaseSummary.vue'
import CaseTimeline from '../components/CaseTimeline.vue'
import CaseRootCause from '../components/CaseRootCause.vue'
import CaseSolution from '../components/CaseSolution.vue'
import CaseReferences from '../components/CaseReferences.vue'

const route = useRoute()
const caseItem = ref(null)
const loading = ref(true)
const error = ref('')

const loadCase = async (id) => {
  loading.value = true
  error.value = ''
  caseItem.value = null
  try {
    caseItem.value = await getCaseById(id)
  } catch (err) {
    error.value = err?.message || 'Failed to load case.'
  } finally {
    loading.value = false
  }
}

onMounted(() => loadCase(route.params.id))
watch(
  () => route.params.id,
  (newId) => loadCase(newId),
)
</script>

<template>
  <RouterLink to="/cases" class="back-link">← Back to list</RouterLink>

  <section v-if="loading" class="section">
    <div class="section-title">Loading...</div>
    <p>Fetching case details.</p>
  </section>

  <section v-else-if="error" class="section">
    <div class="section-title">Failed to load</div>
    <p>{{ error }}</p>
  </section>

  <section v-else-if="caseItem" class="section">
    <div class="section-title">{{ caseItem.title }}</div>
    <div class="subtitle">{{ caseItem.id }}</div>
    <div class="severity" :class="caseItem.severity">{{ caseItem.severity.toUpperCase() }}</div>
    <div style="margin-top: 12px;">
      <span v-for="tag in caseItem.tags" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </section>

  <template v-if="caseItem">
    <CaseSummary :summary="caseItem.summary" />
    <CaseTimeline :steps="caseItem.timeline" />
    <CaseRootCause :root-cause="caseItem.rootCause" />
    <CaseSolution :immediate="caseItem.immediateFix" :long-term="caseItem.longTermFix" />
    <CaseReferences :references="caseItem.references" />
  </template>

  <section v-else class="section">
    <div class="section-title">Case not found</div>
    <p>Please return to the list and select a valid case.</p>
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

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
  margin-bottom: 12px;
}

.subtitle {
  color: #64748b;
  font-size: 13px;
  margin-bottom: 8px;
}
</style>
