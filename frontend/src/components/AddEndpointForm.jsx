import { useState } from 'react'
import { api } from '../api'

export default function AddEndpointForm({ onAdded }) {
  const [form, setForm] = useState({ name: '', url: '', expected_status: 200, interval_seconds: 60 })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    if (!form.name || !form.url) return
    setLoading(true)
    setErr(null)
    try {
      const ep = await api.createEndpoint({
        ...form,
        expected_status: Number(form.expected_status),
        interval_seconds: Number(form.interval_seconds),
      })
      onAdded(ep)
      setForm({ name: '', url: '', expected_status: 200, interval_seconds: 60 })
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="add-form">
      <h2>Add Endpoint</h2>
      <form onSubmit={submit}>
        <div className="form-row">
          <input name="name" placeholder="Name" value={form.name} onChange={set('name')} required />
          <input name="url" placeholder="https://example.com" value={form.url} onChange={set('url')} required />
          <input name="expected_status" type="number" value={form.expected_status} onChange={set('expected_status')} title="Expected HTTP status" />
          <input name="interval_seconds" type="number" min={10} value={form.interval_seconds} onChange={set('interval_seconds')} title="Check interval (seconds)" />
          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Adding…' : '+ Add'}
          </button>
        </div>
        {err && <p style={{ color: '#ef4444', marginTop: '0.5rem', fontSize: '0.8rem' }}>{err}</p>}
      </form>
    </div>
  )
}
