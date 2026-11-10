import { useId, useLayoutEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export default function AccessibleDialog({ title, children, onClose, dismissible = true, closeOnBackdrop = true, className = '' }: {
  title: string
  children: ReactNode
  onClose: () => void
  dismissible?: boolean
  closeOnBackdrop?: boolean
  className?: string
}) {
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const restore = useRef<HTMLElement | null>(document.activeElement as HTMLElement | null)
  const close = useRef(onClose)
  close.current = onClose
  useLayoutEffect(() => {
    const root = panel.current
    const focusables = () => Array.from(root?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])
    ;(focusables()[0] ?? root)?.focus()
    function keydown(event: KeyboardEvent) {
      if (event.key === 'Escape' && dismissible) { event.preventDefault(); close.current(); return }
      if (event.key !== 'Tab') return
      const items = focusables()
      if (items.length === 0) { event.preventDefault(); root?.focus(); return }
      const first = items[0]; const last = items[items.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
    document.addEventListener('keydown', keydown)
    return () => { document.removeEventListener('keydown', keydown); restore.current?.focus() }
  }, [dismissible])
  return createPortal(<div className="dialog-backdrop" onMouseDown={event => {
    if (dismissible && closeOnBackdrop && event.target === event.currentTarget) onClose()
  }}>
    <div ref={panel} className={`dialog-panel ${className}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
      <div className="dialog-heading"><h2 id={titleId}>{title}</h2>{dismissible && <button className="icon-button secondary" aria-label="닫기" onClick={onClose}>×</button>}</div>
      {children}
    </div>
  </div>, document.body)
}
