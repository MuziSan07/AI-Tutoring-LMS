import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { LessonDetail } from './History.jsx'
import { Loading, ProgressProfile, fmtDate } from '../components/ui.jsx'

function heat(p) {
  if (p === undefined) return 'var(--cell-empty)'
  const hue = 8 + p * 128 // red -> green
  return `hsl(${hue} 70% ${88 - p * 18}%)`
}

function AssignForm({ cls, topics, onDone }) {
  const [topic, setTopic] = useState(topics[0]?.id)
  const [selected, setSelected] = useState(cls.students.map((s) => s.id))
  const [due, setDue] = useState(new Date(Date.now() + 7 * 86400000).toISOString().slice(0, 10))
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState('')
  async function submit(e) {
    e.preventDefault()
    const t = topics.find((x) => x.id === topic)
    const out = await api('/teacher/assign', { method: 'POST', body: { topic_id: topic, student_ids: selected, due_date: due, note: note || `Complete a lesson: ${t.title}` } })
    setMsg(`Assigned to ${out.assigned} student${out.assigned === 1 ? '' : 's'}.`)
    onDone()
  }
  const toggle = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  return (
    <form className="card" onSubmit={submit}>
      <h3>Assign a learning activity</h3>
      <label>Topic<select value={topic} onChange={(e) => setTopic(e.target.value)}>{topics.map((t) => <option key={t.id} value={t.id}>{t.title} ({t.key_stage})</option>)}</select></label>
      <div className="grid-2 tight">
        <label>Due date<input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></label>
        <label>Note (optional)<input value={note} onChange={(e) => setNote(e.target.value)} placeholder="e.g. Revise before Friday's quiz" /></label>
      </div>
      <div className="student-picks">
        <button type="button" className="chip" onClick={() => setSelected(selected.length ? [] : cls.students.map((s) => s.id))}>{selected.length ? 'Clear all' : 'Whole class'}</button>
        {cls.students.map((s) => (
          <label key={s.id} className={`chip ${selected.includes(s.id) ? 'on' : ''}`}><input type="checkbox" checked={selected.includes(s.id)} onChange={() => toggle(s.id)} />{s.display_name}</label>
        ))}
      </div>
      <button className="btn" disabled={!selected.length}>Assign</button>
      {msg && <p className="ok">{msg}</p>}
    </form>
  )
}

function StudentModal({ id, onClose }) {
  const [data, setData] = useState(null)
  const [lessonId, setLessonId] = useState(null)
  useEffect(() => { api(`/students/${id}/progress`).then(setData) }, [id])
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <button className="btn ghost close" onClick={onClose} aria-label="Close">✕</button>
        {lessonId ? <LessonDetail id={lessonId} onBack={() => setLessonId(null)} /> : !data ? <Loading /> : (
          <>
            <h2>{data.student.display_name}</h2>
            <p className="muted">Year {data.student.year_group} · ID {data.student.pseudonym_id}</p>
            <ProgressProfile data={data} onOpenLesson={setLessonId} />
          </>
        )}
      </div>
    </div>
  )
}

export default function Teacher() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(null)
  const load = () => api('/teacher/overview').then(setData)
  useEffect(() => { load() }, [])
  if (!data) return <Loading />
  return (
    <div className="page wide">
      {data.classes.map(({ class: cls, students, difficulties, exercise_results, assignments }) => (
        <div key={cls.id}>
          <h1>{cls.name}</h1>
          <p className="muted">{students.length} students · click a student for their full learning record</p>
          <div className="card scroll-x">
            <h3>Class mastery overview</h3>
            <table className="heatmap">
              <thead>
                <tr><th>Student</th>{data.topics.map((t) => <th key={t.id} title={t.title}><span>{t.title}</span></th>)}<th>Slips</th><th>Last active</th></tr>
              </thead>
              <tbody>
                {students.map((s) => (
                  <tr key={s.id}>
                    <td><button className="link" onClick={() => setOpen(s.id)}>{s.display_name}</button></td>
                    {data.topics.map((t) => {
                      const m = s.mastery[t.id]
                      return <td key={t.id} style={{ background: heat(m?.p) }} title={m ? `${m.status} (${Math.round(m.p * 100)}%)` : 'Not started'}>{m ? Math.round(m.p * 100) : ''}</td>
                    })}
                    <td>{s.open_misconceptions || ''}</td>
                    <td className="muted small">{fmtDate(s.last_active)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="muted small">Cells show the evidence-based mastery estimate (%). Empty means not started.</p>
          </div>
          <div className="grid-2">
            <div className="card">
              <h3>Common learning difficulties</h3>
              {difficulties.length ? (
                <ul className="difficulties">
                  {difficulties.map((d) => (
                    <li key={d.topic_id + d.code}>
                      <span className="count">{d.students}</span>
                      <div><strong>{d.description[0].toUpperCase() + d.description.slice(1)}</strong><small className="muted block">{d.topic} · {d.occurrences} occurrences</small></div>
                    </li>
                  ))}
                </ul>
              ) : <p className="muted">No open misconceptions.</p>}
            </div>
            <div className="card">
              <h3>Exercise results by topic</h3>
              <ul className="bars">
                {exercise_results.map((r) => (
                  <li key={r.topic_id}>
                    <span>{r.topic}</span>
                    <div className="hbar"><div style={{ width: `${r.accuracy * 100}%` }} /></div>
                    <span className="num">{Math.round(r.accuracy * 100)}% <small className="muted">({r.n})</small></span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="grid-2">
            <AssignForm cls={{ ...cls, students }} topics={data.topics} onDone={load} />
            <div className="card">
              <h3>Assigned activities</h3>
              <ul className="plain-list">
                {assignments.map((a) => (
                  <li key={a.id}><span>{a.student} · {a.topic}<small className="muted block">due {fmtDate(a.due_date)}</small></span>
                    <span className={`pill ${a.status === 'completed' ? 'secure' : 'developing'}`}>{a.status}</span></li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ))}
      {open && <StudentModal id={open} onClose={() => setOpen(null)} />}
    </div>
  )
}
