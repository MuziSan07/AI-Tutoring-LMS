export function Loading({ text = 'Loading…' }) {
  return <div className="loading"><span className="spinner" />{text}</div>
}

export function ErrorBox({ error }) {
  return error ? <p className="error" role="alert">{error}</p> : null
}

export function Progress({ percent, small = false }) {
  return (
    <div className={`progress ${small ? 'small' : ''}`} role="progressbar" aria-valuenow={percent} aria-valuemin="0" aria-valuemax="100">
      <div style={{ width: `${Math.max(percent, 1)}%` }} />
    </div>
  )
}

export function Stars({ value, count }) {
  if (!value) return <span className="muted small">No ratings yet</span>
  return (
    <span className="stars" aria-label={`${value} out of 5 stars`}>
      <span className="star-fill">{'★'.repeat(Math.round(value))}</span>
      <span className="star-empty">{'★'.repeat(5 - Math.round(value))}</span>
      <strong> {value}</strong>{count !== undefined && <span className="muted"> ({count})</span>}
    </span>
  )
}

export function Stat({ label, value, sub }) {
  return (
    <div className="stat">
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  )
}

export function CourseCover({ course, size = 'md' }) {
  return (
    <div className={`cover cover-${size}`} style={{ '--c': course.colour }}>
      <span>{course.icon}</span>
    </div>
  )
}

export function CourseCard({ course, onOpen, footer }) {
  return (
    <button className="course-card" onClick={onOpen}>
      <CourseCover course={course} />
      <div className="course-card-body">
        <span className="eyebrow">{course.category} · {course.level}</span>
        <h3>{course.title}</h3>
        <p className="muted small clamp">{course.subtitle}</p>
        <div className="meta-row">
          <Stars value={course.rating} count={course.reviews} />
        </div>
        <p className="muted small">{course.lessons} lessons · {fmtMinutes(course.minutes)} · {course.learners} learners</p>
        {footer}
      </div>
    </button>
  )
}

export const MASTERY_CLASS = { Strong: 'good', Developing: 'mid', 'Needs work': 'low', 'Not started': 'none' }

export function MasteryPill({ status }) {
  return <span className={`pill ${MASTERY_CLASS[status] || 'none'}`}>{status}</span>
}

export const KIND_ICON = { article: '📄', video: '🎬', quiz: '✅', assignment: '📝' }

export function fmtMinutes(min) {
  if (!min) return '0 min'
  const h = Math.floor(min / 60)
  return h ? `${h}h ${min % 60 ? `${min % 60}m` : ''}`.trim() : `${min} min`
}

export function fmtDate(iso, withTime = false) {
  if (!iso) return '-'
  const d = new Date(iso.length === 10 ? iso + 'T00:00:00' : iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}) })
}

export function timeAgo(iso) {
  if (!iso) return 'never'
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 86400) return `${Math.round(s / 3600)} h ago`
  return `${Math.round(s / 86400)} d ago`
}
