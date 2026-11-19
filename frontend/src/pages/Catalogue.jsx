import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { CourseCard, ErrorBox, Loading, Progress } from '../components/ui.jsx'

export default function Catalogue({ categories, go }) {
  const [q, setQ] = useState('')
  const [category, setCategory] = useState('')
  const [level, setLevel] = useState('')
  const [courses, setCourses] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const t = setTimeout(() => {
      const params = new URLSearchParams({ q, category, level })
      api(`/courses?${params}`).then(setCourses).catch((e) => setError(e.message))
    }, 200)
    return () => clearTimeout(t)
  }, [q, category, level])

  return (
    <div className="page">
      <h1>Course catalogue</h1>
      <p className="muted">Every course is free and comes with a personal AI tutor.</p>
      <div className="filters">
        <input type="search" placeholder="Search courses…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search courses" />
        <div className="chips">
          <button className={`chip ${!category ? 'on' : ''}`} onClick={() => setCategory('')}>All</button>
          {categories.map((c) => <button key={c} className={`chip ${category === c ? 'on' : ''}`} onClick={() => setCategory(c)}>{c}</button>)}
        </div>
        <select value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Level">
          <option value="">All levels</option><option>Beginner</option><option>Intermediate</option><option>Advanced</option>
        </select>
      </div>
      <ErrorBox error={error} />
      {!courses ? <Loading /> : courses.length === 0 ? <p className="muted">No courses match your search.</p> : (
        <div className="course-grid">
          {courses.map((c) => (
            <CourseCard key={c.id} course={c} onOpen={() => go(`/course/${c.slug}`)}
              footer={c.enrolled ? <div className="enrolled-tag"><Progress percent={c.progress.percent} small /><span>{c.progress.percent}% complete</span></div> : null} />
          ))}
        </div>
      )}
    </div>
  )
}
