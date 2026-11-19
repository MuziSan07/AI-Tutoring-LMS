import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import LessonView from '../components/LessonView.jsx'
import TutorPanel from '../components/TutorPanel.jsx'
import { ErrorBox, KIND_ICON, Loading, MasteryPill, Progress } from '../components/ui.jsx'

export default function Player({ courseId, lessonId, go }) {
  const [course, setCourse] = useState(null)
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [panel, setPanel] = useState(window.innerWidth > 1100 ? 'tutor' : null) // 'tutor' | 'outline' | null on mobile
  const [showSkills, setShowSkills] = useState(false)
  const started = useRef(Date.now())

  const loadCourse = useCallback(() => api(`/learn/${courseId}`).then(setCourse).catch((e) => setError(e.message)), [courseId])
  const loadLesson = useCallback((id) => api(`/lessons/${id}`).then(setLesson).catch((e) => setError(e.message)), [])

  useEffect(() => { loadCourse() }, [loadCourse])
  useEffect(() => {
    if (!course) return
    const id = lessonId || course.progress.next_lesson_id || course.progress.last_lesson_id || course.modules[0]?.lessons[0]?.id
    if (!lessonId && id) return go(`/learn/${courseId}/${id}`)
    if (id) loadLesson(id)
    window.scrollTo(0, 0)
  }, [course?.id, lessonId])

  // study-time heartbeat (feeds streaks, weekly goal and analytics)
  useEffect(() => {
    if (!lesson) return
    started.current = Date.now()
    const send = () => {
      const secs = Math.round((Date.now() - started.current) / 1000)
      started.current = Date.now()
      if (secs > 3 && !document.hidden) api(`/lessons/${lesson.id}/heartbeat`, { method: 'POST', body: { seconds: secs } }).catch(() => {})
    }
    const t = setInterval(send, 30000)
    return () => { clearInterval(t); send() }
  }, [lesson?.id])

  function onComplete() {
    loadCourse()
    loadLesson(lesson.id)
  }

  if (error) return <div className="page"><ErrorBox error={error} /><a href="#/">Back home</a></div>
  if (!course) return <Loading />

  const outline = (
    <nav className="outline" aria-label="Course outline">
      <div className="outline-head">
        <a href={`#/course/${course.slug}`} className="back-link">← Course page</a>
        <h2>{course.icon} {course.title}</h2>
        <div className="row-inline"><Progress percent={course.progress.percent} small /><span className="pct">{course.progress.percent}%</span></div>
        {course.certificate && <a className="btn small wide" href={`#/certificate/${course.certificate}`}>🏅 View certificate</a>}
      </div>
      {course.modules.map((m) => (
        <div key={m.id} className="outline-module">
          <h4>{m.title}</h4>
          <ul>
            {m.lessons.map((l) => (
              <li key={l.id}>
                <a href={`#/learn/${course.id}/${l.id}`} className={`${l.id === lesson?.id ? 'current' : ''} ${l.status}`} onClick={() => window.innerWidth <= 1100 && setPanel(null)}>
                  <span className="status-dot">{l.status === 'completed' ? '✓' : KIND_ICON[l.kind]}</span>
                  <span>{l.title}</span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className="skills">
        <button className="link" onClick={() => setShowSkills(!showSkills)}>{showSkills ? '▾' : '▸'} My skills in this course</button>
        {showSkills && (
          <ul>
            {course.concepts.map((c) => (
              <li key={c.concept}><span>{c.label}</span><MasteryPill status={c.status} /></li>
            ))}
          </ul>
        )}
      </div>
    </nav>
  )

  return (
    <div className={`player ${panel === 'tutor' ? 'with-tutor' : ''}`}>
      <div className="player-bar">
        <button className="chip" onClick={() => setPanel(panel === 'outline' ? null : 'outline')}>☰ Outline</button>
        <button className={`chip ${panel === 'tutor' ? 'on' : ''}`} onClick={() => setPanel(panel === 'tutor' ? null : 'tutor')}>✦ AI tutor</button>
      </div>
      <div className={`player-outline ${panel === 'outline' ? 'open' : ''}`}>{outline}</div>
      <main className="player-main">{lesson ? <LessonView lesson={lesson} onChanged={() => loadLesson(lesson.id)} onComplete={onComplete} /> : <Loading />}</main>
      {panel === 'tutor' && (
        <div className="player-tutor">
          <TutorPanel key={course.id} courseId={course.id} lessonId={lesson?.id} profile={course.profile} onClose={() => setPanel(null)} />
        </div>
      )}
      {panel !== 'tutor' && <button className="tutor-fab" onClick={() => setPanel('tutor')} aria-label="Open AI tutor">✦ Ask Nova</button>}
    </div>
  )
}
