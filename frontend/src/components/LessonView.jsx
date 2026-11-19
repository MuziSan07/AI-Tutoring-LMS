import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Markdown from './Markdown.jsx'
import { ErrorBox, fmtDate, timeAgo } from './ui.jsx'

function videoEmbed(url) {
  const yt = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([\w-]{6,})/)
  if (yt) return <iframe src={`https://www.youtube-nocookie.com/embed/${yt[1]}`} title="Lesson video" allowFullScreen />
  const vimeo = url.match(/vimeo\.com\/(\d+)/)
  if (vimeo) return <iframe src={`https://player.vimeo.com/video/${vimeo[1]}`} title="Lesson video" allowFullScreen />
  return <video src={url} controls />
}

function Quiz({ lesson, onResult }) {
  const [answers, setAnswers] = useState(() => lesson.quiz.map(() => ''))
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const last = lesson.last_attempt

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      const r = await api(`/lessons/${lesson.id}/quiz`, { method: 'POST', body: { answers } })
      setResult(r)
      onResult(r)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const shown = result
  return (
    <form onSubmit={submit} className="quiz">
      {last && !shown && (
        <p className={`banner ${last.passed ? 'good' : 'low'}`}>
          Last attempt: {Math.round(last.score * 100)}% {last.passed ? '- passed ✓' : '- not passed yet'} ({fmtDate(last.created_at)}). You can retake it any time.
        </p>
      )}
      {lesson.quiz.map((q, i) => {
        const r = shown?.results[i]
        return (
          <fieldset key={i} className={`question ${r ? (r.correct ? 'right' : 'wrong') : ''}`} disabled={!!shown}>
            <legend><span className="qn">{i + 1}</span><Markdown text={q.q} className="inline" /></legend>
            {q.type === 'choice' ? (
              <div className="options">
                {q.options.map((opt, j) => (
                  <label key={j} className={`option ${String(answers[i]) === String(j) ? 'on' : ''}`}>
                    <input type="radio" name={`q${i}`} checked={String(answers[i]) === String(j)} onChange={() => setAnswers(answers.map((a, k) => (k === i ? j : a)))} />
                    <Markdown text={opt} className="inline" />
                  </label>
                ))}
              </div>
            ) : (
              <input className="short" value={answers[i]} onChange={(e) => setAnswers(answers.map((a, k) => (k === i ? e.target.value : a)))} placeholder="Your answer" aria-label={`Answer to question ${i + 1}`} />
            )}
            {r && (
              <div className="feedback">
                <strong>{r.correct ? '✓ Correct' : `✗ Answer: ${r.answer}`}</strong>
                <span>{r.explain}</span>
              </div>
            )}
          </fieldset>
        )
      })}
      <ErrorBox error={error} />
      {shown ? (
        <div className={`result-card ${shown.passed ? 'good' : 'low'}`}>
          <h3>{shown.passed ? '🎉 Passed!' : 'Not quite yet'} - {Math.round(shown.score * 100)}%</h3>
          <p>{shown.passed ? 'Great work. This lesson is complete.' : `You need ${Math.round(shown.pass_mark * 100)}% to pass.`}</p>
          {shown.revisit.length > 0 && (
            <p>✦ <strong>Nova suggests:</strong> revisit {shown.revisit.map((w) => <a key={w.concept} href={`#/learn/${lesson.course_id}/${w.lesson_id}`}>{w.lesson_title}</a>).reduce((a, b) => [a, ', ', b])} or ask the tutor to quiz you on {shown.revisit.map((w) => w.label).join(', ')}.</p>
          )}
          <button type="button" className="btn ghost" onClick={() => { setResult(null); setAnswers(lesson.quiz.map(() => '')) }}>Retake quiz</button>
        </div>
      ) : (
        <button className="btn big" disabled={busy || answers.some((a) => a === '')}>{busy ? 'Marking…' : 'Submit answers'}</button>
      )}
    </form>
  )
}

function Assignment({ lesson, onResult }) {
  const [body, setBody] = useState('')
  const [sub, setSub] = useState(lesson.submission)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(!lesson.submission)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    const r = await api(`/lessons/${lesson.id}/submit`, { method: 'POST', body: { body } })
    setSub({ body, auto_feedback: r.auto_feedback, status: 'submitted', created_at: new Date().toISOString() })
    setEditing(false)
    setBusy(false)
    onResult(r)
  }

  return (
    <div className="assignment">
      {lesson.rubric.length > 0 && (
        <div className="rubric"><strong>You'll be assessed on:</strong><ul>{lesson.rubric.map((r) => <li key={r.criterion}>{r.criterion}</li>)}</ul></div>
      )}
      {sub && !editing && (
        <div className="card inset">
          <div className="row-between">
            <h3>Your submission</h3>
            <span className={`pill ${sub.status === 'graded' ? 'good' : 'mid'}`}>{sub.status === 'graded' ? `Graded: ${sub.grade}` : 'Awaiting instructor review'}</span>
          </div>
          <pre className="submission">{sub.body}</pre>
          <h4>Automated rubric check</h4>
          <ul className="rubric-check">
            {sub.auto_feedback.map((f) => <li key={f.criterion} className={f.met ? 'met' : 'unmet'}>{f.met ? '✓' : '○'} {f.criterion}{!f.met && <small> - {f.tip}</small>}</li>)}
          </ul>
          {sub.instructor_feedback && <div className="instructor-fb"><strong>Instructor feedback</strong><p>{sub.instructor_feedback}</p></div>}
          <button className="btn ghost small" onClick={() => { setBody(sub.body); setEditing(true) }}>Submit a new version</button>
        </div>
      )}
      {editing && (
        <form onSubmit={submit}>
          <textarea className="code-input" rows={12} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Write or paste your answer here…" />
          <button className="btn" disabled={busy || body.trim().length < 20}>{busy ? 'Submitting…' : 'Submit assignment'}</button>
        </form>
      )}
    </div>
  )
}

function Discussion({ lesson, onPosted }) {
  const [body, setBody] = useState('')
  const [replyTo, setReplyTo] = useState(null)
  const [error, setError] = useState('')
  const top = lesson.discussion.filter((d) => !d.parent_id)
  const replies = (id) => lesson.discussion.filter((d) => d.parent_id === id)

  async function post(e) {
    e.preventDefault()
    setError('')
    try {
      await api(`/lessons/${lesson.id}/discussion`, { method: 'POST', body: { body, parent_id: replyTo } })
      setBody('')
      setReplyTo(null)
      onPosted()
    } catch (err) {
      setError(err.message)
    }
  }

  const Post = ({ p }) => (
    <div className={`post ${p.role !== 'learner' ? 'staff' : ''}`}>
      <div className="post-head"><strong>{p.display_name}</strong>{p.role !== 'learner' && <span className="pill good">Course team</span>}<span className="muted small">{timeAgo(p.created_at)}</span></div>
      <p>{p.body}</p>
    </div>
  )

  return (
    <div className="discussion">
      {top.length === 0 && <p className="muted">No questions yet. Ask the community - or try the AI tutor first for an instant answer.</p>}
      {top.map((p) => (
        <div key={p.id} className="thread">
          <Post p={p} />
          <div className="replies">{replies(p.id).map((r) => <Post key={r.id} p={r} />)}</div>
          <button className="link small" onClick={() => setReplyTo(p.id)}>Reply</button>
        </div>
      ))}
      <form onSubmit={post} className="post-form">
        {replyTo && <p className="small muted">Replying to a thread · <button type="button" className="link" onClick={() => setReplyTo(null)}>cancel</button></p>}
        <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Ask a question or share a tip…" />
        <ErrorBox error={error} />
        <button className="btn small" disabled={!body.trim()}>Post</button>
      </form>
    </div>
  )
}

function Notes({ lesson }) {
  const [body, setBody] = useState(lesson.note)
  const [saved, setSaved] = useState('')
  const timer = useRef(null)
  function change(v) {
    setBody(v)
    setSaved('Saving…')
    clearTimeout(timer.current)
    timer.current = setTimeout(async () => {
      if (v.trim()) await api(`/lessons/${lesson.id}/note`, { method: 'PUT', body: { body: v } })
      setSaved('Saved')
    }, 700)
  }
  return (
    <div className="notes">
      <textarea rows={8} value={body} onChange={(e) => change(e.target.value)} placeholder="Private notes for this lesson - only you can see them." />
      <span className="muted small">{saved}</span>
    </div>
  )
}

export default function LessonView({ lesson, onChanged, onComplete }) {
  const [tab, setTab] = useState('notes')
  const [completing, setCompleting] = useState(false)
  const [flash, setFlash] = useState(null)

  async function markComplete() {
    setCompleting(true)
    const r = await api(`/lessons/${lesson.id}/complete`, { method: 'POST' })
    setCompleting(false)
    onComplete(r)
  }
  function onResult(r) {
    if (r.certificate) setFlash(r.certificate)
    onComplete(r)
  }

  return (
    <article className="lesson">
      <span className="eyebrow">{lesson.module_title} · Lesson {lesson.position} of {lesson.total}</span>
      <h1>{lesson.title}</h1>
      {lesson.concepts.length > 0 && <div className="concept-tags">{lesson.concepts.map((c) => <span key={c.concept} className="tag">{c.label}</span>)}</div>}

      {flash && (
        <div className="banner good big">🏅 Course complete! Your certificate is ready: <a href={`#/certificate/${flash.code}`}>view certificate {flash.code}</a></div>
      )}

      {lesson.kind === 'video' && (lesson.video_url ? <div className="video">{videoEmbed(lesson.video_url)}</div> : <p className="banner mid">Video coming soon.</p>)}
      {lesson.content_md && <Markdown text={lesson.content_md} className="lesson-body" />}
      {lesson.kind === 'quiz' && <Quiz key={lesson.id} lesson={lesson} onResult={onResult} />}
      {lesson.kind === 'assignment' && <Assignment key={lesson.id} lesson={lesson} onResult={onResult} />}

      <div className="lesson-actions">
        {lesson.prev_id ? <a className="btn ghost" href={`#/learn/${lesson.course_id}/${lesson.prev_id}`}>← Previous</a> : <span />}
        {['article', 'video'].includes(lesson.kind) && lesson.status !== 'completed' && (
          <button className="btn" onClick={markComplete} disabled={completing}>✓ Mark as complete</button>
        )}
        {lesson.status === 'completed' && <span className="done-tag">✓ Completed</span>}
        {lesson.next_id ? <a className="btn ghost" href={`#/learn/${lesson.course_id}/${lesson.next_id}`}>Next →</a> : <span />}
      </div>

      <div className="lesson-extras card">
        <div className="tabs" role="tablist">
          <button role="tab" aria-selected={tab === 'notes'} className={tab === 'notes' ? 'on' : ''} onClick={() => setTab('notes')}>My notes</button>
          <button role="tab" aria-selected={tab === 'discussion'} className={tab === 'discussion' ? 'on' : ''} onClick={() => setTab('discussion')}>
            Discussion{lesson.discussion.length ? ` (${lesson.discussion.length})` : ''}
          </button>
        </div>
        {tab === 'notes' ? <Notes key={lesson.id} lesson={lesson} /> : <Discussion lesson={lesson} onPosted={onChanged} />}
      </div>
    </article>
  )
}
