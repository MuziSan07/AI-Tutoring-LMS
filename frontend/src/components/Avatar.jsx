import { useEffect, useState } from 'react'

// Lightweight animated teacher (SOW Module 5 MVP option). Lip movement is
// driven by speech boundary events; eyes blink and glance; a wave on greeting.
export default function Avatar({ speaking, mouthTick, mood = 'neutral', waving }) {
  const [glance, setGlance] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setGlance((g) => (Math.random() < 0.5 ? 0 : Math.random() < 0.5 ? -1.5 : 1.5)), 2600)
    return () => clearInterval(id)
  }, [])
  const open = speaking && mouthTick % 2 === 0
  const smile = mood === 'happy'
  return (
    <div className={`avatar ${speaking ? 'is-speaking' : ''}`} aria-label="Nova, AI tutor avatar">
      <svg viewBox="0 0 160 160" role="img">
        <title>Nova, an AI-generated tutor</title>
        <circle cx="80" cy="80" r="76" fill="var(--avatar-bg)" />
        {/* body */}
        <path d="M30 160 C34 122 54 110 80 110 C106 110 126 122 130 160 Z" fill="var(--primary)" />
        <path d="M68 110 L80 126 L92 110" fill="#fff" opacity="0.9" />
        {/* waving hand */}
        <g className={waving ? 'wave' : ''} style={{ transformOrigin: '128px 128px', opacity: waving ? 1 : 0 }}>
          <circle cx="136" cy="108" r="9" fill="#f2c39b" />
          <rect x="130" y="112" width="10" height="26" rx="5" fill="var(--primary)" />
        </g>
        <g className="head">
          {/* hair back */}
          <ellipse cx="80" cy="66" rx="40" ry="44" fill="#3b2a20" />
          {/* face */}
          <ellipse cx="80" cy="72" rx="31" ry="36" fill="#f2c39b" />
          {/* fringe */}
          <path d="M48 62 C52 36 92 26 113 58 C100 50 78 46 60 56 C56 58 52 60 48 62 Z" fill="#3b2a20" />
          {/* eyes */}
          <g className="eyes">
            <ellipse cx={68 + glance} cy="72" rx="4" ry="4.6" fill="#2a1d16" />
            <ellipse cx={92 + glance} cy="72" rx="4" ry="4.6" fill="#2a1d16" />
            <circle cx={69.5 + glance} cy="70.5" r="1.3" fill="#fff" />
            <circle cx={93.5 + glance} cy="70.5" r="1.3" fill="#fff" />
          </g>
          <path d="M61 63 Q68 60 75 63" stroke="#3b2a20" strokeWidth="2" fill="none" strokeLinecap="round" />
          <path d="M85 63 Q92 60 99 63" stroke="#3b2a20" strokeWidth="2" fill="none" strokeLinecap="round" />
          {/* glasses */}
          <g stroke="var(--ink)" strokeWidth="1.6" fill="none" opacity="0.75">
            <rect x="59" y="64" width="18" height="15" rx="6" />
            <rect x="83" y="64" width="18" height="15" rx="6" />
            <path d="M77 71 L83 71" />
          </g>
          <ellipse cx="62" cy="86" rx="5" ry="3" fill="#f39a8b" opacity="0.45" />
          <ellipse cx="98" cy="86" rx="5" ry="3" fill="#f39a8b" opacity="0.45" />
          {/* mouth */}
          {open ? (
            <ellipse cx="80" cy="92" rx="7" ry="5" fill="#8a2f2f" />
          ) : (
            <path d={smile ? 'M70 89 Q80 99 90 89' : 'M72 91 Q80 96 88 91'} stroke="#8a2f2f" strokeWidth="2.6" fill="none" strokeLinecap="round" />
          )}
        </g>
      </svg>
      <span className="ai-badge" title="Nova is an AI-generated tutor, not a real person">AI tutor</span>
    </div>
  )
}
