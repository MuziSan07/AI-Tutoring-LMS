import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import MathTex from './Math.jsx'

/* ---------------------------------------------------------- visual ops */

function FractionBars({ fractions, op }) {
  const W = 300, H = 26, gap = 14
  return (
    <svg className="viz" viewBox={`0 0 ${W + 70} ${fractions.length * (H + gap)}`} role="img" aria-label="Fraction bar model">
      {fractions.map(([n, d], row) => {
        const y = row * (H + gap)
        const w = W / d
        return (
          <g key={row}>
            {Array.from({ length: d }, (_, i) => (
              <rect key={i} x={i * w + 1} y={y + 1} width={w - 2} height={H} rx="4"
                fill={i < n ? (row ? 'var(--accent)' : 'var(--primary)') : 'var(--board-cell)'}
                stroke="var(--board-line)" />
            ))}
            <text x={W + 12} y={y + H * 0.72} className="viz-label">{n}/{d}</text>
          </g>
        )
      })}
      {op && fractions.length > 1 && <title>{fractions.map(([n, d]) => `${n}/${d}`).join(` ${op} `)}</title>}
    </svg>
  )
}

function Triangle({ a, b, c, unknown }) {
  const label = (v, key) => (
    <tspan className={unknown === key ? 'viz-unknown' : ''}>{v}</tspan>
  )
  return (
    <svg className="viz" viewBox="0 0 280 190" role="img" aria-label={`Right-angled triangle with sides ${a}, ${b} and hypotenuse ${c}`}>
      <path d="M40 160 L240 160 L40 30 Z" fill="var(--board-cell)" stroke="var(--primary)" strokeWidth="3" strokeLinejoin="round" />
      <path d="M40 142 L58 142 L58 160" fill="none" stroke="var(--ink)" strokeWidth="2" />
      <text x="14" y="100" className="viz-label">{label(a, 'a')}</text>
      <text x="125" y="182" className="viz-label">{label(b, 'b')}</text>
      <text x="150" y="88" className="viz-label">{label(c, 'c')}</text>
    </svg>
  )
}

function Graph({ lines = [], points = [] }) {
  const R = 6, S = 22, O = R * S + 10, size = O * 2
  const px = (x) => O + x * S
  const py = (y) => O - y * S
  const ticks = Array.from({ length: R * 2 + 1 }, (_, i) => i - R)
  return (
    <svg className="viz graph" viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Coordinate grid">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={px(t)} y1={py(-R)} x2={px(t)} y2={py(R)} stroke="var(--board-line)" strokeWidth={t ? 0.6 : 0} />
          <line x1={px(-R)} y1={py(t)} x2={px(R)} y2={py(t)} stroke="var(--board-line)" strokeWidth={t ? 0.6 : 0} />
          {t !== 0 && t % 2 === 0 && <text x={px(t)} y={O + 14} className="viz-tick">{t}</text>}
          {t !== 0 && t % 2 === 0 && <text x={O - 14} y={py(t) + 4} className="viz-tick">{t}</text>}
        </g>
      ))}
      <line x1={px(-R)} y1={O} x2={px(R)} y2={O} stroke="var(--ink)" strokeWidth="1.5" />
      <line x1={O} y1={py(-R)} x2={O} y2={py(R)} stroke="var(--ink)" strokeWidth="1.5" />
      <text x={px(R) - 4} y={O - 6} className="viz-tick">x</text>
      <text x={O + 6} y={py(R) + 10} className="viz-tick">y</text>
      <defs><clipPath id="gclip"><rect x={px(-R)} y={py(R)} width={2 * R * S} height={2 * R * S} /></clipPath></defs>
      {lines.map((l, i) => (
        <g key={i} clipPath="url(#gclip)">
          <line className="draw-in" x1={px(-R)} y1={py(l.m * -R + l.c)} x2={px(R)} y2={py(l.m * R + l.c)}
            stroke={i ? 'var(--accent)' : 'var(--primary)'} strokeWidth="3" strokeLinecap="round" />
        </g>
      ))}
      {lines.map((l, i) => (
        <text key={`l${i}`} x={px(-R) + 6} y={py(R) + 16 + i * 16} className="viz-label small" fill={i ? 'var(--accent)' : 'var(--primary)'}>{l.label}</text>
      ))}
      {points.map(([x, y], i) => (
        <g key={`p${i}`}>
          <circle cx={px(x)} cy={py(y)} r="5" fill="var(--warn)" stroke="#fff" strokeWidth="1.5" />
          <text x={px(x) + 8} y={py(y) - 6} className="viz-tick strong">({x}, {y})</text>
        </g>
      ))}
    </svg>
  )
}

export function BoardOp({ op }) {
  switch (op.type) {
    case 'title':
      return <h3 className="board-title">{op.content}</h3>
    case 'text':
      return <p className="board-text">{op.content}</p>
    case 'math':
      return <div className="board-math"><MathTex tex={op.content} block /></div>
    case 'step':
      return (
        <div className="board-step">
          <span className="step-n">{op.n}</span>
          <div>
            <p>{op.content}</p>
            {op.latex && <MathTex tex={op.latex} block />}
          </div>
        </div>
      )
    case 'highlight':
      return (
        <div className="board-highlight">
          <span>{op.content}</span> {op.latex && <MathTex tex={op.latex} />}
        </div>
      )
    case 'fraction_bars':
      return <FractionBars {...op} />
    case 'triangle':
      return <Triangle {...op} />
    case 'graph':
      return <Graph {...op} />
    default:
      return null
  }
}

/* ---------------------------------------------------------- board + student ink */

const Whiteboard = forwardRef(function Whiteboard({ ops, readOnly = false, drawing }, ref) {
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)
  const [tool, setTool] = useState(null) // null | 'pen' | 'eraser'
  const [colour, setColour] = useState('#e4572e')
  const drawingRef = useRef(false)
  const endRef = useRef(null)

  useImperativeHandle(ref, () => ({
    snapshot: () => canvasRef.current?.toDataURL('image/png'),
    clearInk: () => clearInk(),
  }))

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [ops.length])

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    if (!canvas || !wrap) return
    const resize = () => {
      const data = canvas.width ? canvas.toDataURL() : null
      canvas.width = wrap.scrollWidth
      canvas.height = Math.max(wrap.scrollHeight, wrap.clientHeight)
      if (data) {
        const img = new Image()
        img.onload = () => canvas.getContext('2d').drawImage(img, 0, 0)
        img.src = data
      }
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(wrap.firstElementChild || wrap)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (!drawing || !canvasRef.current) return
    const img = new Image()
    img.onload = () => canvasRef.current?.getContext('2d').drawImage(img, 0, 0)
    img.src = drawing
  }, [drawing])

  function pos(e) {
    const r = canvasRef.current.getBoundingClientRect()
    return [e.clientX - r.left, e.clientY - r.top]
  }
  function down(e) {
    if (!tool) return
    e.preventDefault()
    canvasRef.current.setPointerCapture(e.pointerId)
    drawingRef.current = true
    const ctx = canvasRef.current.getContext('2d')
    const [x, y] = pos(e)
    ctx.beginPath()
    ctx.moveTo(x, y)
  }
  function move(e) {
    if (!drawingRef.current) return
    const ctx = canvasRef.current.getContext('2d')
    const [x, y] = pos(e)
    const pressure = e.pressure && e.pointerType === 'pen' ? e.pressure : 0.5
    ctx.globalCompositeOperation = tool === 'eraser' ? 'destination-out' : 'source-over'
    ctx.strokeStyle = colour
    ctx.lineWidth = tool === 'eraser' ? 22 : 2 + pressure * 3
    ctx.lineCap = ctx.lineJoin = 'round'
    ctx.lineTo(x, y)
    ctx.stroke()
  }
  function up() {
    drawingRef.current = false
  }
  function clearInk() {
    const c = canvasRef.current
    c?.getContext('2d').clearRect(0, 0, c.width, c.height)
  }

  return (
    <div className="whiteboard">
      {!readOnly && (
        <div className="wb-toolbar" role="toolbar" aria-label="Whiteboard tools">
          <span className="wb-label">Your ink</span>
          <button className={`tool ${tool === 'pen' ? 'on' : ''}`} onClick={() => setTool(tool === 'pen' ? null : 'pen')} aria-pressed={tool === 'pen'}>✏️ Pen</button>
          <button className={`tool ${tool === 'eraser' ? 'on' : ''}`} onClick={() => setTool(tool === 'eraser' ? null : 'eraser')} aria-pressed={tool === 'eraser'}>🧽 Eraser</button>
          {['#e4572e', '#2563eb', '#16a34a', '#1d2340'].map((c) => (
            <button key={c} className={`swatch ${colour === c ? 'on' : ''}`} style={{ background: c }} onClick={() => { setColour(c); setTool('pen') }} aria-label={`Pen colour ${c}`} />
          ))}
          <button className="tool" onClick={clearInk}>Clear ink</button>
        </div>
      )}
      <div className="wb-surface" ref={wrapRef}>
        <div className="wb-content">
          {ops.length === 0 && <p className="wb-empty">The whiteboard will fill in as Nova teaches.</p>}
          {ops.map((op, i) => (
            <div className="wb-op" key={i} style={{ animationDelay: `${Math.min(i, 6) * 60}ms` }}>
              <BoardOp op={op} />
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <canvas
          ref={canvasRef}
          className={`wb-ink ${tool ? 'active' : ''}`}
          style={{ touchAction: tool ? 'none' : 'auto' }}
          onPointerDown={down}
          onPointerMove={move}
          onPointerUp={up}
          onPointerCancel={up}
          aria-label="Drawing layer"
        />
      </div>
    </div>
  )
})

export default Whiteboard
