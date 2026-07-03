const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  getEndpoints: () => req('/api/endpoints/'),
  createEndpoint: (data) => req('/api/endpoints/', { method: 'POST', body: JSON.stringify(data) }),
  deleteEndpoint: (id) => req(`/api/endpoints/${id}`, { method: 'DELETE' }),
  toggleEndpoint: (id) => req(`/api/endpoints/${id}/toggle`, { method: 'PATCH' }),
  getChecks: (id, limit = 50) => req(`/api/checks/${id}?limit=${limit}`),
  getStats: (id) => req(`/api/checks/${id}/stats`),
}
