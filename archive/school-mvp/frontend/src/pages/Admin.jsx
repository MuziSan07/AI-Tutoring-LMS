import { useEffect, useState } from 'react'
import { api, downloadJson } from '../api.js'
import { Loading, Stat, fmtDate } from '../components/ui.jsx'

function DailyChart({ daily }) {
  const max = Math.max(1, ...daily.map((d) => d.minutes || 0))
  return (
    <div className="colchart" role="img" aria-label="Tutoring minutes per day">
      {daily.map((d) => (
        <div key={d.day} className="col" title={`${d.day}: ${d.minutes || 0} min, ${d.lessons} lessons`}>
          <div className="colbar" style={{ height: `${((d.minutes || 0) / max) * 100}%` }} />
          <span>{d.day.slice(8)}</span>
        </div>
      ))}
    </div>
  )
}

export default function Admin({ user }) {
  const [data, setData] = useState(null)
  const [tab, setTab] = useState('overview')
  const load = () => api('/admin/overview').then(setData)
  useEffect(() => { load() }, [])
  if (!data) return <Loading />
  const org = data.orgs[0]
  const students = data.users.filter((u) => u.role === 'student')

  async function eraseLearning(u) {
    if (!window.confirm(`Delete all learning data for ${u.display_name}? The account stays, but lessons, answers and mastery are permanently removed.`)) return
    await api(`/students/${u.id}/learning-data`, { method: 'DELETE' })
    load()
  }
  async function setFlag(id, status) {
    await api(`/admin/flags/${id}`, { method: 'PUT', body: { status } })
    load()
  }

  return (
    <div className="page wide">
      <h1>{user.role === 'super_admin' ? 'Platform administration' : org?.name}</h1>
      <div className="tabs" role="tablist">
        {['overview', 'safeguarding', 'accounts', 'AI & audit'].map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
            {t[0].toUpperCase() + t.slice(1)}{t === 'safeguarding' && data.flags.filter((f) => f.status === 'open').length ? ` (${data.flags.filter((f) => f.status === 'open').length})` : ''}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="stats-row">
            <Stat label="Registered students" value={data.usage.registered_students} sub={org ? `${org.licence_seats} licensed seats` : ''} />
            <Stat label="Active students (30d)" value={data.usage.active_students_30d} />
            <Stat label="Tutoring minutes (30d)" value={data.usage.tutoring_minutes_30d} />
            <Stat label="Lessons (30d)" value={data.usage.lessons_30d} />
          </div>
          <div className="grid-2">
            <div className="card">
              <h3>Daily tutoring minutes</h3>
              <DailyChart daily={data.daily} />
            </div>
            <div className="card">
              <h3>Licences</h3>
              {data.orgs.map((o) => {
                const used = data.users.filter((u) => u.role === 'student').length
                return (
                  <div key={o.id} className="licence">
                    <strong>{o.name}</strong>
                    <div className="hbar"><div style={{ width: `${Math.min(100, (used / o.licence_seats) * 100)}%` }} /></div>
                    <span className="muted small">{used} of {o.licence_seats} seats used · renews {fmtDate(o.licence_expires)}</span>
                  </div>
                )
              })}
            </div>
          </div>
          <div className="card">
            <h3>Aggregated performance by topic</h3>
            <p className="muted small">Aggregated across students - no individual data shown.</p>
            <ul className="bars">
              {data.performance.map((p) => (
                <li key={p.topic_id}>
                  <span>{p.topic}</span>
                  <div className="hbar"><div style={{ width: `${p.accuracy * 100}%` }} /></div>
                  <span className="num">{Math.round(p.accuracy * 100)}% <small className="muted">{p.students} students</small></span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      {tab === 'safeguarding' && (
        <div className="card">
          <h3>Safeguarding concerns</h3>
          <p className="muted small">Raised automatically when a student's message suggests risk. Review and escalate to the Designated Safeguarding Lead.</p>
          {data.flags.length ? (
            <table className="table">
              <thead><tr><th>When</th><th>Student</th><th>Category</th><th>Excerpt</th><th>Status</th></tr></thead>
              <tbody>
                {data.flags.map((f) => (
                  <tr key={f.id}>
                    <td>{fmtDate(f.created_at, true)}</td>
                    <td>{f.display_name}<small className="muted block">{f.pseudonym_id}</small></td>
                    <td><span className="pill learning">{f.category.replace('_', ' ')}</span></td>
                    <td>"{f.excerpt}"</td>
                    <td>
                      <select value={f.status} onChange={(e) => setFlag(f.id, e.target.value)}>
                        <option value="open">Open</option><option value="escalated">Escalated to DSL</option><option value="resolved">Resolved</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No concerns raised.</p>}
        </div>
      )}

      {tab === 'accounts' && (
        <div className="card scroll-x">
          <h3>Accounts</h3>
          <p className="muted small">Students are identified internally by pseudonymous IDs.</p>
          <table className="table">
            <thead><tr><th>Name</th><th>Role</th><th>Internal ID</th><th>Email</th><th>Data controls</th></tr></thead>
            <tbody>
              {data.users.map((u) => (
                <tr key={u.id}>
                  <td>{u.display_name}{u.year_group ? <small className="muted"> · Y{u.year_group}</small> : ''}</td>
                  <td>{u.role.replace('_', ' ')}</td>
                  <td><code>{u.pseudonym_id}</code></td>
                  <td className="muted small">{u.email}</td>
                  <td>
                    {u.role === 'student' && (
                      <div className="row-actions">
                        <button className="btn small ghost" onClick={async () => downloadJson(await api(`/students/${u.id}/export`), `learning-record-${u.pseudonym_id}.json`)}>Export</button>
                        <button className="btn small danger" onClick={() => eraseLearning(u)}>Delete data</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{students.length} students</p>
        </div>
      )}

      {tab === 'AI & audit' && (
        <>
          <div className="card">
            <h3>AI model usage</h3>
            <p className="muted small">Active provider: <strong>{data.llm.provider}</strong> ({data.llm.model}). Maths answers are always verified by SymPy, independent of the model.</p>
            <table className="table">
              <thead><tr><th>Provider</th><th>Model</th><th>Calls</th><th>Tokens in / out</th><th>Avg latency</th><th>Cost</th></tr></thead>
              <tbody>
                {data.ai_usage.map((a) => (
                  <tr key={a.provider + a.model}>
                    <td>{a.provider}</td><td>{a.model}</td><td>{a.calls}</td>
                    <td>{a.input_tokens} / {a.output_tokens}</td><td>{(a.avg_latency_ms / 1000).toFixed(1)} s</td>
                    <td>${a.cost_usd.toFixed(4)}{a.students ? <small className="muted block">${(a.cost_usd / a.students).toFixed(4)} per student</small> : null}</td>
                  </tr>
                ))}
                {!data.ai_usage.length && <tr><td colSpan="6" className="muted">No model calls yet.</td></tr>}
              </tbody>
            </table>
          </div>
          <div className="card scroll-x">
            <h3>Audit log</h3>
            <table className="table">
              <thead><tr><th>Time</th><th>User</th><th>Action</th><th>Target</th></tr></thead>
              <tbody>
                {data.audit.map((a) => (
                  <tr key={a.id}><td className="small">{fmtDate(a.created_at, true)}</td><td>{a.display_name || 'system'}<small className="muted"> {a.role || ''}</small></td><td><code>{a.action}</code></td><td className="muted small">{a.target}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
