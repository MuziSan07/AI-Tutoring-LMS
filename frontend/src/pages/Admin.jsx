import { useEffect, useState } from 'react'
import { api, downloadJson } from '../api.js'
import { Loading, Stat, fmtDate, timeAgo } from '../components/ui.jsx'

function DailyChart({ daily }) {
  const max = Math.max(1, ...daily.map((d) => d.minutes || 0))
  return (
    <div className="colchart" role="img" aria-label="Learning minutes per day">
      {daily.map((d) => (
        <div key={d.day} className="col" title={`${d.day}: ${d.minutes} min, ${d.learners} learners`}>
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
  const [filter, setFilter] = useState('')
  const load = () => api('/admin/overview').then(setData)
  useEffect(() => { load() }, [])
  if (!data) return <Loading />
  const s = data.stats
  const open = data.flags.filter((f) => f.status !== 'resolved').length

  const setUser = async (id, body) => { await api(`/admin/users/${id}`, { method: 'PUT', body }); load() }
  const erase = async (u) => {
    if (!window.confirm(`Permanently delete all learning data for ${u.display_name}? Their account stays, but progress, answers, notes, certificates and tutor chats are removed. This cannot be undone.`)) return
    await api(`/admin/users/${u.id}/data`, { method: 'DELETE' })
    load()
  }
  const users = data.users.filter((u) => `${u.display_name} ${u.email} ${u.role}`.toLowerCase().includes(filter.toLowerCase()))

  return (
    <div className="page wide">
      <h1>Academy admin</h1>
      <div className="tabs" role="tablist">
        {[['overview', 'Overview'], ['users', 'Users'], ['moderation', `Moderation${open ? ` (${open})` : ''}`], ['ai', 'AI & audit']].map(([id, label]) => (
          <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'on' : ''} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="stats-row">
            <Stat label="Learners" value={s.learners} sub={`${s.active_7d} active this week`} />
            <Stat label="Enrolments" value={s.enrolments} sub={`${s.courses} published courses`} />
            <Stat label="Completions" value={s.completions} sub={`${s.certificates} certificates`} />
            <Stat label="Learning minutes (30d)" value={s.minutes_30d} sub={`${s.tutor_questions} tutor questions`} />
          </div>
          <div className="grid-2">
            <div className="card"><h3>Daily learning minutes</h3><DailyChart daily={data.daily} /></div>
            <div className="card">
              <h3>Courses by enrolment</h3>
              <ul className="funnel">
                {data.top_courses.map((c) => (
                  <li key={c.id}>
                    <span className="f-title">{c.icon} {c.title}</span>
                    <div className="hbar"><div style={{ width: `${(c.learners / Math.max(1, data.top_courses[0].learners)) * 100}%` }} /></div>
                    <span className="num">{c.learners} <small className="muted">({c.completed} done)</small></span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}

      {tab === 'users' && (
        <div className="card scroll-x">
          <div className="row-between"><h3>Users</h3><input type="search" placeholder="Filter users…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter users" /></div>
          <table className="table">
            <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th><th>Data</th></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className={u.active ? '' : 'inactive'}>
                  <td>{u.display_name}</td>
                  <td className="muted small">{u.email}</td>
                  <td>
                    <select value={u.role} disabled={u.id === user.id} onChange={(e) => setUser(u.id, { role: e.target.value })} aria-label={`Role for ${u.display_name}`}>
                      <option value="learner">Learner</option><option value="instructor">Instructor</option><option value="admin">Admin</option>
                    </select>
                  </td>
                  <td>
                    {u.id === user.id ? <span className="muted small">You</span> : (
                      <button className="btn small ghost" onClick={() => setUser(u.id, { active: !u.active })}>{u.active ? 'Deactivate' : 'Reactivate'}</button>
                    )}
                  </td>
                  <td className="muted small">{fmtDate(u.created_at)}</td>
                  <td className="row-actions">
                    <button className="btn small ghost" onClick={async () => downloadJson(await api(`/users/${u.id}/export`), `user-${u.id}-data.json`)}>Export</button>
                    {u.role === 'learner' && <button className="btn small danger" onClick={() => erase(u)}>Erase</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'moderation' && (
        <div className="card">
          <h3>Moderation queue</h3>
          <p className="muted small">Raised automatically from tutor chats and discussions. Wellbeing concerns should be followed up by a person.</p>
          {data.flags.length ? (
            <table className="table">
              <thead><tr><th>When</th><th>User</th><th>Category</th><th>Where</th><th>Excerpt</th><th>Status</th></tr></thead>
              <tbody>{data.flags.map((f) => (
                <tr key={f.id}>
                  <td className="small">{timeAgo(f.created_at)}</td>
                  <td>{f.display_name}<small className="muted block">{f.email}</small></td>
                  <td><span className={`pill ${f.category === 'wellbeing' ? 'low' : 'mid'}`}>{f.category.replace('_', ' ')}</span></td>
                  <td className="small muted">{f.source}</td>
                  <td>"{f.excerpt}"</td>
                  <td>
                    <select value={f.status} onChange={async (e) => { await api(`/admin/flags/${f.id}`, { method: 'PUT', body: { status: e.target.value } }); load() }} aria-label="Flag status">
                      <option value="open">Open</option><option value="reviewing">Reviewing</option><option value="resolved">Resolved</option>
                    </select>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          ) : <p className="muted">Nothing flagged.</p>}
        </div>
      )}

      {tab === 'ai' && (
        <>
          <div className="card">
            <h3>AI tutor usage</h3>
            <p className="muted small">Active model: <strong>{data.llm.provider}</strong> ({data.llm.model}). Answers are checked for grounding in course content before learners see them.</p>
            <table className="table">
              <thead><tr><th>Provider</th><th>Model</th><th>Calls</th><th>Tokens in / out</th><th>Avg latency</th><th>Cost</th></tr></thead>
              <tbody>
                {data.ai_usage.map((a) => (
                  <tr key={a.provider + a.model}>
                    <td>{a.provider}</td><td>{a.model}</td><td>{a.calls}</td><td>{a.input_tokens} / {a.output_tokens}</td>
                    <td>{(a.avg_latency_ms / 1000).toFixed(1)} s</td>
                    <td>${a.cost_usd.toFixed(4)}{a.learners ? <small className="muted block">${(a.cost_usd / a.learners).toFixed(4)} per learner</small> : null}</td>
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
              <tbody>{data.audit.map((a) => (
                <tr key={a.id}><td className="small">{fmtDate(a.created_at, true)}</td><td>{a.display_name || 'system'} <small className="muted">{a.role || ''}</small></td><td><code>{a.action}</code></td><td className="muted small">{a.target}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
