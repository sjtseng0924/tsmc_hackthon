<script setup>
import { onMounted, ref, watch, onUnmounted } from 'vue'
import * as d3 from 'd3'
import { useRouter } from 'vue-router'

const router = useRouter()

const props = defineProps({
  cases: {
    type: Array,
    default: () => []
  }
})

const container = ref(null)
let simulation = null

// Process data into nodes and links
const processData = (caseItems) => {
  const nodes = []
  const links = []
  const nodeSet = new Set()
  
  // 1. Extract Nodes and Links
  caseItems.forEach(c => {
    // Case Node
    if (!nodeSet.has(c.filename)) {
      nodes.push({ 
        id: c.filename, 
        group: 'case', 
        name: c.title || c.filename, // Use Title
        title: c.title,
        severity: c.severity 
      })
      nodeSet.add(c.filename)
    }
    
    // Team Nodes from Preventive Measures
    if (c.preventiveMeasures && Array.isArray(c.preventiveMeasures)) {
      c.preventiveMeasures.forEach(pm => {
        const owner = pm.owner ? pm.owner.trim() : 'Unknown Team'
        if (!owner) return

        // Create Team Node if not exists
        if (!nodeSet.has(owner)) {
          nodes.push({ 
            id: owner, 
            group: 'team', 
            name: owner,
            radius: 30 // Larger for teams too
          })
          nodeSet.add(owner)
        }
        
        links.push({
          source: owner,
          target: c.filename,
          value: 1
        })
      })
    }
  })
  
  return { nodes, links }
}

const renderGraph = () => {
  if (!container.value) return
  
  // Clear previous
  d3.select(container.value).selectAll('*').remove()
  
  const { nodes, links } = processData(props.cases)
  
  if (nodes.length === 0) {
    d3.select(container.value)
      .append('div')
      .attr('class', 'no-data')
      .text('No data for graph')
    return
  }

  const width = container.value.clientWidth
  const height = container.value.clientHeight || 700

  const svg = d3.select(container.value)
    .append('svg')
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', [0, 0, width, height])
    .attr('style', 'max-width: 100%; height: auto;')

  // Helper for text wrapping
  const wrapText = (text, maxCharsPerLine = 8) => {
    // If text contains spaces (English/Mixed)
    if (text.includes(' ') && /[a-zA-Z]/.test(text)) {
        const words = text.split(/\s+/);
        let lines = [];
        let currentLine = words[0];

        for (let i = 1; i < words.length; i++) {
            const word = words[i];
            if ((currentLine + " " + word).length <= maxCharsPerLine + 4) { // Allow slightly looser for English
                currentLine += " " + word;
            } else {
                lines.push(currentLine);
                currentLine = word;
            }
        }
        lines.push(currentLine);
        return lines;
    } else {
        // CJK or continuous string
        return text.match(new RegExp(`.{1,${maxCharsPerLine}}`, 'g')) || [text];
    }
  };

  // Helper to calculate geometry for a node (radius and box size)
  const getNodeGeometry = (d) => {
     let r, boxSize;
     if (d.group === 'case') {
         // Dynamic radius based on text length
         const isCJK = /[^\x00-\x7F]/.test(d.name || '');
         const lines = wrapText(d.name || '', isCJK ? 7 : 12).length;
         r = Math.max(35, lines * 9 + 20);
         
         // 1.4x for cases (strict margin)
         boxSize = r * 1.4; 
     } else {
         // Fixed radius for teams
         r = 40;
         
         // 1.8x for teams (larger box to avoid clipping)
         boxSize = r * 1.8; 
     }
     return { r, boxSize };
  };

  const selectedTeamId = ref(null)

  // Neighbor map for quick lookup
  const neighbors = new Map()
  links.forEach(link => {
      // Look up nodes by ID (simulation replaces id string with object, handle both)
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source
      const targetId = typeof link.target === 'object' ? link.target.id : link.target
      
      // Initialize sets using correct IDs
      if (!neighbors.has(sourceId)) neighbors.set(sourceId, new Set())
      if (!neighbors.has(targetId)) neighbors.set(targetId, new Set())
      
      neighbors.get(sourceId).add(targetId)
      neighbors.get(targetId).add(sourceId)
  })

  // Function to update forces based on selection
  const updateForces = () => {
      const width = container.value.clientWidth
      const height = container.value.clientHeight || 700
      
      if (selectedTeamId.value) {
          // Focused Mode: Selected Team Center, Neighbors Circle
          const teamId = selectedTeamId.value
          
          // Get neighbors of selected team
          const relatedNodeIds = Array.from(neighbors.get(teamId) || [])
          const count = relatedNodeIds.length
          const radius = 200 // Distance from team
          
          // Calculate target positions for neighbors
          const neighborTargets = new Map()
          relatedNodeIds.forEach((nid, i) => {
              const angle = (i / count) * 2 * Math.PI - Math.PI / 2 // Start from top
              neighborTargets.set(nid, {
                  x: width / 2 + radius * Math.cos(angle),
                  y: height / 2 + radius * Math.sin(angle)
              })
          })

          // Custom force to pull nodes to their targets
          simulation
            .force('radial', null) // Disable radial
            .force('center', d3.forceCenter(width / 2, height / 2).strength(0.1)) // Weak center
            .force('focusX', d3.forceX(d => {
                if (d.id === teamId) return width / 2
                if (neighborTargets.has(d.id)) return neighborTargets.get(d.id).x
                return width / 2 // Others weakly to center (or push away if needed)
            }).strength(d => {
                if (d.id === teamId) return 1 // Strong fix for team
                if (neighborTargets.has(d.id)) return 0.8 // Strong pull for neighbors
                return 0.05 // Weak for others
            }))
            .force('focusY', d3.forceY(d => {
                if (d.id === teamId) return height / 2
                if (neighborTargets.has(d.id)) return neighborTargets.get(d.id).y
                return height / 2
            }).strength(d => {
                if (d.id === teamId) return 1
                if (neighborTargets.has(d.id)) return 0.8
                return 0.05
            }))
            .force('charge', d3.forceManyBody().strength(d => {
                 if (d.id === teamId) return -1000
                 if (neighborTargets.has(d.id)) return -300
                 return -500 // Repel outgoing
            }))
            
      } else {
          // Default Mode
          simulation
            .force('focusX', null)
            .force('focusY', null)
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('radial', d3.forceRadial(d => d.group === 'team' ? 50 : 300, width / 2, height / 2).strength(0.8))
            .force('charge', d3.forceManyBody().strength(-500))
      }
      
      simulation.alpha(0.3).restart()
  }

  // Simulation setup overrides
  // We initialize with default forces first
  simulation = d3.forceSimulation(nodes)
    .velocityDecay(0.7) // Increase friction to slow down movement (default ~0.4)
    .force('link', d3.forceLink(links).id(d => d.id).distance(150)) 
    .force('charge', d3.forceManyBody().strength(-500)) 
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(d => getNodeGeometry(d).r + 10))
    .force('radial', d3.forceRadial(d => d.group === 'team' ? 50 : 300, width / 2, height / 2).strength(0.8))

  // Link elements
  const link = svg.append('g')
    .attr('stroke', '#ccc')
    .attr('stroke-opacity', 0.6)
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('stroke-width', 1.5)

  // Node elements
  const node = svg.append('g')
    .attr('stroke', '#fff')
    .attr('stroke-width', 0) 
    .selectAll('g')
    .data(nodes)
    .join('g')
    .call(d3.drag()
      .on('start', dragstarted)
      .on('drag', dragged)
      .on('end', dragended))
      .on('click', (event, d) => { 
        if (d.group === 'case') {
             router.push({ name: 'case-detail', params: { id: d.id } })
        } else if (d.group === 'team') {
             // Toggle selection
             if (selectedTeamId.value === d.id) {
                 selectedTeamId.value = null
             } else {
                 selectedTeamId.value = d.id
             }
             updateForces()
             event.stopPropagation() // Prevent background click
        }
      })
      .style('cursor', 'pointer') // All pointers now interactive

  // Draw circles based on group
  node.append('circle')
    .attr('r', d => getNodeGeometry(d).r)
    .attr('fill', d => {
      if (d.group === 'team') return '#7C7C7C' 
      return '#D14E52' 
    })

  // Add labels using foreignObject for HTML-like wrapping
  node.append('foreignObject')
    .attr('x', d => -getNodeGeometry(d).boxSize / 2)
    .attr('y', d => -getNodeGeometry(d).boxSize / 2)
    .attr('width', d => getNodeGeometry(d).boxSize)
    .attr('height', d => getNodeGeometry(d).boxSize)
    .style('pointer-events', 'none') // Let clicks pass to the circle
    .append('xhtml:div')
    .style('width', '100%')
    .style('height', '100%')
    .style('display', 'flex')
    .style('justify-content', 'center')
    .style('align-items', 'center')
    .style('text-align', 'center')
    .style('word-wrap', 'break-word')
    .style('white-space', 'pre-line')
    .style('font-size', '11px')
    .style('font-weight', '500')
    .style('color', '#ffffff')
    .style('line-height', '1.2')
    .style('overflow', 'hidden')
    .style('padding', '2px') 
    .html(d => d.name);
    
  // Tooltip title
  node.append('title')
    .text(d => d.group === 'case' ? `${d.title} (${d.severity})` : `Team: ${d.name}`)

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)

    node
      .attr('transform', d => `translate(${d.x},${d.y})`)
  })

  // Background click to deselect
  svg.on('click', () => {
      if (selectedTeamId.value) {
          selectedTeamId.value = null
          updateForces()
      }
  })

  // Drag functions
  function dragstarted(event) {
    if (!event.active) simulation.alphaTarget(0.3).restart()
    event.subject.fx = event.subject.x
    event.subject.fy = event.subject.y

    // If dragging while selected, maybe keep forces?
    // For now, let's keep the behavior: manual drag overrides forces temporarily
    // But if we are in "Focused Mode", the strong forceX/Y might fight back.
    // So usually we pause custom forces on drag or let the drag `fx` win (which D3 does automatically).
    
    // However, user asked to "cancel force" on drag previously. 
    // If we are in "Focused Mode", we might want to stay in focused mode but allow adjustment?
    // Or just cancel layout? 
    // Let's stick to: Dragging cancels the *Radial* constraint if in default mode.
    // If in Focused mode, maybe we strictly hold layout? 
    // Let's allow free drag -> disable custom positioning forces
    
    simulation.force('radial', null)
    simulation.force('focusX', null)
    simulation.force('focusY', null)
  }

  function dragged(event) {
    event.subject.fx = event.x
    event.subject.fy = event.y
  }

  function dragended(event) {
    if (!event.active) simulation.alphaTarget(0)
    event.subject.fx = null
    event.subject.fy = null
  }
}

watch(() => props.cases, () => {
  renderGraph()
}, { deep: true })

onMounted(() => {
  renderGraph()
  window.addEventListener('resize', renderGraph)
})

onUnmounted(() => {
  if (simulation) simulation.stop()
  window.removeEventListener('resize', renderGraph)
})

</script>

<template>
  <div class="graph-container" ref="container"></div>
</template>

<style scoped>
.graph-container {
  width: 100%;
  height: 500px;
  background: #f8fafc;
  border-radius: 12px;
  overflow: hidden;
  position: relative;
}

:deep(.no-data) {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #94a3b8;
}
</style>
