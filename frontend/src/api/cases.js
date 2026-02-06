const normalizeBaseUrl = (baseUrl) => {
  const trimmed = (baseUrl || '').replace(/\/$/, '')
  if (!trimmed) {
    return 'http://localhost:8000/api'
  }
  return trimmed.endsWith('/api') ? trimmed : `${trimmed}/api`
}

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000')

const fetchJson = async (path) => {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }
  return response.json()
}

export const getCases = async () => {
  const data = await fetchJson('/cases')
  return data.items || []
}

export const getCaseById = async (id) => {
  return fetchJson(`/cases/${encodeURIComponent(id)}`)
}

export const getTaxonomy = async () => {
  return fetchJson('/cases/taxonomy')
}
