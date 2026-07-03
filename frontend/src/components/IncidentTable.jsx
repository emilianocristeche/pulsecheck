export default function IncidentTable({ checks }) {
  if (checks.length === 0) {
    return <div className="empty">No checks recorded yet.</div>
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Time</th>
          <th>HTTP</th>
          <th>Response</th>
          <th>Error</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((c) => (
          <tr key={c.id}>
            <td>
              <span className={`dot ${c.is_up ? 'up' : 'down'}`} />
              {c.is_up ? 'UP' : 'DOWN'}
            </td>
            <td>{new Date(c.timestamp).toLocaleString()}</td>
            <td>{c.status_code ?? '—'}</td>
            <td>{c.response_time_ms != null ? `${Math.round(c.response_time_ms)}ms` : '—'}</td>
            <td>{c.error_msg ? <span className="error-msg" title={c.error_msg}>{c.error_msg}</span> : '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
