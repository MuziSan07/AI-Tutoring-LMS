import katex from 'katex'
import { useMemo } from 'react'

export default function Math({ tex, block = false }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(tex || '', { displayMode: block, throwOnError: false, strict: false })
    } catch {
      return tex
    }
  }, [tex, block])
  return <span className={block ? 'math-block' : 'math-inline'} dangerouslySetInnerHTML={{ __html: html }} />
}
