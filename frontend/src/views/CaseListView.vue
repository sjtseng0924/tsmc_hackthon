<script setup>
import { computed, onMounted, ref } from 'vue'
import { getCases, getTaxonomy } from '../api/cases'
import CaseCard from '../components/CaseCard.vue'

const searchTerm = ref('')
const selectedCategory = ref('all')
const cases = ref([])
const categories = ref([])
const loading = ref(true)
const error = ref('')

const loadCases = async () => {
  loading.value = true
  error.value = ''
  try {
    const [caseItems, taxonomy] = await Promise.all([getCases(), getTaxonomy()])
    cases.value = caseItems
    categories.value = taxonomy.categories || []
  } catch (err) {
    error.value = err?.message || 'Failed to load cases.'
  } finally {
    loading.value = false
  }
}

const filteredCases = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  return cases.value.filter((item) => {
    const matchesCategory =
      selectedCategory.value === 'all' || item.category === selectedCategory.value
    if (!matchesCategory) return false

    if (!term) return true

    const haystack = [
      item.id,
      item.title,
      item.rootCause,
      item.category,
      ...(item.tags || []),
    ]
      .join(' ')
      .toLowerCase()

    return haystack.includes(term)
  })
})

onMounted(loadCases)
</script>

<template>
  <section class="section">
    <div class="section-title">Case List</div>
    <p>Browse resolved incidents and their learnings.</p>
    <div class="filter-bar">
      <input
        v-model="searchTerm"
        type="text"
        placeholder="Search by ID, title, tags, root cause..."
        aria-label="Search cases"
      />
      <select v-model="selectedCategory" aria-label="Filter by category">
        <option value="all">All categories</option>
        <option v-for="item in categories" :key="item" :value="item">
          {{ item }}
        </option>
      </select>
    </div>
  </section>

  <section v-if="loading" class="section">
    <div class="section-title">Loading...</div>
    <p>Fetching cases from backend.</p>
  </section>
  <section v-else-if="error" class="section">
    <div class="section-title">Failed to load</div>
    <p>{{ error }}</p>
  </section>
  <div v-else class="case-grid">
    <CaseCard v-for="item in filteredCases" :key="item.id" :case-item="item" />
  </div>
</template>
