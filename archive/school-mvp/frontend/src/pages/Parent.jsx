import { useEffect, useState } from 'react'
import { api, downloadJson } from '../api.js'
import { LessonDetail } from './History.jsx'
import { Loading, ProgressProfile } from '../components/ui.jsx'

function UsageControls({ child, onSaved }) {
  const [s, setS] = useState(child.settings)
  const [saved, setSaved] = useState(false)
  async function save() {
    const out = await api(`/parent/settings/${child.student.id}`, {
      method: 'PUT',
      body: { daily_limit_minutes: Number(s.daily_limit_minutes), voice_enabled: !!s.voice_enabled, avatar_enabled: !!s.avatar_enabled },
    })
    setS(out)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
    onSaved?.()
  }
  return (
    <div className="card">
      <h3>Usage controls</h3>
      <label className="row-label">Daily learning limit: <strong>{s.daily_limit_minutes ? `${s.daily_limit_minutes} min` : 'No limit'}</strong>
        <input type="range" min="0" max="180" step="15" value={s.daily_limit_minutes} onChange={(e) => setS({ ...s, daily_limit_minutes: e.target.value })} />
      </label>
      <label className="check"><input type="checkbox" checked={!!s.voice_enabled} onChange={(e) => setS({ ...s, voice_enabled: e.target.checked })} /> Allow voice conversation</label>
      <label className="check"><input type="checkbox" checked={!!s.avatar_enabled} onChange={(e) => setS({ ...s, avatar_enabled: e.target.checked })} /> Show animated tutor avatar</label>
      <div className="row-actions">
        <button className="btn" onClick={save}>{saved ? 'Saved ✓' : 'Save controls'}</button>
        <button className="btn ghost" onClick={async () => downloadJson(await api(`/students/${child.student.id}/export`), `learning-record-${child.student.pseudonym_id}.json`)}>
          Download learning record
        </button>
      </div>
      <p className="muted small">Today: {child.stats.minutes_today} minutes used.</p>
    </div>
  )
}

export default function Parent() {
  const [data, setData] = useState(null)
  const [lessonId, setLessonId] = useState(null)
  useEffect(() => { api('/parent/overview').then(setData) }, [])
  if (lessonId) return <LessonDetail id={lessonId} onBack={() => setLessonId(null)} />
  if (!data) return <Loading />
  return (
    <div className="page">
      {data.children.map((child) => (
        <div key={child.student.id}>
          <h1>{child.student.display_name}'s learning</h1>
          <p className="muted">Year {child.student.year_group} · Mathematics</p>
          <ProgressProfile data={child} onOpenLesson={setLessonId} />
          <UsageControls child={child} />
        </div>
      ))}
    </div>
  )
}
