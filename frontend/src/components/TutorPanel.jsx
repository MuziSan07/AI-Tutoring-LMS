import { useEffect, useRef, useState } from 'react'
import { api, stream } from '../api.js'
import Avatar from './Avatar.jsx'
import Markdown from './Markdown.jsx'
import { listen, speak, stopSpeaking, sttSupported, ttsSupported } from './speech.js'

const ACTIONS = [
  { action: 'quiz_me', label: '🎯 Quiz me' },
  { action: 'explain_simple', label: '💡 Explain simply' },
  { action: 'example', label: '🧪 Example' },
]

function plain(md) {
  return md.replace(/```[\s\S]*?```/g, ' (see the code example) ').replace(/[*_`#>]/g, '').replace(/\n+/g, '. ')
}

export default function TutorPanel({ courseId, lessonId, profile, onClose }) {
  const [messages, setMessages] = useState([])
  const [greeting, setGreeting] = useState('')
  const [llm, setLlm] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [tick, setTick] = useState(0)
  const [voiceOn, setVoiceOn] = useState(!!profile?.voice_enabled && ttsSupported)
  const [listening, setListening] = useState(false)
  const [practice, setPractice] = useState(null)
  const endRef = useRef(null)
  const recRef = useRef(null)
  const avatarOn = profile?.avatar_enabled ?? true

  useEffect(() => {
    api(`/tutor/${courseId}?lesson_id=${lessonId || ''}`).then((d) => {
      setMessages(d.messages)
      setGreeting(d.greeting)
      setLlm(d.llm)
      const last = d.messages[d.messages.length - 1]
      setPractice(last?.meta?.kind === 'practice' ? last.meta.question : null)
    })
    return () => stopSpeaking()
  }, [courseId, lessonId])

  useEffect(() => { endRef.current?.scrollIntoView({ block: 'end' }) }, [messages, waiting])

  async function say(text) {
    if (!voiceOn || document.hidden) return
    setSpeaking(true)
    await speak(plain(text), { onBoundary: () => setTick((t) => t + 1) })
    setSpeaking(false)
  }

  async function send({ text, action }) {
    if (busy || (!text?.trim() && !action)) return
    stopSpeaking()
    const shown = action ? ACTIONS.find((a) => a.action === action).label.slice(2).trim() : text.trim()
    setMessages((m) => [...m, { role: 'learner', text: shown, meta: {} }, { role: 'tutor', text: '', meta: { streaming: true } }])
    setInput('')
    setBusy(true)
    setWaiting(true)
    let final = null
    try {
      await stream(`/tutor/${courseId}/message`, { text, action, lesson_id: lessonId }, (ev) => {
        if (ev.type === 'delta') {
          setWaiting(false)
          setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, text: x.text + ev.text } : x)))
        } else if (ev.type === 'done') {
          final = ev.message
          setMessages((m) => m.map((x, i) => (i === m.length - 1 ? ev.message : x)))
        }
      })
    } catch (e) {
      setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { role: 'tutor', text: e.message, meta: { kind: 'error' } } : x)))
    } finally {
      setBusy(false)
      setWaiting(false)
    }
    if (final) {
      setPractice(final.meta.kind === 'practice' ? final.meta.question : null)
      say(final.text)
    }
  }

  function toggleMic() {
    if (listening) return recRef.current?.stop()
    stopSpeaking()
    setListening(true)
    recRef.current = listen({
      onInterim: setInput,
      onFinal: (t) => send({ text: t }),
      onEnd: () => setListening(false),
      onError: () => setListening(false),
    })
  }

  const offline = llm?.provider === 'offline'
  return (
    <aside className="tutor" aria-label="AI tutor">
      <header className="tutor-head">
        {avatarOn ? <Avatar speaking={speaking} mouthTick={tick} mood={busy ? 'neutral' : 'happy'} /> : <span className="tutor-dot">✦</span>}
        <div className="tutor-title">
          <strong>Nova</strong>
          <span>{waiting ? 'Thinking…' : speaking ? 'Speaking…' : listening ? 'Listening…' : offline ? 'Answers from course content' : `Personal tutor · ${llm?.model || ''}`}</span>
        </div>
        <button className={`icon-btn ${voiceOn ? 'on' : ''}`} onClick={() => { setVoiceOn(!voiceOn); stopSpeaking() }} disabled={!ttsSupported}
          aria-pressed={voiceOn} title={voiceOn ? 'Mute voice' : 'Read answers aloud'}>{voiceOn ? '🔊' : '🔇'}</button>
        {onClose && <button className="icon-btn" onClick={onClose} aria-label="Close tutor">✕</button>}
      </header>

      <div className="tutor-log" role="log" aria-live="polite">
        <div className="bubble tutor"><Markdown text={greeting} /></div>
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role} ${m.meta?.kind || ''}`}>
            {m.role === 'tutor' ? (
              m.text ? <Markdown text={m.text} /> : <span className="typing"><span /><span /><span /></span>
            ) : m.text}
            {m.role === 'tutor' && m.meta?.sources?.length > 0 && (
              <div className="sources">
                {m.meta.generated ? 'Based on' : 'From'}: {m.meta.sources.map((s) => <a key={s.lesson_id} href={`#/learn/${courseId}/${s.lesson_id}`}>{s.lesson_title}</a>).reduce((a, b) => [a, ', ', b])}
              </div>
            )}
          </div>
        ))}
        {waiting && messages[messages.length - 1]?.text === '' && <p className="muted small center">Nova is thinking{offline ? '' : ' (local AI - can take a little while)'}…</p>}
        <div ref={endRef} />
      </div>

      {practice?.type === 'choice' && !busy && (
        <div className="practice-options">
          {practice.options.map((o, i) => (
            <button key={i} className="chip" onClick={() => send({ text: 'ABCDEFG'[i] })}><strong>{'ABCDEFG'[i]}</strong>&nbsp;{o.replace(/`/g, '')}</button>
          ))}
        </div>
      )}

      <div className="tutor-actions">
        {ACTIONS.map((a) => <button key={a.action} className="chip" onClick={() => send({ action: a.action })} disabled={busy}>{a.label}</button>)}
      </div>
      <form className="tutor-input" onSubmit={(e) => { e.preventDefault(); send({ text: input }) }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={practice ? 'Type your answer…' : 'Ask about this course…'} aria-label="Message the tutor" disabled={busy} />
        <button type="button" className={`icon-btn ${listening ? 'live' : ''}`} onClick={toggleMic} disabled={!sttSupported || busy}
          title={sttSupported ? 'Speak your question' : 'Voice input needs Chrome or Edge'} aria-label="Speak">🎤</button>
        <button className="btn small" disabled={busy || !input.trim()}>Send</button>
      </form>
      <p className="tutor-foot">Nova is an AI and only answers from this course's material.</p>
    </aside>
  )
}
