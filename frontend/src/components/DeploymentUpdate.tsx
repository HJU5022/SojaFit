import { useEffect, useState } from 'react'

function assetVersion(page: Document) {
  const module = page.querySelector<HTMLScriptElement>('script[type="module"][src^="/assets/"]')
  if (!page.querySelector('#root') || !module) return ''
  return [page.querySelector('meta[name="sojafit-build"]')?.getAttribute('content') ?? '', module.getAttribute('src'), ...Array.from(page.querySelectorAll('link[rel="stylesheet"][href^="/assets/"]'), link => link.getAttribute('href'))].sort().join('|')
}

function pendingWork() {
  if (document.querySelector('[data-refresh-blocked="true"], dialog[open], [aria-busy="true"]')) return true
  return Array.from(document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>('input, textarea, select')).some(field => {
    if (field.closest('[data-refresh-managed], dialog:not([open])')) return false
    if (field instanceof HTMLInputElement) {
      if (field.type === 'file') return Boolean(field.files?.length)
      if (field.type === 'password' || field.type === 'email') return Boolean(field.value)
      if (field.type === 'checkbox' || field.type === 'radio') return field.checked !== field.defaultChecked
      if (['hidden', 'submit', 'button'].includes(field.type)) return false
    }
    if (field instanceof HTMLSelectElement) {
      const initial = Array.from(field.options).find(option => option.defaultSelected)?.value ?? field.options[0]?.value ?? ''
      return field.value !== initial
    }
    return field.value !== field.defaultValue
  })
}

// 초안을 저장소에 복사하거나 화면을 재마운트하지 않고 사용자가 안전하게 갱신할 때까지 기다린다.
export default function DeploymentUpdate() {
  const [available, setAvailable] = useState(false)
  const [blocked, setBlocked] = useState(false)
  useEffect(() => {
    const current = assetVersion(document)
    if (!current) return // Vite 개발 서버에는 배포된 자산 경로가 없다.
    let active = true
    let lastCheck = -Infinity
    let pending: AbortController | null = null
    let timeout: ReturnType<typeof setTimeout> | undefined
    let timer: ReturnType<typeof setTimeout>
    async function check() {
      if (document.visibilityState !== 'visible' || pending || Date.now() - lastCheck < 30_000) return
      lastCheck = Date.now()
      clearTimeout(timer)
      timer = setTimeout(() => void check(), 60_000)
      const controller = new AbortController()
      pending = controller
      timeout = setTimeout(() => { controller.abort(); if (pending === controller) pending = null }, 5_000)
      try {
        const response = await fetch('/index.html', { cache: 'no-store', credentials: 'omit', signal: controller.signal })
        if (!response.ok || response.redirected) return
        const latest = assetVersion(new DOMParser().parseFromString(await response.text(), 'text/html'))
        if (active && !controller.signal.aborted && latest) setAvailable(latest !== current)
      } catch { /* 갱신 확인 실패는 현재 작업에 영향을 주지 않는다. */ }
      finally {
        if (pending === controller) { clearTimeout(timeout); pending = null }
      }
    }
    timer = setTimeout(() => void check(), 60_000)
    const wake = () => void check()
    document.addEventListener('visibilitychange', wake)
    window.addEventListener('focus', wake)
    window.addEventListener('online', wake)
    return () => {
      active = false; clearTimeout(timer); clearTimeout(timeout); pending?.abort()
      document.removeEventListener('visibilitychange', wake)
      window.removeEventListener('focus', wake); window.removeEventListener('online', wake)
    }
  }, [])
  useEffect(() => {
    if (!available) return
    const update = () => setBlocked(pendingWork())
    update()
    const observer = new MutationObserver(update)
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-refresh-blocked', 'open', 'aria-busy'] })
    document.addEventListener('input', update); document.addEventListener('change', update)
    return () => { observer.disconnect(); document.removeEventListener('input', update); document.removeEventListener('change', update) }
  }, [available])
  if (!available) return null
  return <aside className="deployment-update notice" role="status" aria-label="화면 업데이트">
    <div><strong>새 버전이 준비되었습니다.</strong><p>{blocked ? '작성 중인 내용·첨부를 저장하거나 정리하고, 진행 중인 작업과 열린 창을 마친 뒤 적용해 주세요.' : '현재 주소에서 최신 화면을 불러올 수 있습니다.'}</p></div>
    <button type="button" className="btn btn-primary" disabled={blocked} onClick={() => {
      if (pendingWork()) { setBlocked(true); return }
      window.location.reload()
    }}>새 버전 적용</button>
  </aside>
}
