import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { ErrorBox, Loading, fmtDate, fmtMinutes } from '../components/ui.jsx'

export default function Certificate({ code }) {
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { api(`/certificates/${code}`).then(setC).catch((e) => setError(e.message)) }, [code])
  if (error) return <div className="page narrow"><ErrorBox error={error} /></div>
  if (!c) return <Loading />
  const url = `${window.location.origin}/#/certificate/${c.code}`
  return (
    <div className="page cert-page">
      <div className="no-print row-between">
        <span className="banner good">✓ Verified certificate - issued by Nova Academy</span>
        <div className="row-actions">
          <button className="btn ghost" onClick={() => navigator.clipboard?.writeText(url)}>Copy share link</button>
          <button className="btn" onClick={() => window.print()}>Print / save as PDF</button>
        </div>
      </div>
      <div className="certificate" style={{ '--c': c.colour }}>
        <div className="cert-border">
          <div className="brand big center"><span className="logo">✦</span> Nova Academy</div>
          <p className="cert-label">Certificate of completion</p>
          <p className="cert-presented">This certifies that</p>
          <h1 className="cert-name">{c.learner}</h1>
          <p className="cert-presented">has successfully completed</p>
          <h2 className="cert-course">{c.icon} {c.course}</h2>
          <p className="muted">{fmtMinutes(c.minutes)} of learning, including assessed quizzes</p>
          <div className="cert-foot">
            <div><strong>{fmtDate(c.issued_at)}</strong><span>Date issued</span></div>
            <div><strong>{c.instructor}</strong><span>Course instructor</span></div>
            <div><strong>{c.code}</strong><span>Verification code</span></div>
          </div>
        </div>
      </div>
    </div>
  )
}
