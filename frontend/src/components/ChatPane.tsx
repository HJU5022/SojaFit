import { useEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { ArrowDown } from 'lucide-react'

export default function ChatPane({ children, composer, input, context }: {
  children: ReactNode; composer: ReactNode; input: RefObject<HTMLTextAreaElement | null>; context: string
}) {
  const viewport = useRef<HTMLElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const end = useRef<HTMLSpanElement>(null)
  const [showJump, setShowJump] = useState(false)
  function updateJump() {
    if (viewport.current && end.current) setShowJump(end.current.getBoundingClientRect().bottom > viewport.current.getBoundingClientRect().bottom + 8)
  }
  useEffect(() => {
    updateJump()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(updateJump)
    if (viewport.current) observer.observe(viewport.current)
    if (content.current) observer.observe(content.current)
    return () => observer.disconnect()
  }, [context])
  function jump() {
    const element = viewport.current
    if (!element) return
    // scrollIntoView can also move the page and adjacent layout ancestors.
    element.scrollTop = element.scrollHeight
    updateJump()
    input.current?.focus({ preventScroll: true })
  }
  return <section className="chat-pane" aria-label="채팅">
    <article ref={viewport} className="chat-history" aria-label="대화 기록" tabIndex={0} onScroll={updateJump}>
      <div ref={content} className="chat-content">{children}<span ref={end} className="conversation-end"><span className="sr-only">대화 끝</span></span></div>
    </article>
    <div className="composer-dock">
      {showJump && <button type="button" className="btn btn-icon jump-latest" aria-label="대화 맨 아래로 이동" title="대화 맨 아래로 이동" onClick={jump}><ArrowDown aria-hidden="true" /></button>}
      {composer}
    </div>
  </section>
}
