import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import Avatar from '../components/Avatar.jsx'
import MathTex from '../components/Math.jsx'
import Whiteboard from '../components/Whiteboard.jsx'
import { listen, speak, stopSpeaking, sttSupported, ttsSupported } from '../components/speech.js'

const PHASES = { diagnostic: 'Warm-up', practice: 'Practice', reassess: 'Final check', complete: 'Complete' }
const QUICK = [
  { label: '💡 Hint', text: 'Can I have a hint?' },
  { label: '🔄 Explain another way', text: "I don't understand, can you explain it another way?" },
]
const KEYS = ['/', 'x', '²', '√', '(', ')', '-', '=']

function applyOps(board, ops) {
  let next = board
  for (const op of ops) next = op.type === 'clear' ? [] : [...next, op]
  return next
}

export default function Classroom({ topicId, onExit }) {
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [messages, setMessages] = useState([])
  const [board, setBoard] = useState([])
  const [progress, setProgress] = useState(null)
  const [question, setQuestion] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [voiceOn, setVoiceOn] = useState(true)
  const [avatarOn, setAvatarOn] = useState(true)
  const [speaking, setSpeaking] = useState(false)
  const [mouthTick, setMouthTick] = useState(0)
  const [mood, setMood] = useState('neutral')
  const [waving, setWaving] = useState(false)
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [recommendation, setRecommendation] = useState(null)

  const queueRef = useRef(Promise.resolve())
  const genRef = useRef(0) // bump to interrupt queued turns
  const voiceRef = useRef(voiceOn)
  const boardRef = useRef(null)
  const chatEndRef = useRef(null)
  const recRef = useRef(null)
  const inputRef = useRef(null)
  voiceRef.current = voiceOn

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, thinking, interim])

  // Play tutor turns one by one, keeping speech, avatar and whiteboard in sync.
  const play = useCallback((turns) => {
    const gen = genRef.current
    for (const turn of turns) {
      queueRef.current = queueRef.current.then(async () => {
        if (gen !== genRef.current) {
          // interrupted: show the remaining turns instantly, silently
          setBoard((b) => applyOps(b, turn.board))
          setMessages((m) => [...m, { role: 'tutor', text: turn.say, action: turn.action }])
          if (turn.question) setQuestion(turn.question)
          return
        }
        if (turn.action === 'greet') { setWaving(true); setTimeout(() => setWaving(false), 2200) }
        setMood(turn.meta?.correct ? 'happy' : turn.action === 'complete' ? 'happy' : 'neutral')
        setBoard((b) => applyOps(b, turn.board))
        setMessages((m) => [...m, { role: 'tutor', text: turn.say, action: turn.action, meta: turn.meta }])
        if (turn.question) setQuestion(turn.question)
        if (turn.action === 'complete') setRecommendation(turn.meta?.recommendation || null)
        if (voiceRef.current && ttsSupported && !document.hidden) {
          setSpeaking(true)
          await speak(turn.say, { onBoundary: () => setMouthTick((t) => t + 1) })
          setSpeaking(false)
        } else {
          await new Promise((r) => setTimeout(r, Math.min(1800, 350 + turn.say.length * 8)))
        }
      })
    }
    queueRef.current = queueRef.current.then(() => inputRef.current?.focus())
  }, [])

  const interrupt = useCallback(() => {
    genRef.current += 1
    stopSpeaking()
    setSpeaking(false)
  }, [])

  useEffect(() => {
    let cancelled = false
    api('/lessons/start', { method: 'POST', body: { topic_id: topicId } })
      .then((data) => {
        if (cancelled) return
        setLesson(data)
        setVoiceOn(!!data.settings.voice_enabled && ttsSupported)
        voiceRef.current = !!data.settings.voice_enabled && ttsSupported
        setAvatarOn(!!data.settings.avatar_enabled)
        setProgress(data.progress)
        play(data.turns)
      })
      .catch((e) => setError(e.message))
    return () => {
      cancelled = true
      genRef.current += 1
      stopSpeaking()
    }
  }, [topicId, play])

  async function send(text) {
    const clean = text.trim()
    if (!clean || busy || !lesson) return
    interrupt()
    setInput('')
    setInterim('')
    setMessages((m) => [...m, { role: 'student', text: clean }])
    setBusy(true)
    const slow = setTimeout(() => setThinking(true), 400)
    try {
      const data = await api(`/lessons/${lesson.lesson_id}/message`, { method: 'POST', body: { text: clean } })
      setProgress(data.progress)
      play(data.turns)
    } catch (e) {
      setMessages((m) => [...m, { role: 'system', text: e.message }])
    } finally {
      clearTimeout(slow)
      setThinking(false)
      setBusy(false)
    }
  }

  function toggleMic() {
    if (listening) {
      recRef.current?.stop()
      return
    }
    interrupt() // the student can talk over Nova
    setListening(true)
    recRef.current = listen({
      onInterim: setInterim,
      onFinal: (t) => send(t),
      onEnd: () => { setListening(false); setInterim('') },
      onError: (err) => {
        setListening(false)
        if (err === 'not-allowed') setMessages((m) => [...m, { role: 'system', text: 'Microphone permission was blocked - you can type instead.' }])
      },
    })
  }

  async function saveAndExit() {
    interrupt()
    if (lesson) {
      const image = boardRef.current?.snapshot()
      await Promise.allSettled([
        image ? api(`/lessons/${lesson.lesson_id}/drawing`, { method: 'POST', body: { image } }) : null,
        api(`/lessons/${lesson.lesson_id}/end`, { method: 'POST' }),
      ])
    }
    onExit()
  }

  function toggleVoice() {
    const next = !voiceOn
    setVoiceOn(next)
    voiceRef.current = next
    if (!next) interrupt()
    api('/student/settings', { method: 'PUT', body: { daily_limit_minutes: 0, voice_enabled: next, avatar_enabled: avatarOn } }).catch(() => {})
  }
  function toggleAvatar() {
    const next = !avatarOn
    setAvatarOn(next)
    api('/student/settings', { method: 'PUT', body: { daily_limit_minutes: 0, voice_enabled: voiceOn, avatar_enabled: next } }).catch(() => {})
  }

  function insertKey(k) {
    const map = { '²': '^2', '√': 'sqrt(' }
    setInput((v) => v + (map[k] || k))
    inputRef.current?.focus()
  }

  if (error) {
    return (
      <div className="page narrow">
        <div className="card notice">
          <h2>We couldn't start this lesson</h2>
          <p>{error}</p>
          <button className="btn" onClick={onExit}>Back to dashboard</button>
        </div>
      </div>
    )
  }

  const complete = progress?.phase === 'complete'
  return (
    <div className="classroom">
      <header className="class-head">
        <button className="btn ghost" onClick={saveAndExit}>← Save & exit</button>
        <div className="class-title">
          <span className="eyebrow">{lesson?.topic.key_stage} · Year {lesson?.topic.year} · {lesson?.topic.strand}</span>
          <h1>{lesson?.topic.title || 'Starting lesson…'}</h1>
        </div>
        {progress && (
          <div className="class-progress" aria-live="polite">
            <span className={`phase phase-${progress.phase}`}>{PHASES[progress.phase]}</span>
            <span className="level">Level: {progress.level}</span>
            <div className="mastery-mini" title="Evidence-based mastery estimate">
              <div className="bar"><div style={{ width: `${progress.p_mastery * 100}%` }} /></div>
              <span>{progress.status}</span>
            </div>
            {progress.streak > 0 && <span className="streak">🔥 {progress.streak}</span>}
          </div>
        )}
      </header>

      <div className="class-body">
        <section className="class-left">
          <div className="tutor-card">
            {avatarOn ? (
              <Avatar speaking={speaking} mouthTick={mouthTick} mood={mood} waving={waving} />
            ) : (
              <div className="avatar-off"><span className="ai-badge static">AI tutor</span></div>
            )}
            <div className="tutor-meta">
              <strong>Nova</strong>
              <span>{speaking ? 'Speaking…' : thinking ? 'Thinking…' : listening ? 'Listening…' : 'Your AI maths tutor'}</span>
              <div className="toggles">
                <button className={`chip ${voiceOn ? 'on' : ''}`} onClick={toggleVoice} disabled={!ttsSupported} aria-pressed={voiceOn}>
                  {voiceOn ? '🔊 Voice on' : '🔇 Voice off'}
                </button>
                <button className={`chip ${avatarOn ? 'on' : ''}`} onClick={toggleAvatar} aria-pressed={avatarOn}>
                  {avatarOn ? '🧑‍🏫 Avatar on' : '🧑‍🏫 Avatar off'}
                </button>
              </div>
            </div>
          </div>

          <div className="chat" role="log" aria-live="polite">
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role} ${m.action || ''}`}>
                {m.role === 'tutor' && m.action === 'safeguarding' && <strong className="safe-tag">Safeguarding</strong>}
                {m.text}
              </div>
            ))}
            {interim && <div className="bubble student interim">{interim}…</div>}
            {thinking && <div className="bubble tutor typing"><span /><span /><span /></div>}
            <div ref={chatEndRef} />
          </div>

          {complete ? (
            <div className="complete-actions">
              {recommendation && <p>Up next: <strong>{recommendation.title}</strong></p>}
              <button className="btn" onClick={saveAndExit}>Back to dashboard</button>
            </div>
          ) : (
            <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input) }}>
              {question && (
                <div className="current-q">
                  <span>Current question</span>
                  <MathTex tex={question.latex} />
                </div>
              )}
              <div className="quick">
                {QUICK.map((q) => (
                  <button type="button" key={q.label} className="chip" onClick={() => send(q.text)} disabled={busy}>{q.label}</button>
                ))}
              </div>
              <div className="keys" aria-label="Maths symbols">
                {KEYS.map((k) => <button type="button" key={k} className="key" onClick={() => insertKey(k)}>{k}</button>)}
              </div>
              <div className="input-row">
                <input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={question ? `Type your answer (${question.input_hint}) or ask a question` : 'Type a message'}
                  aria-label="Your answer or question"
                  disabled={!lesson}
                />
                <button
                  type="button"
                  className={`mic ${listening ? 'live' : ''}`}
                  onClick={toggleMic}
                  disabled={!sttSupported || !lesson}
                  title={sttSupported ? 'Speak your answer' : 'Voice input needs Chrome or Edge - please type instead'}
                  aria-label="Speak"
                >🎤</button>
                <button className="btn" disabled={busy || !input.trim()}>Send</button>
              </div>
            </form>
          )}
        </section>

        <section className="class-right">
          <Whiteboard ref={boardRef} ops={board} />
        </section>
      </div>
    </div>
  )
}
