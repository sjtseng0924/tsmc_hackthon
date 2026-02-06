<script setup>
import { onMounted, ref } from 'vue'
import { getCases } from '../api/cases'
import KnowledgeGraph from '../components/KnowledgeGraph.vue'

const cases = ref([])
const loading = ref(true)
const error = ref('')

const loadCases = async () => {
  loading.value = true
  error.value = ''
  try {
    cases.value = await getCases()
  } catch (err) {
    error.value = err?.message || 'Failed to load data.'
  } finally {
    loading.value = false
  }
}

onMounted(loadCases)
</script>

<template>
  <div class="kg-page">
    <div v-if="loading" class="loading">Loading graph data...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    
    <div v-else class="graph-wrapper full-height">
      <KnowledgeGraph :cases="cases" />
    </div>
  </div>
</template>

<style scoped>
.kg-page {
  display: flex;
  flex-direction: column;
  /* Use 100vh minus header (approx 64px or 80px), but to be safe use flex-grow if parent allows, 
     or just stick to calc. Assuming header is fixed or we want to scroll header away? 
     User said "cannot scroll" and "full screen". 
     Ideally we want it to take all available space. */
  height: calc(100vh - 64px); /* Adjusted assuming standard header */
  overflow: hidden; /* Prevent scrolling */
  padding: 0;
  margin: 0;
  position: fixed; /* Force it to stay */
  width: 100%;
  top: 64px; /* Below header */
  left: 0;
}

.graph-wrapper {
  background: #ffffff;
  border: none; /* Remove border for cleaner full screen look */
  border-radius: 0; /* Remove radius */
  flex: 1; 
  display: flex;
  flex-direction: column;
  box-shadow: none;
  overflow: hidden; 
}

/* Ensure graph component fills wrapper */
:deep(.graph-container) {
  height: 100% !important;
  width: 100% !important;
  border-radius: 0 !important;
}

.loading, .error {
  padding: 40px;
  text-align: center;
  color: #64748b;
}
</style>
