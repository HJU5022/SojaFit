import { useEffect, useState } from 'react'
import type { DemoCircuit, Project } from '../api/projects'
import type { JudgementDto, RoleLabel } from '../api/conversations'
import CircuitContextDiagram from './CircuitContextDiagram'
import CircuitSchematic from './CircuitSchematic'
import { buildCircuitContext } from './circuitContext'

export default function CircuitSummary({ project, demo, targetRef, onTarget, judgement, roleLabels = [], missing = [], providedConditions = '', analysisStatus = 'idle', readOnly = false }: {
  project: Project; targetRef: string; onTarget: (ref: string) => void
  demo?: DemoCircuit
  readOnly?: boolean
  judgement?: JudgementDto
  roleLabels?: RoleLabel[]
  missing?: string[]
  providedConditions?: string
  analysisStatus?: 'idle' | 'running' | 'requires_input' | 'completed' | 'refused' | 'failed'
}) {
  const [view, setView] = useState<'original' | 'concept'>('original')
  useEffect(() => { setView('original') }, [project.id])
  const hasOriginal = project.source_kind === 'demo' && demo?.id === project.demo_id && Boolean(demo.schematic)
  const parts = project.connections.parts ?? project.connections.components ?? []
  const target = parts.some(part => part.ref === targetRef) ? targetRef : ''
  const context = targetRef ? buildCircuitContext(project, targetRef, judgement, roleLabels, missing, providedConditions) : null
  return <section className="panel" aria-label="회로 요약">
    <h2>{project.name}</h2>
    <p>{project.source_kind === 'demo' ? '공개 데모 회로' : '업로드한 회로'} · 서버에서 확인한 연결 정보</p>
    <p>부품 {parts.length}개 · 넷 {project.connections.nets.length}개</p>
    <label htmlFor="target-ref">대상 부품</label>
    <select id="target-ref" value={target} disabled={readOnly} onChange={event => onTarget(event.target.value)}>
      <option value="">대상을 선택하세요</option>
      {parts.map(part => <option key={part.ref} value={part.ref}>{part.ref} · {part.value || '값 없음'}</option>)}
    </select>
    {target && <p>선택한 대상: {target}</p>}
    {hasOriginal && <div className="circuit-view-tabs" role="tablist" aria-label="회로 보기" onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
      event.preventDefault()
      const next = event.key === 'Home' ? 'original' : event.key === 'End' ? 'concept' : view === 'original' ? 'concept' : 'original'
      setView(next)
      event.currentTarget.querySelector<HTMLButtonElement>(`#circuit-${next}-tab`)?.focus()
    }}>
      <button id="circuit-original-tab" role="tab" tabIndex={view === 'original' ? 0 : -1} aria-selected={view === 'original'} aria-controls="circuit-visual-panel" onClick={() => setView('original')}>원본 회로도</button>
      <button id="circuit-concept-tab" role="tab" tabIndex={view === 'concept' ? 0 : -1} aria-selected={view === 'concept'} aria-controls="circuit-visual-panel" onClick={() => setView('concept')}>연결 개념도</button>
    </div>}
    {project.source_kind === 'upload' && <p>업로드한 넷리스트에는 원본 회로도 이미지와 부품 좌표가 포함되지 않습니다.</p>}
    <div id="circuit-visual-panel" role={hasOriginal ? 'tabpanel' : undefined} aria-labelledby={hasOriginal ? `circuit-${view}-tab` : undefined}>
    {hasOriginal && view === 'original' ? <CircuitSchematic key={project.id} schematic={demo!.schematic} circuitName={demo!.name} targetRef={target} /> : target ? <CircuitContextDiagram key={target} context={context!} analysisStatus={analysisStatus} />
      : targetRef && context ? <CircuitContextDiagram key={targetRef} context={context} analysisStatus={analysisStatus} />
        : <p>검토할 부품의 참조 번호를 선택하세요.</p>}
    </div>
  </section>
}
