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
const severityThreshold = ref(0) // 0: All, 1: Medium+, 2: High+, 3: Critical
const selectedTeams = ref(['All']) // default select all teams

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

const SEVERITY_MAP = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3
}

// -- METHODS --
const handleTeamChange = (team) => {
  if (team === 'All') {
    selectedTeams.value = ['All']
    return
  }
  
  // If "All" was previously selected, clear it and select this team
  if (selectedTeams.value.includes('All')) {
    selectedTeams.value = [team]
    return
  }

  // Toggle selection
  const idx = selectedTeams.value.indexOf(team)
  if (idx > -1) {
    selectedTeams.value.splice(idx, 1)
  } else {
    selectedTeams.value.push(team)
  }

  // If nothing selected, revert to All
  if (selectedTeams.value.length === 0) {
    selectedTeams.value = ['All']
  }
}

// -- COMPUTED: HELPERS --
const availableTeams = computed(() => {
  const teams = new Set()
  cases.value.forEach(c => {
    if (c.preventiveMeasures) {
      c.preventiveMeasures.forEach(pm => {
        if (pm.owner) teams.add(pm.owner.trim())
      })
    }
  })
  return Array.from(teams).sort()
})

// -- COMPUTED: FILTERING --
const filteredCases = computed(() => {
  const term = searchTerm.value.trim().toLowerCase()
  return cases.value.filter((item) => {
    // 1. Severity Filter (Threshold)
    const itemSevValue = SEVERITY_MAP[item.severity?.toLowerCase()] ?? 1 // default medium
    if (itemSevValue < severityThreshold.value) {
      return false
    }

    // 2. Team Filter (Multi-select with 'All')
    if (!selectedTeams.value.includes('All') && selectedTeams.value.length > 0) {
      const itemTeams = item.preventiveMeasures?.map(pm => pm.owner?.trim()) || []
      const hasMatch = itemTeams.some(t => selectedTeams.value.includes(t))
      if (!hasMatch) return false
    }

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

// -- STATISTICS FOR CHARTS (Global Data) --
const severityCounts = computed(() => {
  return cases.value.reduce(
    (acc, item) => {
      const s = item.severity ? item.severity.toLowerCase() : 'medium'
      acc[s] = (acc[s] || 0) + 1
      return acc
    },
    { critical: 0, high: 0, medium: 0, low: 0 }
  )
})

const teamWorkload = computed(() => {
  const counts = {} // record each team's workload
  cases.value.forEach(item => {
    let handled = false
    if (item.preventiveMeasures && Array.isArray(item.preventiveMeasures)) {
      item.preventiveMeasures.forEach(obj => {
        const owner = obj.owner ? obj.owner.trim() : 'Unassigned' // 'QA Team / AI Team / ...'
        counts[owner] = (counts[owner] || 0) + 1
        // console.log(`[${item.filename}] Found owner: "${owner}". Current count:`, counts[owner])
        handled = true
      })
    } 
    
    if (!handled) {
      counts['Unassigned'] = (counts['Unassigned'] || 0) + 1
    }
  })
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1]) // Sort desc
})

// Colors
const SEVERITY_COLORS = {
  critical: '#E55353',
  high: '#2D3436',
  medium: '#95A5A6',
  low: '#DCDDE1'
}

const TEAM_COLORS = [
  '#D63031', '#E55353', '#FF7675', 
  '#1E272E', '#2D3436', '#485460', 
  '#7F8C8D', '#95A5A6', '#BDC3C7' 
]

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
          { value: severityCounts.value.critical, name: 'Critical', itemStyle: { color: SEVERITY_COLORS.critical } },
          { value: severityCounts.value.high, name: 'High', itemStyle: { color: SEVERITY_COLORS.high } },
          { value: severityCounts.value.medium, name: 'Medium', itemStyle: { color: SEVERITY_COLORS.medium } },
          { value: severityCounts.value.low, name: 'Low', itemStyle: { color: SEVERITY_COLORS.low } }
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
        <div class="card-title">事件等級分佈</div>
        <div class="chart-container">
          <v-chart class="chart" :option="pieOption" autoresize />
        </div>
      </div>

      <div class="viz-card">
        <div class="card-title">Team Workload</div>
        <div class="bar-list-container">
          <div 
            v-for="(item, index) in teamWorkload" 
            :key="item[0]" 
            class="bar-row"
          >
            <div class="bar-label">{{ item[0] }}</div>
            <div class="bar-track">
              <div 
                class="bar-fill" 
                :style="{ 
                  width: `${(item[1] / (teamWorkload[0]?.[1] || 1)) * 100}%`,
                  backgroundColor: TEAM_COLORS[index % TEAM_COLORS.length]
                }"
              ></div>
              <span class="bar-count">{{ item[1] }}</span>
            </div>
          </div>
          
          <div v-if="teamWorkload.length === 0" class="no-data">
            No active workload data
          </div>
        </div>
      </div>
      
    </section>

    <!-- Bottom Section: Split Layout -->
    <section class="content-split">
      <!-- ... filters ... -->
      <aside class="filters-sidebar">
        <!-- ... sidebar content ... -->
        <div class="sidebar-header">搜尋特定結案報告</div>
        
        <div class="filter-group">
          <label class="filter-label">關鍵字搜尋</label>
          <input 
            v-model="searchTerm" 
            type="text" 
            class="search-input"
            placeholder="keyword" 
          />
        </div>

        <!-- Severity Slider -->
        <div class="filter-group">
          <label class="filter-label">事件等級</label>
          <div class="slider-container">
            <input 
              type="range" 
              min="0" 
              max="3" 
              step="1" 
              v-model.number="severityThreshold" 
              class="severity-slider"
            />
            <div class="slider-labels">
              <span>Low</span>
              <span>Med</span>
              <span>High</span>
              <span>Critical</span>
            </div>
          </div>
        </div>

        <!-- Team Filter -->
        <div class="filter-group">
          <label class="filter-label">部門</label>
          <div class="checkbox-list scrollable">
            <!-- All Option -->
            <label class="checkbox-item try-all">
              <input 
                type="checkbox" 
                :checked="selectedTeams.includes('All')" 
                @change="handleTeamChange('All')" 
              />
              <span class="cb-label-text">All (所有部門)</span>
            </label>

            <!-- Loop Option -->
            <label v-for="team in availableTeams" :key="team" class="checkbox-item">
              <input 
                type="checkbox" 
                :value="team" 
                :checked="selectedTeams.includes(team)" 
                @change="handleTeamChange(team)" 
              />
              <span class="cb-label-text">{{ team }}</span>
            </label>
            
            <div v-if="availableTeams.length === 0" class="no-options">
              No teams found
            </div>
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
  display: grid;
  grid-template-columns: 3fr 7fr;
  gap: 24px;
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

.viz-card.full-width {
  height: auto;
  min-height: 500px;
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

/* HTML Bar Chart Styles */
.bar-list-container {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bar-label {
  width: 140px;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  text-align: right;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 24px;
}

.bar-fill {
  height: 100%;
  border-radius: 4px 12px 12px 4px; /* Rounded right */
  transition: width 0.5s ease-out;
  min-width: 4px;
}

.bar-count {
  font-size: 13px;
  color: #64748b;
  font-weight: 600;
}

.no-data {
  text-align: center;
  color: #94a3b8;
  margin-top: 40px;
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

.cb-label.critical { color: #E55353; }
.cb-label.high { color: #2D3436; }
.cb-label.medium { color: #95A5A6; }
.cb-label.low { color: #DCDDE1; }


/* Scrollable Checkbox List */
.checkbox-list.scrollable {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #f1f5f9;
  border-radius: 8px;
  padding: 8px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #334155;
  padding: 4px 0;
}

.cb-label-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-options {
  font-size: 13px;
  color: #94a3b8;
  text-align: center;
  padding: 8px 0;
}

/* Slider Styles */
.slider-container {
  padding: 0 4px;
}

.severity-slider {
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  margin: 12px 0;
}

.severity-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #64748b;
  margin-top: -4px;
}

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
