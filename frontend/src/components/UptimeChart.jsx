import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

export default function UptimeChart({ checks }) {
  // checks come in desc order from API — reverse for chronological display
  const data = [...checks]
    .reverse()
    .filter((c) => c.is_up && c.response_time_ms != null)
    .map((c, i) => ({
      i,
      ms: Math.round(c.response_time_ms),
      time: new Date(c.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }))

  if (data.length === 0) {
    return <div className="empty" style={{ paddingTop: '1rem' }}>No successful checks yet.</div>
  }

  const avg = Math.round(data.reduce((s, d) => s + d.ms, 0) / data.length)

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <XAxis dataKey="time" tick={{ fill: '#64748b', fontSize: 11 }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} unit="ms" width={55} />
        <Tooltip
          contentStyle={{ background: '#0f1117', border: '1px solid #1e2535', borderRadius: 6 }}
          labelStyle={{ color: '#94a3b8' }}
          itemStyle={{ color: '#3b82f6' }}
          formatter={(v) => [`${v}ms`, 'Response']}
        />
        <ReferenceLine y={avg} stroke="#64748b" strokeDasharray="3 3" label={{ value: `avg ${avg}ms`, fill: '#64748b', fontSize: 11 }} />
        <Line
          type="monotone"
          dataKey="ms"
          stroke="#3b82f6"
          dot={false}
          strokeWidth={2}
          activeDot={{ r: 4, fill: '#3b82f6' }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
