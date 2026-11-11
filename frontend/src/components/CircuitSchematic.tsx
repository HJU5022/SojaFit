import { useEffect, useRef, useState } from 'react'
import type { DemoSchematic } from '../api/projects'

const MIN_ZOOM = 50
const MAX_ZOOM = 300
const ZOOM_STEP = 25

export default function CircuitSchematic({ schematic, circuitName, targetRef }: {
  schematic?: DemoSchematic | null; circuitName: string; targetRef: string
}) {
  const [failed, setFailed] = useState(false)
  const [zoom, setZoom] = useState(100)
  const [dragging, setDragging] = useState(false)
  const viewportRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{
    pointerId: number
    startX: number
    startY: number
    scrollLeft: number
    scrollTop: number
  } | null>(null)

  const resetView = () => {
    setZoom(100)
    if (viewportRef.current) {
      viewportRef.current.scrollLeft = 0
      viewportRef.current.scrollTop = 0
    }
  }

  useEffect(() => {
    setFailed(false)
    setDragging(false)
    dragRef.current = null
    resetView()
  }, [schematic?.image_url, targetRef])

  const startPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      scrollLeft: event.currentTarget.scrollLeft,
      scrollTop: event.currentTarget.scrollTop,
    }
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setDragging(true)
    event.preventDefault()
  }

  const movePan = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    event.currentTarget.scrollLeft = drag.scrollLeft - (event.clientX - drag.startX)
    event.currentTarget.scrollTop = drag.scrollTop - (event.clientY - drag.startY)
  }

  const stopPan = (event: React.PointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
    dragRef.current = null
    setDragging(false)
  }

  if (!schematic || failed) return <p>검증된 원본 회로도를 제공할 수 없습니다.</p>
  return <figure className="circuit-schematic">
    <figcaption><h3>{circuitName} 원본 회로도</h3>{targetRef && <span className="target-badge">선택 대상 {targetRef}</span>}</figcaption>
    <div className="circuit-schematic-toolbar" role="group" aria-label="원본 회로도 보기 도구">
      <button type="button" className="secondary compact" aria-label="축소" disabled={zoom === MIN_ZOOM} onClick={() => setZoom((value) => Math.max(MIN_ZOOM, value - ZOOM_STEP))}>−</button>
      <span className="schematic-zoom-level" aria-live="polite">{zoom}%</span>
      <button type="button" className="secondary compact" aria-label="확대" disabled={zoom === MAX_ZOOM} onClick={() => setZoom((value) => Math.min(MAX_ZOOM, value + ZOOM_STEP))}>+</button>
      <button type="button" className="secondary compact" aria-label="화면에 맞춤" onClick={resetView}>맞춤</button>
    </div>
    <p className="schematic-help">확대 후 이미지를 끌어 이동하거나 스크롤할 수 있습니다.</p>
    <div
      ref={viewportRef}
      className={`circuit-schematic-scroll${dragging ? ' dragging' : ''}`}
      role="region"
      aria-label="원본 회로도 확대 및 이동"
      tabIndex={0}
      onPointerDown={startPan}
      onPointerMove={movePan}
      onPointerUp={stopPan}
      onPointerCancel={stopPan}
    >
      <img src={schematic.image_url} alt={`${circuitName} 원본 회로도`} loading="lazy" decoding="async" draggable={false} style={{ width: `${zoom}%` }} onError={() => setFailed(true)} />
    </div>
    <p>{schematic.attribution} · {schematic.license}</p>
    <div className="evidence-links">
      {schematic.original_url.startsWith('https://') && <a href={schematic.original_url} target="_blank" rel="noreferrer noopener">원본 자료 열기</a>}
      {schematic.source_repo.startsWith('https://') && <a href={schematic.source_repo} target="_blank" rel="noreferrer noopener">원본 저장소 열기</a>}
    </div>
    <p>이 이미지는 공개 원본 회로도입니다. 선택 부품의 연결 해석은 연결 개념도에서 확인하세요.</p>
  </figure>
}
