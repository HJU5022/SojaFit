import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode, RefObject } from 'react'
import { ArrowDown } from 'lucide-react'
import { errorMessage } from '../api/client'

export default function ChatPane({ children, composer, input, context, older }: {
  children: ReactNode; composer: ReactNode; input: RefObject<HTMLTextAreaElement | null>; context: string
  older?: { before: number | null; loading: boolean; error: unknown; load: () => Promise<void> }
}) {
  const viewport = useRef<HTMLElement>(null)
  const content = useRef<HTMLDivElement>(null)
  const end = useRef<HTMLSpanElement>(null)
  const [showJump, setShowJump] = useState(false)
  const anchor = useRef<{ element: HTMLElement; top: number } | null>(null)
  function preserveAnchor() {
    if (!anchor.current) return
    const { element, top } = anchor.current
    if (element.isConnected && viewport.current) {
      viewport.current.scrollTop += element.getBoundingClientRect().top - top
    } else anchor.current = null
  }
  useLayoutEffect(() => {
    if (older?.loading) return
    preserveAnchor()
    if (older?.before === null && document.activeElement === document.body) anchor.current?.element.querySelector<HTMLButtonElement>('.activity-turn')?.focus({ preventScroll: true })
  })
  function loadOlder() {
    const area = viewport.current
    const element = area && Array.from(area.querySelectorAll<HTMLElement>('[data-turn]')).find(item => item.getBoundingClientRect().bottom > area.getBoundingClientRect().top)
    anchor.current = element ? { element, top: element.getBoundingClientRect().top } : null
    void older?.load()
  }
  function updateJump() {
    if (viewport.current && end.current) setShowJump(end.current.getBoundingClientRect().bottom > viewport.current.getBoundingClientRect().bottom + 8)
  }
  useEffect(() => {
    anchor.current = null
    updateJump()
    if (typeof ResizeObserver === 'undefined') return
    // Past replies may grow after the page itself has arrived.
    const observer = new ResizeObserver(() => { preserveAnchor(); updateJump() })
    if (viewport.current) observer.observe(viewport.current)
    if (content.current) observer.observe(content.current)
    return () => observer.disconnect()
  }, [context])
  function jump() {
    anchor.current = null
    const element = viewport.current
    if (!element) return
    // scrollIntoView can also move the page and adjacent layout ancestors.
    element.scrollTop = element.scrollHeight
    updateJump()
    input.current?.focus({ preventScroll: true })
  }
  return <section className="chat-pane" aria-label="채팅">
    <article ref={viewport} className="chat-history" aria-label="대화 기록" tabIndex={0} onScroll={updateJump}
      onWheel={() => { anchor.current = null }} onTouchStart={() => { anchor.current = null }} onPointerDown={() => { anchor.current = null }} onKeyDown={() => { anchor.current = null }}>
      <div ref={content} className="chat-content">
        {older && older.before !== null && <div className="history-pages">
          {older.error ? <p className="notice" role="alert">이전 대화를 불러오지 못했습니다. {errorMessage(older.error)}</p> : null}
          <button type="button" className="btn" disabled={older.loading} onClick={loadOlder}>{older.loading ? '이전 대화 불러오는 중' : older.error ? '이전 대화 다시 불러오기' : '이전 대화 불러오기'}</button>
        </div>}
        {children}<span ref={end} className="conversation-end"><span className="sr-only">대화 끝</span></span></div>
    </article>
    <div className="composer-dock">
      {showJump && <button type="button" className="btn btn-icon jump-latest" aria-label="대화 맨 아래로 이동" title="대화 맨 아래로 이동" onClick={jump}><ArrowDown aria-hidden="true" /></button>}
      {composer}
    </div>
  </section>
}
