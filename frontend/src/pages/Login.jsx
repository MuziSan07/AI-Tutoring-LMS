import { useState } from 'react'
import { api } from '../api.js'
import { ErrorBox } from '../components/ui.jsx'

const DEMO = [
  { role: 'Learner', email: 'aisha@learner.demo', who: 'Aisha - career changer, mid-way through Python' },
  { role: 'Instructor', email: 'daniel@academy.demo', who: 'Daniel - content team (Python & Data)' },
  { role: 'Admin', email: 'admin@academy.demo', who: 'Rachel - academy administrator' },
]

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('signin')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  async function submit(e, demoEmail) {
    e?.preventDefault()
    setBusy(true)
    setError('')
    try {
      const data = demoEmail
        ? await api('/auth/login', { method: 'POST', body: { email: demoEmail, password: 'demo1234' } })
        : mode === 'signin'
          ? await api('/auth/login', { method: 'POST', body: { email: form.email, password: form.password } })
          : await api('/auth/register', { method: 'POST', body: form })
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
        <div className="brand big"><span className="logo">✦</span> Nova Academy</div>
        <h1>Online courses with a personal AI tutor in every lesson.</h1>
        <p>Learn practical tech and business skills at your own pace. Nova learns how you like to learn, answers your questions from the course material and quizzes you on what you find hardest.</p>
        <ul className="hero-points">
          <li>Tutor answers grounded in the course - never made up</li>
          <li>Personal practice on your weakest topics</li>
          <li>Certificates you can share and verify</li>
        </ul>
      </div>
      <div className="login-panel">
        <form className="card login-card" onSubmit={submit}>
          <div className="seg" role="tablist">
            <button type="button" role="tab" aria-selected={mode === 'signin'} className={mode === 'signin' ? 'on' : ''} onClick={() => setMode('signin')}>Sign in</button>
            <button type="button" role="tab" aria-selected={mode === 'signup'} className={mode === 'signup' ? 'on' : ''} onClick={() => setMode('signup')}>Create account</button>
          </div>
          {mode === 'signup' && <label>Full name<input value={form.name} onChange={set('name')} autoComplete="name" required minLength={2} /></label>}
          <label>Email<input type="email" value={form.email} onChange={set('email')} autoComplete="username" required /></label>
          <label>Password<input type="password" value={form.password} onChange={set('password')} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 8 : 1} />
            {mode === 'signup' && <span className="hint">At least 8 characters</span>}
          </label>
          <ErrorBox error={error} />
          <button className="btn wide" disabled={busy}>{busy ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create free account'}</button>
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
