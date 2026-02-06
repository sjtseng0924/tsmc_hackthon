<script setup>
import { computed, onMounted, ref, provide } from 'vue'
import { getCases } from '../api/cases'
import CaseCard from '../components/CaseCard.vue'

// ECHARTS IMPORTS
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'
import VChart, { THEME_KEY } from 'vue-echarts'

// Register ECharts components
use([
  CanvasRenderer,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

provide(THEME_KEY, 'light')

// -- STATE --
const cases = ref([])
const loading = ref(true)
const error = ref('')

// -- FILTERS --
const searchTerm = ref('')
const selectedSeverities = ref(['critical', 'high', 'medium', 'low'])

// -- DATA FETCHING --
const loadCases = async () => {
  loading.value = true
  error.value = ''
  try {
    const caseItems = await getCases()
    cases.value = caseItems
  } catch (err) {
    error.value = err?.message || 'Failed to load cases.'
  } finally {
    loading.value = false
  }
}

onMounted(loadCases)

// -- COMPUTED: FILTERING --
const filteredCases = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  return cases.value.filter((item) => {
    // 1. Severity Filter
    if (!selectedSeverities.value.includes(item.severity.toLowerCase())) {
      return false
    }

    // 2. (Category removed)

    // 3. Search Term
    if (!term) return true
    const haystack = [
      item.filename,
      item.title,
      item.rootCause,
    ]
      .join(' ')
      .toLowerCase()

    return haystack.includes(term)
  })
})

// -- STATISTICS FOR CHARTS (Reactive to Filtered Cases) --
const severityCounts = computed(() => {
  return filteredCases.value.reduce(
    (acc, item) => {
      const s = item.severity ? item.severity.toLowerCase() : 'medium'
      acc[s] = (acc[s] || 0) + 1
      return acc
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  )
})

// -- ECHARTS OPTIONS --

const pieOption = computed(() => {
  return {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      bottom: 'bottom'
    },
    series: [
      {
        name: 'Severity',
        type: 'pie',
        radius: ['50%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: false,
          position: 'center'
        },
        emphasis: {
          label: {
            show: true,
            fontSize: '18',
            fontWeight: 'bold'
          }
        },
        labelLine: {
          show: false
        },
        data: [
          { value: severityCounts.value.critical, name: 'Critical', itemStyle: { color: '#b91c1c' } },
          { value: severityCounts.value.high, name: 'High', itemStyle: { color: '#c2410c' } },
          { value: severityCounts.value.medium, name: 'Medium', itemStyle: { color: '#b45309' } },
          { value: severityCounts.value.low, name: 'Low', itemStyle: { color: '#15803d' } }
        ]
      }
    ]
  }
})

</script>

<template>
  <div class="analysis-page">
    <!-- Top Section: Visualization -->
    <section class="viz-section">
      
      <div class="viz-card">
        <div class="card-title">Severity Distribution</div>
        <div class="chart-container">
          <v-chart class="chart" :option="pieOption" autoresize />
        </div>
      </div>
      
    </section>

    <!-- Bottom Section: Split Layout -->
    <section class="content-split">
      
      <!-- Left Sidebar: Filters -->
      <aside class="filters-sidebar">
        <div class="sidebar-header">Filters</div>
        
        <div class="filter-group">
          <label class="filter-label">Search</label>
          <input 
            v-model="searchTerm" 
            type="text" 
            class="search-input"
            placeholder="Search filtered results..." 
          />
        </div>



        <div class="filter-group">
          <label class="filter-label">Severity</label>
          <div class="checkbox-list">
            <label class="checkbox-item">
              <input type="checkbox" value="critical" v-model="selectedSeverities" />
              <span class="cb-label critical">Critical</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" value="high" v-model="selectedSeverities" />
              <span class="cb-label high">High</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" value="medium" v-model="selectedSeverities" />
              <span class="cb-label medium">Medium</span>
            </label>
            <label class="checkbox-item">
              <input type="checkbox" value="low" v-model="selectedSeverities" />
              <span class="cb-label low">Low</span>
            </label>
          </div>
        </div>
        
        <div class="results-count">
          Showing {{ filteredCases.length }} reports
        </div>
      </aside>

      <!-- Right Main: Case List -->
      <main class="cases-main">
        <div v-if="loading" class="loading-state">Loading reports...</div>
        <div v-else-if="error" class="error-state">{{ error }}</div>
        
        <div v-else class="case-grid">
          <CaseCard v-for="item in filteredCases" :key="item.filename" :case-item="item" />
          <div v-if="filteredCases.length === 0" class="empty-state">
            No reports match your filters.
          </div>
        </div>
      </main>

    </section>
  </div>
</template>

<style scoped>
.analysis-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Visualization Section */
.viz-section {
  display: block;
}

.viz-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  height: 400px; /* Fixed height for charts */
  display: flex;
  flex-direction: column;
}

.card-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 16px;
}

.chart-container {
  flex: 1;
  min-height: 0; /* Important for flex child with chart */
}

.chart {
  height: 100%;
  width: 100%;
}

@media (max-width: 1024px) {
  .viz-section {
    grid-template-columns: 1fr;
  }
}

/* Split Content */
.content-split {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 24px;
  align-items: start;
}

@media (max-width: 768px) {
  .content-split {
    grid-template-columns: 1fr;
  }
}

/* Sidebar Styles */
.filters-sidebar {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 20px;
  position: sticky;
  top: 24px;
}

.sidebar-header {
  font-size: 18px;
  font-weight: 700;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.filter-group {
  margin-bottom: 24px;
}

.filter-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.search-input, .category-select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.search-input:focus, .category-select:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #334155;
}

.cb-label.critical { color: #b91c1c; }
.cb-label.high { color: #c2410c; }
.cb-label.medium { color: #b45309; }
.cb-label.low { color: #15803d; }

.results-count {
  margin-top: 20px;
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
}

/* Main Content Styles */
.case-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
  color: #94a3b8;
  background: #f8fafc;
  border-radius: 12px;
  border: 2px dashed #e2e8f0;
}
</style>
