import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CircuitContext } from './circuitContext'
import { buildLayoutGraph, fallbackLayout, type LayoutPoint, type LayoutedNode } from './circuitLayout'
import { requestCircuitLayout } from './circuitLayoutClient'

type AnalysisStatus = 'idle' | 'running' | 'requires_input' | 'completed' | 'refused' | 'failed'

function analysisLabel(context: CircuitContext, status: AnalysisStatus) {
  if (context.state === 'no_connections') return '연결 정보 없음'
  if (context.state === 'target_not_found') return '대상 부품을 찾을 수 없음'
  if (status === 'failed' || status === 'refused') return '분석 오류'
  if (status === 'running') return 'loading'
  if (status === 'requires_input' || context.missing.length > 0) return '사용 조건 부족'
  if (status === 'completed') return '판정 완료'
  return '역할 분석 전'
}

function pathData(points: LayoutPoint[]) {
  return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')
}

function nodeCenter(node: LayoutedNode) {
  return { x: node.x + node.width / 2, y: node.y + node.height / 2 }
}

export default function CircuitContextDiagram({ context, analysisStatus = 'idle' }: {
  context: CircuitContext
  analysisStatus?: AnalysisStatus
}) {
  const [selectedRef, setSelectedRef] = useState(context.target.ref)
  const [page, setPage] = useState(0)
  const [zoom, setZoom] = useState(100)
  const zoomValue = useRef(100)
  const [dragging, setDragging] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)
  const anchor = useRef<{ x: number; y: number; u: number; v: number } | null>(null)
  const drag = useRef<{ pointerId: number; target: Element; x: number; y: number; left: number; top: number } | null>(null)
  const dragged = useRef(false)
  const graph = useMemo(() => buildLayoutGraph(context, page), [context, page])
  const [layout, setLayout] = useState(() => fallbackLayout(graph))
  const [layoutSource, setLayoutSource] = useState<'fallback' | 'worker'>('fallback')
  function resetView() {
    anchor.current = null; zoomValue.current = 100; dragged.current = false
    if (drag.current?.target.hasPointerCapture?.(drag.current.pointerId)) drag.current.target.releasePointerCapture(drag.current.pointerId)
    drag.current = null; setDragging(false)
    setZoom(100)
    if (viewport.current) { viewport.current.scrollLeft = 0; viewport.current.scrollTop = 0 }
  }
  useEffect(resetView, [context.target.ref, context.circuitName, graph.page])

  function changeZoom(step: number, clientX?: number, clientY?: number) {
    const element = viewport.current
    const next = Math.max(50, Math.min(300, zoomValue.current + step))
    if (!element || next === zoomValue.current) return
    const box = element.getBoundingClientRect()
    const image = element.querySelector('svg')!.getBoundingClientRect()
    const x = clientX === undefined ? element.clientWidth / 2 : clientX - box.left - element.clientLeft
    const y = clientY === undefined ? element.clientHeight / 2 : clientY - box.top - element.clientTop
    anchor.current = image.width && image.height ? { x, y, u: (element.scrollLeft + x) / image.width, v: (element.scrollTop + y) / image.height } : null
    zoomValue.current = next; setZoom(next)
  }
  useLayoutEffect(() => {
    const element = viewport.current
    if (!element || !anchor.current) return
    const image = element.querySelector('svg')!.getBoundingClientRect()
    element.scrollLeft = anchor.current.u * image.width - anchor.current.x
    element.scrollTop = anchor.current.v * image.height - anchor.current.y
    anchor.current = null
  }, [zoom])
  useEffect(() => {
    const element = viewport.current
    if (!element) return
    setDragging(false)
    function wheel(event: WheelEvent) {
      if (!event.deltaY || event.ctrlKey || event.metaKey) return
      event.preventDefault()
      changeZoom(event.deltaY < 0 ? 25 : -25, event.clientX, event.clientY)
    }
    element.addEventListener('wheel', wheel, { passive: false })
    return () => {
      element.removeEventListener('wheel', wheel)
      const active = drag.current
      drag.current = null
      if (active?.target.hasPointerCapture?.(active.pointerId)) active.target.releasePointerCapture(active.pointerId)
    }
  }, [context.state])

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || drag.current) return
    const target = event.target as Element
    drag.current = { pointerId: event.pointerId, target, x: event.clientX, y: event.clientY, left: event.currentTarget.scrollLeft, top: event.currentTarget.scrollTop }
    dragged.current = false
    target.setPointerCapture?.(event.pointerId)
  }
  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    const active = drag.current
    if (!active || active.pointerId !== event.pointerId) return
    const dx = event.clientX - active.x, dy = event.clientY - active.y
    if (!dragged.current && Math.hypot(dx, dy) < 4) return
    if (!dragged.current) { dragged.current = true; setDragging(true) }
    event.preventDefault()
    event.currentTarget.scrollLeft = active.left - dx
    event.currentTarget.scrollTop = active.top - dy
  }
  function stopPan(event: React.PointerEvent<HTMLDivElement>) {
    const active = drag.current
    if (!active || active.pointerId !== event.pointerId) return
    drag.current = null; setDragging(false)
    if (active.target.hasPointerCapture?.(event.pointerId)) active.target.releasePointerCapture(event.pointerId)
  }

  useEffect(() => {
    let active = true
    setLayout(fallbackLayout(graph))
    setLayoutSource('fallback')
    requestCircuitLayout(graph).then(result => {
      if (active) {
        setLayout(result)
        setLayoutSource('worker')
      }
    }).catch(() => {
      if (active) setLayout(fallbackLayout(graph))
    })
    return () => { active = false }
  }, [graph])

  const selected = selectedRef === context.target.ref
    ? context.target
    : context.nodes.find(node => node.ref === selectedRef) ?? context.target
  const status = analysisLabel(context, analysisStatus)

  if (context.state !== 'ready') return <div className="circuit-context-state" role="status">
    <strong>{status}</strong>
    <p>실제 회로도가 아닌 대상 부품 주변 연결 개념도입니다.</p>
  </div>

  return <section className="circuit-context" aria-labelledby="circuit-context-heading">
    <div className="context-heading-row">
      <div><h3 id="circuit-context-heading">교체 대상 부품 주변 연결</h3><p>{context.circuitName}</p></div>
      <span role="status" className={`context-status context-status-${analysisStatus}`}>{status}</span>
    </div>
    <div className="context-layout">
      <div className="context-canvas-wrap">
        <div className="context-diagram-frame">
        <div className="context-view-toolbar" role="group" aria-label="연결 개념도 보기 도구">
          <span className="schematic-zoom-level" aria-label="연결 개념도 배율" aria-live="polite">{zoom}%</span>
          <button type="button" className="secondary compact" aria-label="연결 개념도 화면에 맞춤" title="화면에 맞춤" onClick={resetView}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
              <path d="M9 4H4v5m11-5h5v5M4 15v5h5m11-5v5h-5" />
              <rect x="8" y="8" width="8" height="8" rx="1" />
            </svg>
          </button>
        </div>
        <div ref={viewport} className={`context-diagram-scroll${dragging ? ' dragging' : ''}`} role="region" aria-label="연결 개념도 확대 및 이동" tabIndex={0}
          onPointerDown={startPan} onPointerMove={movePan} onPointerUp={stopPan} onPointerCancel={stopPan} onLostPointerCapture={stopPan}
          onClickCapture={event => { if (dragged.current && event.detail > 0) { event.preventDefault(); event.stopPropagation(); dragged.current = false } }}
          onKeyDown={event => { if (!event.ctrlKey && !event.metaKey && !event.altKey && ['+', '=', '-'].includes(event.key)) { event.preventDefault(); changeZoom(event.key === '-' ? -25 : 25) } }}>
        <svg className="context-diagram" style={{ width: `${zoom}%`, height: `${zoom}%` }} data-layout={layoutSource} viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label={`${context.target.ref} 주변 연결 개념도`}>
          {layout.edges.map(edge => <g key={edge.id} className={`context-edge depth-${edge.depth}`} data-edge={edge.id}>
            <path d={pathData(edge.points)} />
          </g>)}
          {layout.nodes.map(node => {
            const center = nodeCenter(node)
            if (node.kind === 'net') return <g key={node.id} className={`context-junction depth-${node.depth}`} data-kind="net">
              <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="17" />
              <text x={center.x} y={center.y + 4}>{node.label}</text>
            </g>
            if (node.kind === 'overflow') return <g key={node.id} className="context-overflow" data-kind="overflow">
              <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="17" />
              <text x={center.x} y={center.y + 4}>{node.label}</text>
            </g>
            const ref = node.id.slice('component:'.length)
            return <g key={node.id} role="button" tabIndex={0} aria-label={`${ref} 노드`}
              className={`context-node ${node.kind === 'target' ? 'target' : `depth-${node.depth}`}${selectedRef === ref ? ' selected' : ''}`}
              onClick={() => setSelectedRef(ref)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedRef(ref) } }}>
              <rect x={node.x} y={node.y} width={node.width} height={node.height} rx="10" />
              <text x={center.x} y={center.y + (node.value ? -3 : 5)}>{node.label}</text>
              {node.value && <text className="node-value" x={center.x} y={center.y + 15}>{node.value}</text>}
            </g>
          })}
        </svg>
        </div>
        </div>
        <p className="context-zoom-help">마우스 휠로 확대·축소하고 드래그로 이동하세요. 키보드는 +/−로 배율, 방향키로 위치를 조절합니다.</p>
        {graph.pageCount > 1 && <nav className="context-pagination" aria-label="연결 개념도 페이지">
          <button type="button" onClick={() => setPage(value => Math.max(0, value - 1))} disabled={graph.page === 0}>이전</button>
          <span>{graph.page + 1} / {graph.pageCount}</span>
          <button type="button" onClick={() => setPage(value => Math.min(graph.pageCount - 1, value + 1))} disabled={graph.page === graph.pageCount - 1}>다음</button>
        </nav>}
      </div>
      <aside className="context-details" aria-live="polite">
        <h4>선택 노드 {selected.ref}</h4>
        <dl>
          <div><dt>값</dt><dd>{selected.value || '정보 필요'}</dd></div>
          <div><dt>패키지</dt><dd>{selected.footprint || '정보 필요'}</dd></div>
        </dl>
        <div className="context-role">
          <h4>역할</h4>
          {context.role ? <><strong><span>{context.role.code} · </span><span>{context.role.name || '역할명 정보 필요'}</span></strong>
            {context.role.evidence.length > 0 ? <ul>{context.role.evidence.map(item => <li key={item}>{item}</li>)}</ul> : <p>역할 근거 정보 필요</p>}</> : <p>역할 분석 전</p>}
        </div>
      </aside>
    </div>
    <div className="context-conditions" aria-label="개념도 사용 조건">
      <h4>{context.conditions.some(item => item.code !== 'USER') ? '판정에 사용한 조건' : '사용 조건'}</h4>
      {context.conditions.length > 0 ? <ul>{context.conditions.map(item => <li key={`${item.code}-${item.value}`}>
        <strong>{item.label}</strong> {item.value}
      </li>)}</ul> : <p>판정 결과에서 확인된 사용 조건이 없습니다.</p>}
      {context.missing.length > 0 && <p>빠진 조건: {context.missing.join(', ')} · 정보 필요</p>}
      {context.candidates.length > 0 && <p>추천 후보 {context.candidates.length}개 · 판정과 데이터시트 근거 패널에서 확인</p>}
    </div>
    <p className="context-caption">실제 회로도가 아닌 대상 부품 주변 연결 개념도입니다.</p>
  </section>
}
