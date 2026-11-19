export const STATUS_CLASS = { Secure: 'secure', Developing: 'developing', Learning: 'learning', 'Not started': 'none' }

export function StatusPill({ status }) {
  return <span className={`pill ${STATUS_CLASS[status] || 'none'}`}>{status}</span>
}

export function MasteryBar({ p, status }) {
  return (
    <div className="mastery" title={`Mastery estimate ${Math.round(p * 100)}%`}>
      <div className={`fill ${STATUS_CLASS[status] || ''}`} style={{ width: `${Math.max(2, p * 100)}%` }} />
    </div>
  )
}

export function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}

export function fmtDate(iso, withTime = false) {
  if (!iso) return '-'
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}) })
}

export function relativeDue(iso) {
  if (!iso) return ''
  const today = new Date().toISOString().slice(0, 10)
  if (iso < today) return 'Overdue'
  if (iso === today) return 'Today'
  const days = Math.round((new Date(iso) - new Date(today)) / 86400000)
  return days === 1 ? 'Tomorrow' : `In ${days} days`
}

export function Loading({ text = 'Loading…' }) {
  return <div className="loading"><span className="spinner" />{text}</div>
}

export function ProgressProfile({ data, onOpenLesson }) {
  const { stats, topics, misconceptions, revision, lessons } = data
  return (
    <div className="profile">
      <div className="stats-row">
        <Stat label="Lessons" value={stats.lessons} />
        <Stat label="Minutes learning" value={stats.minutes} sub={`${stats.minutes_today} today`} />
        <Stat label="Accuracy" value={`${Math.round(stats.accuracy * 100)}%`} sub={`${stats.questions} questions`} />
        <Stat label="Topics secure" value={stats.secure} sub={`of ${topics.length}`} />
      </div>
      <div className="grid-2">
        <div className="card">
          <h3>Strengths</h3>
          {stats.strengths.length ? <ul className="tick-list">{stats.strengths.map((s) => <li key={s}>{s}</li>)}</ul> : <p className="muted">Building up evidence…</p>}
          <h3>Needs work</h3>
          {stats.weaknesses.length ? <ul className="dot-list">{stats.weaknesses.map((s) => <li key={s}>{s}</li>)}</ul> : <p className="muted">Nothing flagged.</p>}
          {misconceptions.length > 0 && (
            <>
              <h3>Common slips spotted</h3>
              <ul className="dot-list">{misconceptions.map((m) => <li key={m.topic_id + m.code}>Sometimes {m.description} <span className="muted">({m.count}×)</span></li>)}</ul>
            </>
          )}
        </div>
        <div className="card">
          <h3>Topic mastery</h3>
          <div className="topic-rows">
            {topics.map((t) => (
              <div key={t.id} className="topic-row">
                <span className="t-name">{t.title}</span>
                <MasteryBar p={t.p_mastery} status={t.status} />
                <StatusPill status={t.status} />
              </div>
            ))}
          </div>
          <p className="muted small">Mastery is estimated only from marked answers - never from a student saying they understand.</p>
        </div>
      </div>
      <div className="grid-2">
        <div className="card">
          <h3>Upcoming revision</h3>
          {revision.length ? (
            <ul className="plain-list">{revision.map((r) => <li key={r.topic_id}><span>{r.title}</span><span className={`due ${relativeDue(r.due) === 'Overdue' || relativeDue(r.due) === 'Today' ? 'now' : ''}`}>{relativeDue(r.due)}</span></li>)}</ul>
          ) : <p className="muted">No revision scheduled yet.</p>}
        </div>
        <div className="card">
          <h3>Recent lessons</h3>
          {lessons.length ? (
            <ul className="lesson-list">
              {lessons.slice(0, 6).map((l) => (
                <li key={l.id} onClick={onOpenLesson ? () => onOpenLesson(l.id) : undefined} className={onOpenLesson ? 'clickable' : ''}>
                  <div><strong>{l.title}</strong><span className="muted"> · {fmtDate(l.started_at)} · {Math.round(l.duration_seconds / 60)} min</span></div>
                  <p>{l.summary || (l.status === 'active' ? 'In progress' : '')}</p>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No lessons yet.</p>}
        </div>
      </div>
    </div>
  )
}
