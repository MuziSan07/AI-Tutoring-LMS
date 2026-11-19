import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { CourseCard, CourseCover, ErrorBox, Loading, Progress, Stat } from '../components/ui.jsx'

export default function LearnerHome({ user, go }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api('/learner/home').then(setData).catch((e) => setError(e.message)) }, [])
  if (error) return <div className="page"><ErrorBox error={error} /></div>
  if (!data) return <Loading />
  const [current, ...others] = data.in_progress
  const hour = new Date().getHours()
  const greet = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const weekPct = Math.min(100, Math.round((data.week_minutes / data.week_goal) * 100))

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{greet}, {user.display_name.split(' ')[0]} 👋</h1>
          <p className="muted">Goal: {data.profile.goal || 'not set'} · <a href="#/profile">edit preferences</a></p>
        </div>
      </div>

      <div className="stats-row">
        <Stat label="Day streak" value={`🔥 ${data.streak}`} sub={data.streak ? 'Keep it going!' : 'Learn today to start one'} />
        <div className="stat">
          <span className="stat-value">{data.week_minutes}<small>/{data.week_goal} min</small></span>
          <span className="stat-label">This week</span>
          <Progress percent={weekPct} small />
        </div>
        <Stat label="Courses in progress" value={data.in_progress.length} />
        <Stat label="Certificates" value={data.certificates} sub={<a href="#/learning">View all</a>} />
      </div>

      {current ? (
        <div className="continue card" style={{ '--c': current.colour }}>
          <CourseCover course={current} size="lg" />
          <div className="continue-body">
            <span className="eyebrow">Continue learning</span>
            <h2>{current.title}</h2>
            <p className="muted">Next: <strong>{current.progress.next_lesson_title || 'Course complete!'}</strong></p>
            <div className="row-inline"><Progress percent={current.progress.percent} /><span className="pct">{current.progress.percent}%</span></div>
            {current.weak.length > 0 && (
              <p className="tutor-tip">✦ <strong>Nova:</strong> {current.weak[0].label} needs a bit more practice - I'll quiz you on it in the lesson.</p>
            )}
          </div>
          <button className="btn big" onClick={() => go(`/learn/${current.id}${current.progress.next_lesson_id ? `/${current.progress.next_lesson_id}` : ''}`)}>Resume</button>
        </div>
      ) : (
        <div className="card empty-state">
          <h2>Start your first course</h2>
          <p className="muted">Pick something below - your AI tutor will be there in every lesson.</p>
          <button className="btn" onClick={() => go('/catalogue')}>Browse courses</button>
        </div>
      )}

      {(others.length > 0 || data.reviews_due.length > 0) && (
        <div className="grid-2">
          {others.length > 0 && (
            <div className="card">
              <h3>Also in progress</h3>
              <ul className="plain-list">
                {others.map((c) => (
                  <li key={c.id} className="clickable" onClick={() => go(`/learn/${c.id}${c.progress.next_lesson_id ? `/${c.progress.next_lesson_id}` : ''}`)}>
                    <span className="li-main"><span className="mini-icon">{c.icon}</span><span><strong>{c.title}</strong><small className="muted block">Next: {c.progress.next_lesson_title}</small></span></span>
                    <span className="pct">{c.progress.percent}%</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.reviews_due.length > 0 && (
            <div className="card">
              <h3>Due for review</h3>
              <p className="muted small">Spaced review keeps skills fresh. Open the course and tap <strong>Quiz me</strong>.</p>
              <ul className="plain-list">
                {data.reviews_due.map((r) => (
                  <li key={r.course_id + r.concept} className="clickable" onClick={() => go(`/learn/${r.course_id}`)}>
                    <span><strong>{r.label}</strong><small className="muted block">{r.course_title}</small></span>
                    <span className="pill low">Review</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {data.recommended.length > 0 && (
        <>
          <h2 className="section-title">Recommended for you</h2>
          <div className="course-grid">
            {data.recommended.map((c) => (
              <CourseCard key={c.id} course={c} onOpen={() => go(`/course/${c.slug}`)} footer={<p className="reason">✦ {c.reason}</p>} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
