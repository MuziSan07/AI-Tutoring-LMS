// Browser speech: British-English TTS and speech recognition (Web Speech API).
// Production swaps these for a streaming STT/TTS service behind the same interface.

const synth = typeof window !== 'undefined' ? window.speechSynthesis : null
const Recognition = typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : null

export const ttsSupported = !!synth
export const sttSupported = !!Recognition

function britishVoice() {
  const voices = synth?.getVoices() || []
  return (
    voices.find((v) => v.lang === 'en-GB' && /female|libby|sonia|hazel|serena|kate|google uk english female/i.test(v.name)) ||
    voices.find((v) => v.lang === 'en-GB') ||
    voices.find((v) => v.lang.startsWith('en'))
  )
}

// Read maths aloud more naturally than raw symbols.
function speakable(text) {
  return text
    .replace(/(\d+)\/(\d+)/g, '$1 over $2')
    .replace(/\bx\^2\b/g, 'x squared')
    .replace(/\^2/g, ' squared')
    .replace(/(\d)\s*x\s*(\d)/g, '$1 times $2')
    .replace(/÷/g, ' divided by ')
    .replace(/ - /g, ' minus ')
    .replace(/=/g, ' equals ')
    .replace(/£/g, '£')
}

let cancelled = 0

function speakOne(sentence, { onBoundary, onStart }) {
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(sentence)
    const voice = britishVoice()
    if (voice) u.voice = voice
    u.lang = 'en-GB'
    u.rate = 1.02
    u.pitch = 1.05
    // Chromium sometimes never fires onend; never let a lesson stall on audio.
    const watchdog = setTimeout(() => { synth.cancel(); resolve() }, 2500 + sentence.length * 90)
    const done = () => { clearTimeout(watchdog); resolve() }
    u.onstart = () => onStart?.()
    u.onboundary = () => onBoundary?.()
    u.onend = done
    u.onerror = done
    synth.speak(u)
  })
}

// Speak sentence by sentence: avoids the long-utterance hang and lets
// interruptions take effect quickly.
export async function speak(text, handlers = {}) {
  if (!synth) return
  const gen = cancelled
  const sentences = speakable(text).match(/[^.!?]+[.!?]*/g) || [text]
  for (const s of sentences) {
    if (gen !== cancelled) return
    if (s.trim()) await speakOne(s.trim(), handlers)
  }
}

export function stopSpeaking() {
  cancelled += 1
  synth?.cancel()
}

export function listen({ onInterim, onFinal, onEnd, onError }) {
  if (!Recognition) return null
  const r = new Recognition()
  r.lang = 'en-GB'
  r.interimResults = true
  r.continuous = false
  r.onresult = (e) => {
    let interim = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i]
      if (res.isFinal) onFinal?.(res[0].transcript)
      else interim += res[0].transcript
    }
    if (interim) onInterim?.(interim)
  }
  r.onerror = (e) => onError?.(e.error)
  r.onend = () => onEnd?.()
  r.start()
  return r
}
