import { useEffect, useRef, useState } from 'react'

/** Cosmetic character-by-character reveal. F-007 sends the assistant's
 * complete answer in a single SSE `token` event (not incremental chunks —
 * see the demo-alignment note in the F-009 spec conversation), so this is
 * client-side animation over already-fully-received text, not real
 * streaming. Chosen deliberately so the demo recording still reads as a
 * live, generating response. */
export function useTypewriter(fullText: string, charsPerTick = 3, tickMs = 16) {
  const [visibleLength, setVisibleLength] = useState(0)
  const fullTextRef = useRef(fullText)

  useEffect(() => {
    fullTextRef.current = fullText
    setVisibleLength(0)
    if (!fullText) return

    const interval = window.setInterval(() => {
      setVisibleLength((current) => {
        const next = current + charsPerTick
        if (next >= fullTextRef.current.length) {
          window.clearInterval(interval)
          return fullTextRef.current.length
        }
        return next
      })
    }, tickMs)

    return () => window.clearInterval(interval)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fullText])

  return {
    visibleText: fullText.slice(0, visibleLength),
    isComplete: visibleLength >= fullText.length,
  }
}
