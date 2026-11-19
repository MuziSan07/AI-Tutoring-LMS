import { useState } from 'react'
import { api } from '../api.js'
import { ErrorBox } from '../components/ui.jsx'

export const GOALS = ['Change career into tech', 'Get promoted', 'Start a business', 'Learn for fun']
export const STYLES = [
  { id: 'examples', label: 'Show me examples', desc: 'Real-world examples first, then the theory' },
  { id: 'step-by-step', label: 'Step by step', desc: 'Break things into small numbered steps' },
  { id: 'concise', label: 'Keep it short', desc: 'Just the key idea, quickly' },
]
export const LEVELS = [
  { id: 'beginner', label: 'New to this' },
  { id: 'intermediate', label: 'Some experience' },
  { id: 'advanced', label: 'Experienced' },
]

// Shared by onboarding and the profile page.
export function PreferencesForm({ initial, categories, onSave, submitLabel }) {
  const [p, setP] = useState({
    goal: initial.goal || GOALS[0], experience: initial.experience || 'beginner', interests: initial.interests || [],
    style: initial.style || 'examples', weekly_goal_minutes: initial.weekly_goal_minutes || 120,
    voice_enabled: initial.voice_enabled ?? true, avatar_enabled: initial.avatar_enabled ?? true,
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toggle = (c) => setP({ ...p, interests: p.interests.includes(c) ? p.interests.filter((x) => x !== c) : [...p.interests, c] })

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      onSave(await api('/profile', { method: 'PUT', body: { ...p, voice_enabled: !!p.voice_enabled, avatar_enabled: !!p.avatar_enabled } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save} className="prefs">
      <fieldset>
        <legend>What's your main goal?</legend>
        <div className="choice-grid">
          {GOALS.map((g) => <button type="button" key={g} className={`choice ${p.goal === g ? 'on' : ''}`} aria-pressed={p.goal === g} onClick={() => setP({ ...p, goal: g })}>{g}</button>)}
        </div>
      </fieldset>
      <fieldset>
        <legend>What would you like to learn?</legend>
        <div className="choice-grid">
          {categories.map((c) => <button type="button" key={c} className={`choice ${p.interests.includes(c) ? 'on' : ''}`} aria-pressed={p.interests.includes(c)} onClick={() => toggle(c)}>{c}</button>)}
        </div>
      </fieldset>
      <fieldset>
        <legend>Your experience</legend>
        <div className="choice-grid">
          {LEVELS.map((l) => <button type="button" key={l.id} className={`choice ${p.experience === l.id ? 'on' : ''}`} aria-pressed={p.experience === l.id} onClick={() => setP({ ...p, experience: l.id })}>{l.label}</button>)}
        </div>
      </fieldset>
      <fieldset>
        <legend>How should your AI tutor explain things?</legend>
        <div className="choice-grid">
          {STYLES.map((s) => (
            <button type="button" key={s.id} className={`choice tall ${p.style === s.id ? 'on' : ''}`} aria-pressed={p.style === s.id} onClick={() => setP({ ...p, style: s.id })}>
              <strong>{s.label}</strong><span>{s.desc}</span>
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>Weekly learning goal: <strong>{p.weekly_goal_minutes} minutes</strong></legend>
        <input type="range" min="30" max="600" step="30" value={p.weekly_goal_minutes} onChange={(e) => setP({ ...p, weekly_goal_minutes: Number(e.target.value) })} aria-label="Weekly learning goal in minutes" />
      </fieldset>
      <fieldset className="checks">
        <label className="check"><input type="checkbox" checked={!!p.voice_enabled} onChange={(e) => setP({ ...p, voice_enabled: e.target.checked })} /> Let the tutor read answers aloud</label>
        <label className="check"><input type="checkbox" checked={!!p.avatar_enabled} onChange={(e) => setP({ ...p, avatar_enabled: e.target.checked })} /> Show the animated tutor avatar</label>
      </fieldset>
      <ErrorBox error={error} />
      <button className="btn big" disabled={busy}>{busy ? 'Saving…' : submitLabel}</button>
    </form>
  )
}

export default function Onboarding({ user, categories, onDone }) {
  return (
    <div className="page narrow onboarding">
      <span className="eyebrow">Welcome, {user.display_name.split(' ')[0]}</span>
      <h1>Let's personalise your learning</h1>
      <p className="muted">Your AI tutor uses this to recommend courses and explain things the way that works for you. You can change it any time.</p>
      <div className="card"><PreferencesForm initial={{}} categories={categories} onSave={onDone} submitLabel="Start learning" /></div>
    </div>
  )
}
