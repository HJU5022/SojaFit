import { useMemo, useState } from 'react'
import type { CircuitContext, ContextNode } from './circuitContext'

type AnalysisStatus = 'idle' | 'running' | 'requires_input' | 'completed' | 'refused' | 'failed'
type Point = { x: number; y: number }

function ring(nodes: ContextNode[], radiusX: number, radiusY: number, offset = -Math.PI / 2) {
  return new Map(nodes.map((node, index) => {
    const angle = offset + (Math.PI * 2 * index) / Math.max(nodes.length, 1)
    return [node.ref, { x: 300 + Math.cos(angle) * radiusX, y: 190 + Math.sin(angle) * radiusY }] as const
  }))
}

function analysisLabel(context: CircuitContext, status: AnalysisStatus) {
  if (context.state === 'no_connections') return '연결 정보 없음'
  if (context.state === 'target_not_found') return '대상 부품을 찾을 수 없음'
  if (status === 'failed' || status === 'refused') return '분석 오류'
  if (status === 'running') return 'loading'
  if (status === 'requires_input' || context.missing.length > 0) return '사용 조건 부족'
  if (status === 'completed') return '판정 완료'
  return '역할 분석 전'
}

export default function CircuitContextDiagram({ context, analysisStatus = 'idle' }: {
  context: CircuitContext
  analysisStatus?: AnalysisStatus
}) {
  const [selectedRef, setSelectedRef] = useState(context.target.ref)
  const positions = useMemo(() => {
    const direct = ring(context.nodes.filter(node => node.depth === 1), 115, 72)
    const outer = ring(context.nodes.filter(node => node.depth === 2), 235, 145, -Math.PI / 3)
    return new Map<string, Point>([[context.target.ref, { x: 300, y: 190 }], ...direct, ...outer])
  }, [context])
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
      <svg className="context-diagram" viewBox="0 0 600 380" role="img" aria-label={`${context.target.ref} 주변 연결 개념도`}>
        {context.nets.flatMap(net => {
          const refs = net.nodeRefs.filter(ref => positions.has(ref))
          const anchor = net.depth === 1 ? context.target.ref : refs.find(ref => context.nodes.find(node => node.ref === ref)?.depth === 1)
          if (!anchor) return []
          const start = positions.get(anchor)!
          return refs.filter(ref => ref !== anchor).map((ref, edgeIndex) => {
            const end = positions.get(ref)!
            return <g key={`${net.name}-${ref}-${edgeIndex}`} className={`context-edge depth-${net.depth}`}>
              <line x1={start.x} y1={start.y} x2={end.x} y2={end.y} />
              {edgeIndex === 0 && <text x={(start.x + end.x) / 2} y={(start.y + end.y) / 2 - 6}>{net.name}</text>}
            </g>
          })
        })}
        <g role="button" tabIndex={0} aria-label={`${context.target.ref} 노드`} className="context-node target"
          onClick={() => setSelectedRef(context.target.ref)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') setSelectedRef(context.target.ref) }}>
          <rect x="246" y="159" width="108" height="62" rx="10" />
          <text x="300" y="195">{context.target.ref} / {context.target.value || '정보 필요'}</text>
        </g>
        {context.nodes.map(node => {
          const point = positions.get(node.ref)!
          return <g key={node.ref} role="button" tabIndex={0} aria-label={`${node.ref} 노드`}
            className={`context-node depth-${node.depth}${selectedRef === node.ref ? ' selected' : ''}`}
            onClick={() => setSelectedRef(node.ref)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') setSelectedRef(node.ref) }}>
            <rect x={point.x - 36} y={point.y - 22} width="72" height="44" rx="8" />
            <text x={point.x} y={point.y + 5}>{node.ref}</text>
          </g>
        })}
      </svg>
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
