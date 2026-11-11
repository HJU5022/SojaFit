import { useEffect } from 'react'

type Axis = 'x' | 'y'

export default function useOverlayScrollbar() {
  useEffect(() => {
    const edgeSize = 14
    const track = document.createElement('div')
    const thumb = document.createElement('div')
    track.className = 'overlay-scrollbar'
    thumb.className = 'overlay-scrollbar-thumb'
    track.setAttribute('aria-hidden', 'true')
    track.append(thumb)
    document.body.append(track)

    let active: HTMLElement | null = null
    let axis: Axis = 'y'
    let dragging = false
    let dragStart = 0
    let scrollStart = 0

    const metrics = () => {
      if (!active) return null
      const rect = active.getBoundingClientRect()
      const viewportStart = axis === 'y' ? Math.max(0, rect.top) : Math.max(0, rect.left)
      const viewportEnd = axis === 'y' ? Math.min(window.innerHeight, rect.bottom) : Math.min(window.innerWidth, rect.right)
      const trackLength = Math.max(0, viewportEnd - viewportStart)
      const clientLength = axis === 'y' ? active.clientHeight : active.clientWidth
      const scrollLength = axis === 'y' ? active.scrollHeight : active.scrollWidth
      const scrollPosition = axis === 'y' ? active.scrollTop : active.scrollLeft
      const thumbLength = Math.min(trackLength, Math.max(36, trackLength * clientLength / scrollLength))
      const maxScroll = Math.max(0, scrollLength - clientLength)
      const maxTravel = Math.max(0, trackLength - thumbLength)
      const thumbPosition = maxScroll > 0 ? maxTravel * scrollPosition / maxScroll : 0
      return { rect, viewportStart, trackLength, thumbLength, maxScroll, maxTravel, thumbPosition }
    }

    const render = () => {
      const value = metrics()
      if (!value || value.trackLength <= 0) {
        track.classList.remove('active')
        return
      }
      track.dataset.axis = axis
      if (axis === 'y') {
        track.style.left = `${Math.min(window.innerWidth, value.rect.right) - 10}px`
        track.style.top = `${value.viewportStart}px`
        track.style.width = '10px'
        track.style.height = `${value.trackLength}px`
        thumb.style.left = '2px'
        thumb.style.top = `${value.thumbPosition}px`
        thumb.style.width = '6px'
        thumb.style.height = `${value.thumbLength}px`
      } else {
        track.style.left = `${value.viewportStart}px`
        track.style.top = `${Math.min(window.innerHeight, value.rect.bottom) - 10}px`
        track.style.width = `${value.trackLength}px`
        track.style.height = '10px'
        thumb.style.left = `${value.thumbPosition}px`
        thumb.style.top = '2px'
        thumb.style.width = `${value.thumbLength}px`
        thumb.style.height = '6px'
      }
      track.classList.add('active')
    }

    const hide = () => {
      if (dragging) return
      active = null
      track.classList.remove('active')
    }

    const findAtEdge = (event: PointerEvent) => {
      const candidates = new Set<HTMLElement>()
      for (const node of document.elementsFromPoint(event.clientX, event.clientY)) {
        let current: HTMLElement | null = node instanceof HTMLElement ? node : node.parentElement
        while (current) {
          candidates.add(current)
          current = current.parentElement
        }
      }
      if (document.scrollingElement instanceof HTMLElement) candidates.add(document.scrollingElement)
      for (const element of candidates) {
        const rect = element.getBoundingClientRect()
        const style = getComputedStyle(element)
        const root = element === document.scrollingElement
        const vertical = element.scrollHeight > element.clientHeight && (root || /(auto|scroll|overlay)/.test(style.overflowY))
        const horizontal = element.scrollWidth > element.clientWidth && (root || /(auto|scroll|overlay)/.test(style.overflowX))
        if (vertical && event.clientX >= rect.right - edgeSize && event.clientX <= rect.right) return { element, axis: 'y' as const }
        if (horizontal && event.clientY >= rect.bottom - edgeSize && event.clientY <= rect.bottom) return { element, axis: 'x' as const }
      }
      return null
    }

    const onPointerMove = (event: PointerEvent) => {
      if (dragging) {
        const value = metrics()
        if (!active || !value || value.maxTravel <= 0) return
        const pointer = axis === 'y' ? event.clientY : event.clientX
        const next = scrollStart + (pointer - dragStart) * value.maxScroll / value.maxTravel
        if (axis === 'y') active.scrollTop = next
        else active.scrollLeft = next
        render()
        return
      }
      if (event.target === track || event.target === thumb) return
      const found = findAtEdge(event)
      if (!found) return hide()
      active = found.element
      axis = found.axis
      render()
    }

    const onPointerDown = (event: PointerEvent) => {
      if (!active) return
      const value = metrics()
      if (!value || value.maxTravel <= 0) return
      const pointer = axis === 'y' ? event.clientY : event.clientX
      const trackStart = axis === 'y' ? track.getBoundingClientRect().top : track.getBoundingClientRect().left
      const thumbStart = trackStart + value.thumbPosition
      if (pointer < thumbStart || pointer > thumbStart + value.thumbLength) {
        const next = Math.max(0, Math.min(value.maxTravel, pointer - trackStart - value.thumbLength / 2))
        if (axis === 'y') active.scrollTop = next * value.maxScroll / value.maxTravel
        else active.scrollLeft = next * value.maxScroll / value.maxTravel
        render()
      }
      dragging = true
      dragStart = pointer
      scrollStart = axis === 'y' ? active.scrollTop : active.scrollLeft
      event.preventDefault()
    }

    const onPointerUp = () => { dragging = false }
    const onScroll = () => { if (active) render() }
    track.addEventListener('pointerdown', onPointerDown)
    window.addEventListener('pointermove', onPointerMove, { passive: false })
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', render)
    window.addEventListener('blur', hide)
    return () => {
      track.removeEventListener('pointerdown', onPointerDown)
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('pointerup', onPointerUp)
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', render)
      window.removeEventListener('blur', hide)
      track.remove()
    }
  }, [])
}
