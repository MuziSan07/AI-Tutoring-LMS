import { useEffect, useState } from 'react'
import { api, loadSession, saveSession, setToken } from './api.js'
import Admin from './pages/Admin.jsx'
import Catalogue from './pages/Catalogue.jsx'
import Certificate from './pages/Certificate.jsx'
import CoursePage from './pages/CoursePage.jsx'
import LearnerHome from './pages/LearnerHome.jsx'
import Login from './pages/Login.jsx'
import MyLearning from './pages/MyLearning.jsx'
import Onboarding from './pages/Onboarding.jsx'
import Player from './pages/Player.jsx'
import Profile from './pages/Profile.jsx'
import { Analytics, CourseBuilder, StudioHome, Submissions } from './pages/Studio.jsx'
import { Loading } from './components/ui.jsx'

const ROLE_LABEL = { learner: 'Learner', instructor: 'Content team', admin: 'Admin' }

function useHashRoute() {
  const read = () => window.location.hash.slice(1) || '/'
  const [hash, setHash] = useState(read)
  useEffect(() => {
    const on = () => setHash(read())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [hash, (to) => { window.location.hash = to }]
}

export default function App() {
  const [session, setSession] = useState(loadSession())
  const [route, go] = useHashRoute()
  const [system, setSystem] = useState(null)
  const [profile, setProfile] = useState(undefined)
  const user = session?.user

  useEffect(() => { api('/system/status').then(setSystem).catch(() => setSystem({ categories: [], llm: {} })) }, [])
  useEffect(() => {
    if (!session) return
    api('/me').then((me) => setProfile(me.profile)).catch((e) => e.status === 401 && logout())
  }, [session?.token])

  function login(data) {
    setToken(data.token)
    saveSession(data)
    setProfile(undefined)
    setSession(data)
    go('/')
  }
  function logout() {
    setToken(null)
    saveSession(null)
    setSession(null)
    go('/')
  }

  const [, section, a, b] = route.split('/')
  // certificates are publicly verifiable, signed in or not
  if (section === 'certificate' && a) return <div className="app"><main><Certificate code={a} /></main></div>
  if (!user) return <Login onLogin={login} />
  if (!system || profile === undefined) return <Loading />
  const categories = system.categories

  if (user.role === 'learner' && profile && !profile.onboarded) {
    return <Onboarding user={user} categories={categories} onDone={(p) => { setProfile(p); go('/') }} />
  }

  const isStaff = user.role !== 'learner'
  let page
  if (section === 'learn' && a) page = <Player key={a} courseId={Number(a)} lessonId={b ? Number(b) : null} go={go} />
  else if (section === 'course' && a) page = <CoursePage slug={a} go={go} />
  else if (section === 'catalogue') page = <Catalogue categories={categories} go={go} />
  else if (section === 'learning') page = <MyLearning go={go} />
  else if (section === 'profile') page = <Profile user={user} categories={categories} />
  else if (isStaff && section === 'studio') {
    if (a === 'course' && b) page = <CourseBuilder courseId={Number(b)} go={go} />
    else if (a === 'analytics' && b) page = <Analytics courseId={Number(b)} go={go} />
    else if (a === 'submissions') page = <Submissions />
    else page = <StudioHome go={go} />
  } else if (user.role === 'admin' && section === 'admin') page = <Admin user={user} />
  else if (isStaff) page = user.role === 'admin' ? <Admin user={user} /> : <StudioHome go={go} />
  else page = <LearnerHome user={user} go={go} />

  const nav = {
    learner: [['/', 'Home'], ['/catalogue', 'Catalogue'], ['/learning', 'My learning']],
    instructor: [['/studio', 'Studio'], ['/catalogue', 'Catalogue']],
    admin: [['/admin', 'Admin'], ['/studio', 'Studio'], ['/catalogue', 'Catalogue']],
  }[user.role]
  const current = '/' + (section || '')
  const inPlayer = section === 'learn'

  return (
    <div className={`app ${inPlayer ? 'in-player' : ''}`}>
      <header className="topbar">
        <a className="brand" href="#/"><span className="logo">✦</span> Nova Academy</a>
        <nav>
          {nav.map(([to, label]) => (
            <a key={to} href={`#${to}`} className={current === to || (to === '/' && current === '/') ? 'on' : ''}>{label}</a>
          ))}
        </nav>
        <div className="who">
          {system.llm?.provider && (
            <span className="llm-tag" title="Model behind the AI tutor. Answers are checked against course content.">
              {system.llm.provider === 'offline' ? 'Tutor: course content' : `Tutor: ${system.llm.model}`}
            </span>
          )}
          <a href="#/profile" className="user"><strong>{user.display_name}</strong><small>{ROLE_LABEL[user.role]}</small></a>
          <button className="btn ghost small" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main>{page}</main>
      {!inPlayer && <footer className="footer">Nova Academy · demo with fictional data · AI tutor answers are checked against course content</footer>}
    </div>
  )
}
