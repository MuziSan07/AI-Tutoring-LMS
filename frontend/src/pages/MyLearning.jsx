import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { CourseCard, Loading, Progress, fmtDate } from '../components/ui.jsx'

export default function MyLearning({ go }) {
  const [home, setHome] = useState(null)
  const [certs, setCerts] = useState(null)
  useEffect(() => {
    api('/learner/home').then(setHome)
    api('/learner/certificates').then(setCerts)
  }, [])
  if (!home || !certs) return <Loading />
  const open = (c) => go(`/learn/${c.id}${c.progress.next_lesson_id ? `/${c.progress.next_lesson_id}` : ''}`)
  return (
    <div className="page">
      <h1>My learning</h1>
      <h2 className="section-title">In progress</h2>
      {home.in_progress.length ? (
        <div className="course-grid">
          {home.in_progress.map((c) => (
            <CourseCard key={c.id} course={c} onOpen={() => open(c)}
              footer={<div className="enrolled-tag"><Progress percent={c.progress.percent} small /><span>{c.progress.percent}% · next: {c.progress.next_lesson_title}</span></div>} />
          ))}
        </div>
      ) : <p className="muted">Nothing in progress. <a href="#/catalogue">Find a course</a>.</p>}

      <h2 className="section-title">Completed</h2>
      {home.completed.length ? (
        <div className="course-grid">
          {home.completed.map((c) => <CourseCard key={c.id} course={c} onOpen={() => go(`/learn/${c.id}`)} footer={<span className="pill good">Completed</span>} />)}
        </div>
      ) : <p className="muted">No completed courses yet.</p>}

      <h2 className="section-title">Certificates</h2>
      {certs.length ? (
        <div className="cert-list">
          {certs.map((c) => (
            <a key={c.code} className="cert-tile" href={`#/certificate/${c.code}`} style={{ '--c': c.colour }}>
              <span className="cert-icon">🏅</span>
              <span><strong>{c.title}</strong><small className="block muted">Issued {fmtDate(c.issued_at)} · {c.code}</small></span>
            </a>
          ))}
        </div>
      ) : <p className="muted">Complete every lesson in a course to earn its certificate.</p>}
    </div>
  )
}
