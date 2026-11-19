import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Loading, MasteryBar, StatusPill, relativeDue } from '../components/ui.jsx'

const KIND_ICON = { resume: '▶️', revision: '🔁', assignment: '📝', misconception: '🎯', continue: '📈', new: '✨' }

export default function StudentHome({ user, onStart }) {
  const [data, setData] = useState(null)
  const [subjects, setSubjects] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api('/student/dashboard').then(setData).catch((e) => setError(e.message))
    api('/curriculum').then((c) => setSubjects(c.subjects)).catch(() => {})
  }, [])

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!data) return <Loading />
  const [next, ...others] = data.recommendations
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="page">
      <div className="welcome">
        <div>
          <h1>{greeting}, {user.display_name.split(' ')[0]} 👋</h1>
          <p className="muted">Year {user.year_group} · {data.stats.minutes_today} min learnt today · {data.stats.secure} topic{data.stats.secure === 1 ? '' : 's'} secure</p>
        </div>
      </div>

      {next && (
        <div className="up-next card">
          <div>
            <span className="eyebrow">{KIND_ICON[next.kind]} Up next for you</span>
            <h2>{next.title}</h2>
            <p>{next.reason}</p>
          </div>
          <button className="btn big" onClick={() => onStart(next.topic_id)}>Start lesson</button>
        </div>
      )}

      <div className="grid-3">
        <div className="card">
          <h3>Also recommended</h3>
          <ul className="rec-list">
            {others.map((r) => (
              <li key={r.topic_id}>
                <button onClick={() => onStart(r.topic_id)}>
                  <span className="rec-icon">{KIND_ICON[r.kind]}</span>
                  <span><strong>{r.title}</strong><small>{r.reason}</small></span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>Homework</h3>
          {data.assignments.length ? (
            <ul className="plain-list">
              {data.assignments.map((a) => (
                <li key={a.id}>
                  <span>{a.title}<small className="muted block">{a.note ? `${a.note} · ` : ''}from {a.teacher}</small></span>
                  <span className={`pill ${a.status === 'completed' ? 'secure' : 'developing'}`}>{a.status === 'completed' ? 'Done' : relativeDue(a.due_date)}</span>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No homework set.</p>}
        </div>
        <div className="card">
          <h3>Revision schedule</h3>
          <ul className="plain-list">
            {data.revision.slice(0, 5).map((r) => (
              <li key={r.topic_id}>
                <span>{r.title}</span>
                <span className={`due ${['Today', 'Overdue'].includes(relativeDue(r.due)) ? 'now' : ''}`}>{relativeDue(r.due)}</span>
              </li>
            ))}
            {!data.revision.length && <p className="muted">Finish a lesson to start your schedule.</p>}
          </ul>
        </div>
      </div>

      <h2 className="section-title">Subjects</h2>
      <div className="subjects">
        {subjects.map((s) => (
          <div key={s.id} className={`subject ${s.status}`}>
            <strong>{s.name}</strong>
            <span>{s.status === 'available' ? s.note : `Coming soon · ${s.note}`}</span>
          </div>
        ))}
      </div>

      <h2 className="section-title">Mathematics topics</h2>
      <div className="topics">
        {data.topics.map((t) => (
          <button key={t.id} className="topic-card" onClick={() => onStart(t.id)}>
            <div className="topic-top">
              <span className="eyebrow">{t.key_stage} · Year {t.year}</span>
              <StatusPill status={t.status} />
            </div>
            <h3>{t.title}</h3>
            <p className="muted small">{t.strand}</p>
            <MasteryBar p={t.p_mastery} status={t.status} />
            {t.prerequisites.length > 0 && <p className="muted small">Builds on: {t.prerequisites.map((p) => data.topics.find((x) => x.id === p)?.title).join(', ')}</p>}
          </button>
        ))}
      </div>
    </div>
  )
}
