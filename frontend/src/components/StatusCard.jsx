import { useEffect, useState } from 'react'
import { api } from '../api'

export default function StatusCard({ endpoint, selected, onSelect, onDelete, onToggle }) {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.getStats(endpoint.id).then(setStats).catch(() => {})
    const t = setInterval(() => api.getStats(endpoint.id).then(setStats).catch(() => {}), 30000)
    return () => clearInterval(t)
  }, [endpoint.id])

  const statusKey = endpoint.last_status === null ? 'unknown' : endpoint.last_status ? 'up' : 'down'
  const statusLabel = { up: 'UP', down: 'DOWN', unknown: '—' }[statusKey]

  return (
    <div
      className={`card ${statusKey} ${selected ? 'selected' : ''}`}
      onClick={onSelect}
    >
      <div className="card-header">
        <span className="name">{endpoint.name}</span>
        <span className={`badge ${statusKey}`}>{statusLabel}</span>
      </div>
      <div className="card-url">{endpoint.url}</div>
      <div className="card-stats">
        <div className="stat">
          <label>Uptime</label>
          <value>{stats ? `${stats.uptime_percent}%` : '—'}</value>
        </div>
        <div className="stat">
          <label>Avg Response</label>
          <value>{stats?.avg_response_time_ms ? `${stats.avg_response_time_ms}ms` : '—'}</value>
        </div>
        <div className="stat">
          <label>Checks</label>
          <value>{stats?.total_checks ?? '—'}</value>
        </div>
      </div>
      <div className="card-actions" onClick={(e) => e.stopPropagation()}>
        <button className="ghost" onClick={onToggle}>
          {endpoint.is_active ? 'Pause' : 'Resume'}
        </button>
        <button className="ghost danger" onClick={onDelete}>Delete</button>
      </div>
    </div>
  )
}
