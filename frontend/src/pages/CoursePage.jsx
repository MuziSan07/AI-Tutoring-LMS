import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { CourseCover, ErrorBox, KIND_ICON, Loading, Progress, Stars, fmtDate, fmtMinutes } from '../components/ui.jsx'

function ReviewForm({ course, onSaved }) {
  const [rating, setRating] = useState(course.my_review?.rating || 0)
  const [body, setBody] = useState(course.my_review?.body || '')
  const [msg, setMsg] = useState('')
  async function save(e) {
    e.preventDefault()
    await api(`/courses/${course.id}/review`, { method: 'POST', body: { rating, body } })
    setMsg('Thanks for your review!')
    onSaved()
  }
  return (
    <form className="review-form" onSubmit={save}>
      <div className="star-input" role="radiogroup" aria-label="Your rating">
        {[1, 2, 3, 4, 5].map((n) => (
          <button type="button" key={n} role="radio" aria-checked={rating === n} className={n <= rating ? 'on' : ''} onClick={() => setRating(n)}>★</button>
        ))}
      </div>
      <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="What did you think of this course?" rows={3} />
      <button className="btn small" disabled={!rating}>{course.my_review ? 'Update review' : 'Post review'}</button>
      {msg && <span className="ok small">{msg}</span>}
    </form>
  )
}

export default function CoursePage({ slug, go }) {
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(0)
  const load = () => api(`/courses/${slug}`).then(setC).catch((e) => setError(e.message))
  useEffect(() => { load() }, [slug])

  async function enrol() {
    try {
      const p = await api(`/courses/${c.id}/enrol`, { method: 'POST' })
      go(`/learn/${c.id}/${p.next_lesson_id || ''}`)
    } catch (e) {
      setError(e.message)
    }
  }

  if (error) return <div className="page"><ErrorBox error={error} /></div>
  if (!c) return <Loading />
  const start = () => (c.enrolled ? go(`/learn/${c.id}${c.progress.next_lesson_id ? `/${c.progress.next_lesson_id}` : ''}`) : enrol())

  return (
    <div className="course-page">
      <header className="course-hero" style={{ '--c': c.colour }}>
        <div className="page hero-inner">
          <div>
            <a href="#/catalogue" className="back-link">← Catalogue</a>
            <span className="eyebrow light">{c.category} · {c.level}</span>
            <h1>{c.title}</h1>
            <p className="lead">{c.subtitle}</p>
            <div className="hero-meta">
              <Stars value={c.rating} count={c.reviews} />
              <span>{c.learners} learners</span>
              <span>{c.lesson_count} lessons · {fmtMinutes(c.duration_min)}</span>
              {c.instructor && <span>By {c.instructor.display_name}</span>}
            </div>
          </div>
          <div className="enrol-box card">
            <CourseCover course={c} size="lg" />
            {c.enrolled ? (
              <>
                <div className="row-inline"><Progress percent={c.progress.percent} /><span className="pct">{c.progress.percent}%</span></div>
                <button className="btn wide big" onClick={start}>{c.progress.completed_at ? 'Review course' : 'Continue learning'}</button>
              </>
            ) : (
              <>
                <p className="price">Free</p>
                <button className="btn wide big" onClick={start}>Enrol now</button>
              </>
            )}
            <ul className="includes">
              <li>✦ Personal AI tutor in every lesson</li>
              <li>✅ Quizzes with instant feedback</li>
              <li>🏅 Certificate of completion</li>
            </ul>
          </div>
        </div>
      </header>

      <div className="page course-body">
        <section className="card">
          <h2>What you'll learn</h2>
          <ul className="outcomes">{c.outcomes.map((o) => <li key={o}>{o}</li>)}</ul>
        </section>
        <section className="card">
          <h2>About this course</h2>
          <p>{c.description}</p>
          {c.instructor && <p className="muted"><strong>{c.instructor.display_name}</strong> - {c.instructor.headline}</p>}
        </section>
        <section className="card">
          <h2>Curriculum</h2>
          {c.modules.map((m, i) => (
            <div key={m.id} className="accordion">
              <button className="acc-head" onClick={() => setOpen(open === i ? -1 : i)} aria-expanded={open === i}>
                <span>{open === i ? '▾' : '▸'} {m.title}</span>
                <span className="muted small">{m.lessons.length} lessons · {fmtMinutes(m.lessons.reduce((s, l) => s + l.duration_min, 0))}</span>
              </button>
              {open === i && (
                <ul className="acc-body">
                  {m.lessons.map((l) => (
                    <li key={l.id}>
                      <span>{KIND_ICON[l.kind]} {l.title}</span>
                      <span className="muted small">{l.status === 'completed' ? '✓ Done' : `${l.duration_min} min`}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </section>
        <section className="card">
          <h2>Reviews</h2>
          {c.enrolled && <ReviewForm course={c} onSaved={load} />}
          {c.review_list.length ? c.review_list.map((r, i) => (
            <div key={i} className="review">
              <div><strong>{r.display_name}</strong> <Stars value={r.rating} /> <span className="muted small">{fmtDate(r.created_at)}</span></div>
              {r.body && <p>{r.body}</p>}
            </div>
          )) : <p className="muted">No reviews yet.</p>}
        </section>
      </div>
    </div>
  )
}
