const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

const fetchJson = async (path) => {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }
  return response.json()
}

export const getCases = async () => {
  const data = await fetchJson('/api/cases')
  return data.items || []
}

export const getCaseById = async (id) => {
  return fetchJson(`/api/cases/${encodeURIComponent(id)}`)
}

export const getTaxonomy = async () => {
  return fetchJson('/api/cases/taxonomy')
}
