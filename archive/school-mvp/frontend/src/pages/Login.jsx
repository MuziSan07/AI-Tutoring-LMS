import { useState } from 'react'
import { api } from '../api.js'

const DEMO = [
  { role: 'Student', email: 'amelia@demo.school', who: 'Amelia, Year 8 - returning learner' },
  { role: 'Parent', email: 'parent@demo.school', who: "Sarah - Amelia's parent" },
  { role: 'Teacher', email: 'teacher@demo.school', who: 'Mr Wright - 8M Maths' },
  { role: 'School admin', email: 'admin@demo.school', who: 'Oakfield Academy' },
  { role: 'Platform admin', email: 'super@demo.platform', who: 'All institutions' },
]

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e, demoEmail) {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const data = await api('/auth/login', { method: 'POST', body: { email: demoEmail || email, password: demoEmail ? 'demo1234' : password } })
      onLogin(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <div className="login-hero">
        <div className="brand big"><span className="logo">✦</span> Nova</div>
        <h1>A patient, personal maths tutor for every student.</h1>
        <p>Step-by-step teaching, an interactive whiteboard, voice conversation and a learning memory that picks up exactly where each student left off.</p>
        <ul className="hero-points">
          <li>Every answer checked by a maths engine, not guessed by AI</li>
          <li>Spots misconceptions and adapts the explanation</li>
          <li>Progress for students, parents, teachers and schools</li>
        </ul>
      </div>
      <div className="login-panel">
        <form className="card login-card" onSubmit={submit}>
          <h2>Sign in</h2>
          <label>Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required /></label>
          <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn wide" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        </form>
        <div className="card demo-card">
          <h3>Demo accounts</h3>
          <p className="muted small">Fictional test users. One click signs in.</p>
          {DEMO.map((d) => (
            <button key={d.email} className="demo-row" onClick={(e) => submit(e, d.email)} disabled={busy}>
              <strong>{d.role}</strong><span>{d.who}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
