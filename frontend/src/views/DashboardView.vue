<script setup>
import { computed, onMounted, ref } from 'vue'
import { getCases } from '../api/cases'

const cases = ref([])
const loading = ref(true)
const error = ref('')

const loadCases = async () => {
  loading.value = true
  error.value = ''
  try {
    cases.value = await getCases()
  } catch (err) {
    error.value = err?.message || 'Failed to load cases.'
    cases.value = []
  } finally {
    loading.value = false
  }
}

const totalCases = computed(() => cases.value.length)
const severityCounts = computed(() => {
  return cases.value.reduce(
    (acc, item) => {
      acc[item.severity] = (acc[item.severity] || 0) + 1
      return acc
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  )
})

const categoryCounts = computed(() => {
  return cases.value.reduce((acc, item) => {
    acc[item.category] = (acc[item.category] || 0) + 1
    return acc
  }, {})
})

const topCategories = computed(() => {
  return Object.entries(categoryCounts.value)
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value)
})

const maxCategoryCount = computed(() => {
  return Math.max(1, ...topCategories.value.map((item) => item.value))
})

onMounted(loadCases)
</script>

<template>
  <section class="section">
    <div class="section-title">Dashboard</div>
    <p>總覽事件數量與分布情況。</p>
  </section>

  <section v-if="loading" class="section">
    <div class="section-title">Loading...</div>
    <p>Fetching cases from backend.</p>
  </section>
  <section v-else-if="error" class="section">
    <div class="section-title">Failed to load</div>
    <p>{{ error }}</p>
  </section>

  <section v-else class="dashboard-grid">
    <div class="stat-card">
      <div class="stat-label">Total Cases</div>
      <div class="stat-value">{{ totalCases }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">High / Critical</div>
      <div class="stat-value">
        {{ severityCounts.critical + severityCounts.high }}
      </div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Medium</div>
      <div class="stat-value">{{ severityCounts.medium }}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Low</div>
      <div class="stat-value">{{ severityCounts.low }}</div>
    </div>
  </section>

  <section class="section">
    <div class="section-title">Cases by Severity</div>
    <div class="chip-row">
      <span class="chip chip-critical">Critical {{ severityCounts.critical }}</span>
      <span class="chip chip-high">High {{ severityCounts.high }}</span>
      <span class="chip chip-medium">Medium {{ severityCounts.medium }}</span>
      <span class="chip chip-low">Low {{ severityCounts.low }}</span>
    </div>
  </section>

  <section class="section">
    <div class="section-title">Top Categories</div>
    <div class="bar-list">
      <div v-for="item in topCategories" :key="item.label" class="bar-row">
        <div class="bar-label">{{ item.label }}</div>
        <div class="bar-track">
          <div
            class="bar-fill"
            :style="{ width: `${(item.value / maxCategoryCount) * 100}%` }"
          ></div>
        </div>
        <div class="bar-value">{{ item.value }}</div>
      </div>
    </div>
  </section>
</template>
