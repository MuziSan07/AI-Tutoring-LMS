import { useEffect, useState } from 'react'
import { api, downloadJson } from '../api.js'
import { Loading } from '../components/ui.jsx'
import { PreferencesForm } from './Onboarding.jsx'

export default function Profile({ user, categories }) {
  const [profile, setProfile] = useState(null)
  const [saved, setSaved] = useState(false)
  useEffect(() => { api('/profile').then(setProfile) }, [])
  if (!profile) return <Loading />
  return (
    <div className="page narrow">
      <h1>Profile & preferences</h1>
      <p className="muted">{user.display_name} · {user.email}</p>
      <div className="card">
        <h2>How you like to learn</h2>
        <p className="muted small">Your AI tutor uses these settings to personalise explanations and recommendations.</p>
        <PreferencesForm initial={profile} categories={categories} submitLabel={saved ? 'Saved ✓' : 'Save preferences'}
          onSave={(p) => { setProfile(p); setSaved(true); setTimeout(() => setSaved(false), 2000) }} />
      </div>
      <div className="card">
        <h2>Your data</h2>
        <p className="muted">Download everything we hold about your learning - progress, quiz answers, notes and tutor conversations.</p>
        <button className="btn ghost" onClick={async () => downloadJson(await api(`/users/${user.id}/export`), 'my-nova-data.json')}>Download my data</button>
      </div>
    </div>
  )
}
