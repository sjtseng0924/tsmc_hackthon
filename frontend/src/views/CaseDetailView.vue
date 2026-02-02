<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { getCaseById } from '../api/cases'
import CaseSummary from '../components/CaseSummary.vue'
import CaseTimeline from '../components/CaseTimeline.vue'
import CaseRootCause from '../components/CaseRootCause.vue'
import CaseSolution from '../components/CaseSolution.vue'
import CaseReferences from '../components/CaseReferences.vue'

const route = useRoute()
const caseItem = computed(() => getCaseById(route.params.id))
</script>

<template>
  <RouterLink to="/cases" class="back-link">← Back to list</RouterLink>

  <section v-if="caseItem" class="section">
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
.subtitle {
  color: #64748b;
  font-size: 13px;
  margin-bottom: 8px;
}
</style>