import { useEffect, useState } from 'react'
import { api } from '../api.js'
import MathTex from '../components/Math.jsx'
import { BoardOp } from '../components/Whiteboard.jsx'
import { Loading, fmtDate } from '../components/ui.jsx'

export function LessonDetail({ id, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api(`/lessons/${id}`).then(setData).catch((e) => setError(e.message)) }, [id])
  if (error) return <p className="error">{error}</p>
  if (!data) return <Loading />
  const { lesson, messages, attempts } = data
  return (
    <div className="page">
      <button className="btn ghost" onClick={onBack}>← All lessons</button>
      <h1>{lesson.title}</h1>
      <p className="muted">{fmtDate(lesson.started_at, true)} · {Math.round(lesson.duration_seconds / 60)} minutes · {lesson.status === 'active' ? 'In progress' : 'Completed'}</p>
      {lesson.summary && <div className="card summary-card"><strong>Summary saved to learning record</strong><p>{lesson.summary}</p></div>}
      <div className="grid-2">
        <div className="card">
          <h3>Answers</h3>
          {attempts.length ? (
            <table className="table">
              <thead><tr><th>Question</th><th>Answer</th><th>Result</th></tr></thead>
              <tbody>
                {attempts.map((a, i) => (
                  <tr key={i}>
                    <td>{a.question}</td>
                    <td><code>{a.answer}</code>{!a.correct && <span className="muted small block">Expected <MathTex tex={a.expected} /></span>}</td>
                    <td>
                      <span className={`pill ${a.correct ? 'secure' : 'learning'}`}>{a.correct ? 'Correct' : 'Not yet'}</span>
                      {a.misconception && <span className="muted small block">{a.misconception.replaceAll('_', ' ')}</span>}
                      {a.hints_used > 0 && <span className="muted small block">with support</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No answers recorded.</p>}
        </div>
        <div className="card">
          <h3>Saved whiteboard</h3>
          <div className="wb-content saved">
            {lesson.board_json.map((op, i) => <BoardOp key={i} op={op} />)}
          </div>
          {lesson.student_drawing && (
            <>
              <h3>Student's ink</h3>
              <img src={lesson.student_drawing} alt="Student whiteboard drawing" className="ink-preview" />
            </>
          )}
        </div>
      </div>
      {messages.length > 0 && (
        <div className="card">
          <h3>Transcript</h3>
          <div className="transcript">
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>{m.text}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function History({ openId, onOpen }) {
  const [data, setData] = useState(null)
  useEffect(() => { api('/student/dashboard').then(setData) }, [])
  if (openId) return <LessonDetail id={openId} onBack={() => onOpen(null)} />
  if (!data) return <Loading />
  return (
    <div className="page">
      <h1>Lesson history</h1>
      <p className="muted">Everything Nova has taught you is saved here, including the whiteboard and your answers.</p>
      <div className="card">
        <ul className="lesson-list">
          {data.lessons.map((l) => (
            <li key={l.id} className="clickable" onClick={() => onOpen(l.id)}>
              <div><strong>{l.title}</strong><span className="muted"> · {fmtDate(l.started_at, true)} · {Math.round(l.duration_seconds / 60)} min</span>
                {l.status === 'active' && <span className="pill developing">In progress</span>}</div>
              <p>{l.summary}</p>
            </li>
          ))}
          {!data.lessons.length && <p className="muted">No lessons yet.</p>}
        </ul>
      </div>
    </div>
  )
}
