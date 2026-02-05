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

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.chip-critical {
  background: #fee2e2;
  color: #b91c1c;
}

.chip-high {
  background: #ffedd5;
  color: #c2410c;
}

.chip-medium {
  background: #fef3c7;
  color: #b45309;
}

.chip-low {
  background: #dcfce7;
  color: #15803d;
}

.bar-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bar-row {
  display: grid;
  grid-template-columns: 120px 1fr 40px;
  gap: 12px;
  align-items: center;
}

.bar-label {
  font-size: 13px;
  color: #475569;
}

.bar-track {
  background: #e2e8f0;
  border-radius: 999px;
  height: 8px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: #2563eb;
}

.bar-value {
  font-size: 12px;
  color: #475569;
  text-align: right;
}
</style>
