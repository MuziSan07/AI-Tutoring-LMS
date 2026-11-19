import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { CourseCover, ErrorBox, Loading, Stars, Stat, fmtDate, timeAgo } from '../components/ui.jsx'

export function StudioHome({ go }) {
  const [courses, setCourses] = useState(null)
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { api('/studio/courses').then(setCourses) }, [])

  async function create(e) {
    e.preventDefault()
    try {
      const { id } = await api('/studio/courses', { method: 'POST', body: { title } })
      go(`/studio/course/${id}`)
    } catch (err) {
      setError(err.message)
    }
  }
  if (!courses) return <Loading />
  const pending = courses.reduce((s, c) => s + c.pending, 0)
  return (
    <div className="page wide">
      <div className="page-head">
        <div><h1>Content studio</h1><p className="muted">Build, publish and improve the academy's courses.</p></div>
        <a className="btn ghost" href="#/studio/submissions">📝 Submissions to grade{pending ? ` (${pending})` : ''}</a>
      </div>
      <div className="stats-row">
        <Stat label="Published courses" value={courses.filter((c) => c.status === 'published').length} />
        <Stat label="Drafts" value={courses.filter((c) => c.status === 'draft').length} />
        <Stat label="Total enrolments" value={courses.reduce((s, c) => s + c.learners, 0)} />
        <Stat label="Awaiting grading" value={pending} />
      </div>
      <form className="card new-course" onSubmit={create}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New course title, e.g. Intro to AI Prompting" aria-label="New course title" required />
        <button className="btn">+ Create course</button>
        <ErrorBox error={error} />
      </form>
      <div className="card">
        <table className="table">
          <thead><tr><th>Course</th><th>Status</th><th>Learners</th><th>Completion</th><th>Rating</th><th>Updated</th><th /></tr></thead>
          <tbody>
            {courses.map((c) => (
              <tr key={c.id}>
                <td><span className="li-main"><CourseCover course={c} size="sm" /><strong>{c.title}</strong></span></td>
                <td><span className={`pill ${c.status === 'published' ? 'good' : 'mid'}`}>{c.status}</span></td>
                <td>{c.learners}</td>
                <td>{Math.round(c.completion_rate * 100)}%</td>
                <td><Stars value={c.rating} count={c.reviews} /></td>
                <td className="muted small">{timeAgo(c.updated_at)}</td>
                <td className="row-actions">
                  <button className="btn small ghost" onClick={() => go(`/studio/course/${c.id}`)}>Edit</button>
                  <button className="btn small ghost" onClick={() => go(`/studio/analytics/${c.id}`)}>Insights</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- course builder */

function QuizEditor({ quiz, onChange }) {
  const update = (i, patch) => onChange(quiz.map((q, k) => (k === i ? { ...q, ...patch } : q)))
  const add = (type) => onChange([...quiz, type === 'choice'
    ? { q: '', type, options: ['', ''], answer: 0, concept: '', explain: '' }
    : { q: '', type, accept: [''], tolerance: null, concept: '', explain: '' }])
  return (
    <div className="quiz-editor">
      {quiz.map((q, i) => (
        <div key={i} className="q-edit">
          <div className="row-between"><strong>Question {i + 1} · {q.type === 'choice' ? 'Multiple choice' : 'Short answer'}</strong>
            <button type="button" className="link danger-text" onClick={() => onChange(quiz.filter((_, k) => k !== i))}>Remove</button></div>
          <textarea rows={2} value={q.q} onChange={(e) => update(i, { q: e.target.value })} placeholder="Question text (markdown allowed)" />
          {q.type === 'choice' ? (
            <div className="opts-edit">
              {q.options.map((o, j) => (
                <div key={j} className="opt-row">
                  <input type="radio" name={`ans${i}`} checked={q.answer === j} onChange={() => update(i, { answer: j })} aria-label="Correct option" />
                  <input value={o} onChange={(e) => update(i, { options: q.options.map((x, k) => (k === j ? e.target.value : x)) })} placeholder={`Option ${'ABCDEFG'[j]}`} />
                  {q.options.length > 2 && <button type="button" className="link" onClick={() => update(i, { options: q.options.filter((_, k) => k !== j), answer: q.answer === j ? 0 : q.answer > j ? q.answer - 1 : q.answer })}>✕</button>}
                </div>
              ))}
              {q.options.length < 6 && <button type="button" className="link small" onClick={() => update(i, { options: [...q.options, ''] })}>+ Add option</button>}
              <p className="hint">Select the radio button next to the correct option.</p>
            </div>
          ) : (
            <label>Accepted answers (comma-separated)
              <input value={q.accept.join(', ')} onChange={(e) => update(i, { accept: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
            </label>
          )}
          <div className="grid-2 tight">
            <label>Concept it tests<input value={q.concept} onChange={(e) => update(i, { concept: e.target.value })} placeholder="e.g. loops" /></label>
            <label>Explanation shown after answering<input value={q.explain} onChange={(e) => update(i, { explain: e.target.value })} /></label>
          </div>
        </div>
      ))}
      <div className="row-actions">
        <button type="button" className="btn small ghost" onClick={() => add('choice')}>+ Multiple choice</button>
        <button type="button" className="btn small ghost" onClick={() => add('short')}>+ Short answer</button>
      </div>
    </div>
  )
}

function RubricEditor({ rubric, onChange }) {
  const update = (i, patch) => onChange(rubric.map((r, k) => (k === i ? { ...r, ...patch } : r)))
  return (
    <div className="rubric-editor">
      {rubric.map((r, i) => (
        <div key={i} className="q-edit">
          <div className="row-between"><strong>Criterion {i + 1}</strong><button type="button" className="link danger-text" onClick={() => onChange(rubric.filter((_, k) => k !== i))}>Remove</button></div>
          <input value={r.criterion} onChange={(e) => update(i, { criterion: e.target.value })} placeholder="e.g. Defines a function" />
          <div className="grid-2 tight">
            <label>Keywords for automated check<input value={r.keywords.join(', ')} onChange={(e) => update(i, { keywords: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} /></label>
            <label>Tip if missing<input value={r.tip} onChange={(e) => update(i, { tip: e.target.value })} /></label>
          </div>
        </div>
      ))}
      <button type="button" className="btn small ghost" onClick={() => onChange([...rubric, { criterion: '', keywords: [], tip: '' }])}>+ Add criterion</button>
    </div>
  )
}

function LessonEditor({ lesson, onSaved, onDelete }) {
  const [l, setL] = useState({ ...lesson, concepts: lesson.concepts.join(', ') })
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  useEffect(() => { setL({ ...lesson, concepts: lesson.concepts.join(', ') }); setMsg(''); setError('') }, [lesson.id])

  async function save(e) {
    e.preventDefault()
    setError('')
    try {
      await api(`/studio/lessons/${l.id}`, {
        method: 'PUT',
        body: {
          title: l.title, content_md: l.content_md, video_url: l.video_url || null, duration_min: Number(l.duration_min),
          concepts: l.concepts.split(',').map((s) => s.trim()).filter(Boolean),
          ...(l.kind === 'quiz' ? { quiz: l.quiz.map((q) => ({ ...q, concept: (q.concept || 'general').toLowerCase().replace(/\s+/g, '-') })) } : {}),
          ...(l.kind === 'assignment' ? { rubric: l.rubric } : {}),
        },
      })
      setMsg('Saved ✓')
      onSaved()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <form className="lesson-editor card" onSubmit={save}>
      <div className="row-between">
        <span className="pill none">{l.kind}</span>
        <button type="button" className="link danger-text" onClick={() => window.confirm(`Delete lesson "${l.title}"? Learner progress on it will be removed.`) && onDelete(l.id)}>Delete lesson</button>
      </div>
      <div className="grid-2 tight">
        <label>Title<input value={l.title} onChange={(e) => setL({ ...l, title: e.target.value })} /></label>
        <label>Duration (minutes)<input type="number" min="1" value={l.duration_min} onChange={(e) => setL({ ...l, duration_min: e.target.value })} /></label>
      </div>
      {l.kind === 'video' && <label>Video URL (YouTube, Vimeo or .mp4)<input value={l.video_url || ''} onChange={(e) => setL({ ...l, video_url: e.target.value })} /></label>}
      <label>{l.kind === 'quiz' ? 'Intro text' : l.kind === 'assignment' ? 'Assignment brief' : 'Lesson content'} (markdown)
        <textarea className="code-input" rows={l.kind === 'quiz' ? 3 : 14} value={l.content_md} onChange={(e) => setL({ ...l, content_md: e.target.value })} />
        {l.kind === 'article' && <span className="hint">Tip: add "## Example" and "## Key points" sections - the AI tutor uses them for "Explain simply" and "Example".</span>}
      </label>
      <label>Concepts taught (comma-separated)<input value={l.concepts} onChange={(e) => setL({ ...l, concepts: e.target.value })} placeholder="e.g. loops, functions" /></label>
      {l.kind === 'quiz' && <QuizEditor quiz={l.quiz || []} onChange={(quiz) => setL({ ...l, quiz })} />}
      {l.kind === 'assignment' && <RubricEditor rubric={l.rubric || []} onChange={(rubric) => setL({ ...l, rubric })} />}
      <ErrorBox error={error} />
      <div className="row-actions"><button className="btn">Save lesson</button><span className="ok small">{msg}</span></div>
    </form>
  )
}

export function CourseBuilder({ courseId, go }) {
  const [c, setC] = useState(null)
  const [selected, setSelected] = useState(null)
  const [details, setDetails] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')

  const load = () => api(`/studio/courses/${courseId}`).then((d) => {
    setC(d)
    setDetails((prev) => prev || { title: d.title, subtitle: d.subtitle || '', description: d.description || '', category: d.category, level: d.level, icon: d.icon, colour: d.colour, outcomes: d.outcomes.join('\n') })
  })
  useEffect(() => { load() }, [courseId])
  if (!c || !details) return <Loading />
  const lessons = c.modules.flatMap((m) => m.lessons)
  const current = lessons.find((l) => l.id === selected)

  const act = async (fn) => { setError(''); try { await fn(); await load() } catch (e) { setError(e.message) } }
  const saveDetails = (e) => {
    e.preventDefault()
    act(async () => {
      await api(`/studio/courses/${c.id}`, { method: 'PUT', body: { ...details, outcomes: details.outcomes.split('\n').map((s) => s.trim()).filter(Boolean) } })
      setMsg('Details saved ✓')
    })
  }
  const setStatus = (status) => act(() => api(`/studio/courses/${c.id}`, { method: 'PUT', body: { status } }))
  const addModule = () => { const t = window.prompt('Module title'); if (t) act(() => api(`/studio/courses/${c.id}/modules`, { method: 'POST', body: { title: t } })) }
  const renameModule = (m) => { const t = window.prompt('Module title', m.title); if (t) act(() => api(`/studio/modules/${m.id}`, { method: 'PUT', body: { title: t } })) }
  const deleteModule = (m) => window.confirm(`Delete module "${m.title}" and all its lessons?`) && act(() => api(`/studio/modules/${m.id}`, { method: 'DELETE' }))
  const addLesson = (m, kind) => act(async () => {
    const { id } = await api(`/studio/modules/${m.id}/lessons`, { method: 'POST', body: { title: `New ${kind}`, kind } })
    setSelected(id)
  })
  const move = (type, id, direction) => act(() => api('/studio/move', { method: 'POST', body: { type, id, direction } }))

  return (
    <div className="page wide builder">
      <div className="page-head">
        <div>
          <a href="#/studio" className="back-link">← Studio</a>
          <h1>{c.icon} {c.title}</h1>
          <span className={`pill ${c.status === 'published' ? 'good' : 'mid'}`}>{c.status}</span> <span className="muted small">version {c.version}</span>
        </div>
        <div className="row-actions">
          <a className="btn ghost" href={`#/course/${c.slug}`}>Preview</a>
          <button className="btn ghost" onClick={() => go(`/studio/analytics/${c.id}`)}>Insights</button>
          {c.status === 'published'
            ? <button className="btn ghost" onClick={() => setStatus('draft')}>Unpublish</button>
            : <button className="btn" onClick={() => setStatus('published')}>Publish</button>}
        </div>
      </div>
      <ErrorBox error={error} />
      <div className="builder-grid">
        <div className="builder-tree card">
          <h3>Curriculum</h3>
          {c.modules.map((m) => (
            <div key={m.id} className="tree-module">
              <div className="tree-row module">
                <strong>{m.title}</strong>
                <span className="tree-tools">
                  <button onClick={() => move('module', m.id, 'up')} aria-label="Move module up">↑</button>
                  <button onClick={() => move('module', m.id, 'down')} aria-label="Move module down">↓</button>
                  <button onClick={() => renameModule(m)} aria-label="Rename module">✎</button>
                  <button onClick={() => deleteModule(m)} aria-label="Delete module">🗑</button>
                </span>
              </div>
              {m.lessons.map((l) => (
                <div key={l.id} className={`tree-row ${selected === l.id ? 'on' : ''}`}>
                  <button className="tree-lesson" onClick={() => setSelected(l.id)}>{{ article: '📄', video: '🎬', quiz: '✅', assignment: '📝' }[l.kind]} {l.title}</button>
                  <span className="tree-tools">
                    <button onClick={() => move('lesson', l.id, 'up')} aria-label="Move lesson up">↑</button>
                    <button onClick={() => move('lesson', l.id, 'down')} aria-label="Move lesson down">↓</button>
                  </span>
                </div>
              ))}
              <select className="add-lesson" value="" onChange={(e) => e.target.value && addLesson(m, e.target.value)} aria-label="Add lesson">
                <option value="">+ Add lesson…</option><option value="article">Article</option><option value="video">Video</option>
                <option value="quiz">Quiz</option><option value="assignment">Assignment</option>
              </select>
            </div>
          ))}
          <button className="btn small ghost wide" onClick={addModule}>+ Add module</button>
        </div>
        <div>
          {current ? (
            <LessonEditor key={current.id} lesson={current} onSaved={load} onDelete={(id) => act(async () => { await api(`/studio/lessons/${id}`, { method: 'DELETE' }); setSelected(null) })} />
          ) : (
            <form className="card" onSubmit={saveDetails}>
              <h3>Course details</h3>
              <p className="muted small">Select a lesson on the left to edit it.</p>
              <div className="grid-2 tight">
                <label>Title<input value={details.title} onChange={(e) => setDetails({ ...details, title: e.target.value })} /></label>
                <label>Subtitle<input value={details.subtitle} onChange={(e) => setDetails({ ...details, subtitle: e.target.value })} /></label>
              </div>
              <label>Description<textarea rows={4} value={details.description} onChange={(e) => setDetails({ ...details, description: e.target.value })} /></label>
              <div className="grid-4">
                <label>Category<select value={details.category} onChange={(e) => setDetails({ ...details, category: e.target.value })}>{c.categories.map((x) => <option key={x}>{x}</option>)}</select></label>
                <label>Level<select value={details.level} onChange={(e) => setDetails({ ...details, level: e.target.value })}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
                <label>Icon<input value={details.icon} onChange={(e) => setDetails({ ...details, icon: e.target.value })} maxLength={4} /></label>
                <label>Colour<input type="color" value={details.colour} onChange={(e) => setDetails({ ...details, colour: e.target.value })} /></label>
              </div>
              <label>Learning outcomes (one per line)<textarea rows={5} value={details.outcomes} onChange={(e) => setDetails({ ...details, outcomes: e.target.value })} /></label>
              <div className="row-actions"><button className="btn">Save details</button><span className="ok small">{msg}</span></div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- analytics */

export function Analytics({ courseId, go }) {
  const [a, setA] = useState(null)
  useEffect(() => { api(`/studio/courses/${courseId}/analytics`).then(setA) }, [courseId])
  if (!a) return <Loading />
  const maxDone = Math.max(1, a.learners)
  return (
    <div className="page wide">
      <a href="#/studio" className="back-link">← Studio</a>
      <div className="page-head"><h1>Insights: {a.course.title}</h1><button className="btn ghost" onClick={() => go(`/studio/course/${courseId}`)}>Edit course</button></div>
      <div className="stats-row five">
        <Stat label="Learners" value={a.learners} />
        <Stat label="Active (7 days)" value={a.active_7d} />
        <Stat label="Average progress" value={`${a.avg_progress}%`} />
        <Stat label="Completed" value={a.completed} />
        <Stat label="Rating" value={a.rating ?? '-'} sub={`${a.reviews} reviews`} />
      </div>
      <div className="grid-2">
        <div className="card">
          <h3>Lesson completion funnel</h3>
          <p className="muted small">Where learners drop off.</p>
          <ul className="funnel">
            {a.funnel.map((f) => (
              <li key={f.lesson_id}>
                <span className="f-title">{f.title}</span>
                <div className="hbar"><div style={{ width: `${(f.completed / maxDone) * 100}%` }} /></div>
                <span className="num">{f.completed}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card">
          <h3>✦ What learners ask the AI tutor</h3>
          <p className="muted small">Recent questions (anonymised). Frequent questions point to lessons that need clearer content.</p>
          {a.tutor_questions.length ? <ul className="asked">{a.tutor_questions.map((t, i) => <li key={i}>"{t.text}" <span className="muted small">{timeAgo(t.created_at)}</span></li>)}</ul> : <p className="muted">No questions yet.</p>}
        </div>
      </div>
      <div className="grid-2">
        <div className="card">
          <h3>Hardest quiz questions</h3>
          <table className="table">
            <thead><tr><th>Question</th><th>Concept</th><th>Correct</th></tr></thead>
            <tbody>{a.hardest_questions.map((q, i) => (
              <tr key={i}><td>{q.q.split('\n')[0]}<small className="muted block">{q.lesson}</small></td><td>{q.concept}</td><td className={q.correct_rate < 0.5 ? 'danger-text' : ''}>{Math.round(q.correct_rate * 100)}% <small className="muted">({q.attempts})</small></td></tr>
            ))}</tbody>
          </table>
        </div>
        <div className="card">
          <h3>Concept mastery across learners</h3>
          <ul className="funnel">
            {a.concepts.map((cp) => (
              <li key={cp.concept}><span className="f-title">{cp.label}</span><div className="hbar"><div className={cp.p < 0.5 ? 'low' : ''} style={{ width: `${cp.p * 100}%` }} /></div><span className="num">{Math.round(cp.p * 100)}%</span></li>
            ))}
          </ul>
        </div>
      </div>
      <div className="grid-2">
        <div className="card">
          <h3>Learners</h3>
          <table className="table">
            <thead><tr><th>Name</th><th>Progress</th><th>Struggling with</th><th>Last active</th></tr></thead>
            <tbody>{a.roster.map((r) => (
              <tr key={r.user_id}><td>{r.name}{r.completed && ' 🏅'}</td><td>{r.percent}%</td><td className="small">{r.weak.join(', ') || '-'}</td><td className="muted small">{timeAgo(r.last_active)}</td></tr>
            ))}</tbody>
          </table>
        </div>
        <div className="card">
          <h3>Unanswered discussion questions</h3>
          {a.unanswered.length ? a.unanswered.map((d) => (
            <div key={d.id} className="post">
              <div className="post-head"><strong>{d.display_name}</strong><span className="muted small">{d.lesson} · {timeAgo(d.created_at)}</span></div>
              <p>{d.body}</p>
              <a className="link small" href={`#/learn/${courseId}/${d.lesson_id}`}>Reply in lesson →</a>
            </div>
          )) : <p className="muted">All caught up ✓</p>}
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- grading */

export function Submissions() {
  const [status, setStatus] = useState('submitted')
  const [rows, setRows] = useState(null)
  const [drafts, setDrafts] = useState({})
  const load = () => api(`/studio/submissions?status=${status}`).then(setRows)
  useEffect(() => { load() }, [status])

  async function grade(s) {
    const d = drafts[s.id] || {}
    await api(`/studio/submissions/${s.id}`, { method: 'PUT', body: { grade: d.grade || 'Pass', feedback: d.feedback || '' } })
    load()
  }
  if (!rows) return <Loading />
  return (
    <div className="page">
      <a href="#/studio" className="back-link">← Studio</a>
      <h1>Assignment submissions</h1>
      <div className="seg inline">
        <button className={status === 'submitted' ? 'on' : ''} onClick={() => setStatus('submitted')}>To grade</button>
        <button className={status === 'graded' ? 'on' : ''} onClick={() => setStatus('graded')}>Graded</button>
      </div>
      {rows.length === 0 && <p className="muted">Nothing here.</p>}
      {rows.map((s) => (
        <div key={s.id} className="card">
          <div className="row-between"><div><strong>{s.learner}</strong> · {s.course} · {s.lesson}</div><span className="muted small">{fmtDate(s.created_at, true)}</span></div>
          <pre className="submission">{s.body}</pre>
          <h4>Automated rubric check</h4>
          <ul className="rubric-check">{s.auto_feedback.map((f) => <li key={f.criterion} className={f.met ? 'met' : 'unmet'}>{f.met ? '✓' : '○'} {f.criterion}</li>)}</ul>
          {s.status === 'graded' ? (
            <p><span className="pill good">{s.grade}</span> {s.instructor_feedback}</p>
          ) : (
            <div className="grade-row">
              <select value={drafts[s.id]?.grade || 'Pass'} onChange={(e) => setDrafts({ ...drafts, [s.id]: { ...drafts[s.id], grade: e.target.value } })} aria-label="Grade">
                <option>Distinction</option><option>Merit</option><option>Pass</option><option>Resubmit</option>
              </select>
              <input placeholder="Feedback for the learner" value={drafts[s.id]?.feedback || ''} onChange={(e) => setDrafts({ ...drafts, [s.id]: { ...drafts[s.id], feedback: e.target.value } })} />
              <button className="btn" onClick={() => grade(s)}>Save grade</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
