<script setup>
import { computed, ref } from 'vue'
import { getCases, getCategories } from '../api/cases'
import CaseCard from '../components/CaseCard.vue'

const searchTerm = ref('')
const selectedCategory = ref('all')

const categories = computed(() => getCategories())

const cases = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  return getCases().filter((item) => {
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

  <div class="case-grid">
    <CaseCard v-for="item in cases" :key="item.id" :case-item="item" />
  </div>
</template>