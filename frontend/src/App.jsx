import { useEffect, useState } from 'react'
import { api } from './api'
import StatusCard from './components/StatusCard'
import UptimeChart from './components/UptimeChart'
import IncidentTable from './components/IncidentTable'
import AddEndpointForm from './components/AddEndpointForm'

export default function App() {
  const [endpoints, setEndpoints] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [checks, setChecks] = useState([])

  useEffect(() => {
    load()
    const t = setInterval(load, 30000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (!selectedId) return
    api.getChecks(selectedId, 50).then(setChecks).catch(() => setChecks([]))
    const t = setInterval(
      () => api.getChecks(selectedId, 50).then(setChecks).catch(() => {}),
      15000
    )
    return () => clearInterval(t)
  }, [selectedId])

  async function load() {
    try {
      setEndpoints(await api.getEndpoints())
    } catch {
      // backend not reachable yet
    }
  }

  function handleAdded(ep) {
    setEndpoints((prev) => [...prev, ep])
    setSelectedId(ep.id)
  }

  async function handleDelete(id) {
    await api.deleteEndpoint(id)
    setEndpoints((prev) => prev.filter((e) => e.id !== id))
    if (selectedId === id) setSelectedId(null)
  }

  async function handleToggle(id) {
    const updated = await api.toggleEndpoint(id)
    setEndpoints((prev) => prev.map((e) => (e.id === id ? updated : e)))
  }

  function handleSelect(id) {
    setSelectedId((prev) => (prev === id ? null : id))
  }

  const selected = endpoints.find((e) => e.id === selectedId)

  return (
    <>
      <header>
        <div className="pulse-dot" />
        <h1>PulseCheck</h1>
        <span>{endpoints.length} endpoint{endpoints.length !== 1 ? 's' : ''} monitored</span>
      </header>
      <main>
        <AddEndpointForm onAdded={handleAdded} />

        {endpoints.length === 0 ? (
          <div className="empty">No endpoints yet. Add one above to start monitoring.</div>
        ) : (
          <div className="grid">
            {endpoints.map((ep) => (
              <StatusCard
                key={ep.id}
                endpoint={ep}
                selected={selectedId === ep.id}
                onSelect={() => handleSelect(ep.id)}
                onDelete={() => handleDelete(ep.id)}
                onToggle={() => handleToggle(ep.id)}
              />
            ))}
          </div>
        )}

        {selected && (
          <div className="detail">
            <h3>Response time — {selected.name} (last 50 successful checks)</h3>
            <div className="chart-wrap">
              <UptimeChart checks={checks} />
            </div>
            <h3 style={{ marginBottom: '0.75rem' }}>Incident log (last 50)</h3>
            <IncidentTable checks={checks} />
          </div>
        )}
      </main>
    </>
  )
}
