import { useEffect, useState } from 'react'
import { api, downloadJson, loadSession, saveSession, setToken } from './api.js'
import Admin from './pages/Admin.jsx'
import Classroom from './pages/Classroom.jsx'
import History from './pages/History.jsx'
import Login from './pages/Login.jsx'
import Parent from './pages/Parent.jsx'
import StudentHome from './pages/StudentHome.jsx'
import Teacher from './pages/Teacher.jsx'
import { Loading, ProgressProfile } from './components/ui.jsx'

const ROLE_LABEL = { student: 'Student', parent: 'Parent', teacher: 'Teacher', school_admin: 'School admin', super_admin: 'Platform admin' }

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash.slice(1) || '/')
  useEffect(() => {
    const on = () => setHash(window.location.hash.slice(1) || '/')
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [hash, (to) => { window.location.hash = to }]
}

function MyProgress({ go }) {
  const [data, setData] = useState(null)
  useEffect(() => { api('/student/dashboard').then(setData) }, [])
  if (!data) return <Loading />
  return (
    <div className="page">
      <div className="page-head">
        <h1>My progress</h1>
        <button className="btn ghost" onClick={async () => downloadJson(await api(`/students/${data.student.id}/export`), 'my-learning-record.json')}>Download my data</button>
      </div>
      <ProgressProfile data={data} onOpenLesson={(id) => go(`/history/${id}`)} />
    </div>
  )
}

export default function App() {
  const [session, setSession] = useState(loadSession())
  const [route, go] = useHashRoute()
  const [llm, setLlm] = useState(null)
  const user = session?.user

  useEffect(() => {
    api('/system/status').then((s) => setLlm(s.llm)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!session) return
    api('/me').catch((e) => e.status === 401 && logout())
  }, [])

  function login(data) {
    setToken(data.token)
    saveSession(data)
    setSession(data)
    go('/')
  }
  function logout() {
    setToken(null)
    saveSession(null)
    setSession(null)
    go('/')
  }

  if (!user) return <Login onLogin={login} />

  const [, section, param] = route.split('/')
  if (user.role === 'student' && section === 'lesson' && param) {
    return <Classroom key={param} topicId={param} onExit={() => go('/')} />
  }

  const nav = {
    student: [['/', 'Home'], ['/progress', 'My progress'], ['/history', 'Lesson history']],
    parent: [['/', 'My child']],
    teacher: [['/', 'My classes']],
    school_admin: [['/', 'School']],
    super_admin: [['/', 'Platform']],
  }[user.role]

  let page
  if (user.role === 'student') {
    if (section === 'progress') page = <MyProgress go={go} />
    else if (section === 'history') page = <History openId={param ? Number(param) : null} onOpen={(id) => go(id ? `/history/${id}` : '/history')} />
    else page = <StudentHome user={user} onStart={(topic) => go(`/lesson/${topic}`)} />
  } else if (user.role === 'parent') page = <Parent />
  else if (user.role === 'teacher') page = <Teacher />
  else page = <Admin user={user} />

  const current = '/' + (section || '')
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand"><span className="logo">✦</span> Nova</div>
        <nav>
          {nav.map(([to, label]) => (
            <a key={to} href={`#${to}`} className={current === to || (to !== '/' && current.startsWith(to)) ? 'on' : ''}>{label}</a>
          ))}
        </nav>
        <div className="who">
          {llm && <span className="llm-tag" title="Language model in use. All maths marking is verified by SymPy.">{llm.provider === 'offline' ? 'Rule-based voice' : `Local AI: ${llm.model}`}</span>}
          <span className="user"><strong>{user.display_name}</strong><small>{ROLE_LABEL[user.role]}</small></span>
          <button className="btn ghost small" onClick={logout}>Sign out</button>
        </div>
      </header>
      <main>{page}</main>
      <footer className="footer">Nova is an AI tutor. Demo MVP · fictional data · KS3/GCSE Mathematics content v1.0</footer>
    </div>
  )
}
