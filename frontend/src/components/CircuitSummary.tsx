import { useEffect, useState } from 'react'
import type { DemoCircuit, Project } from '../api/projects'
import type { JudgementDto, RoleLabel } from '../api/conversations'
import CircuitContextDiagram from './CircuitContextDiagram'
import CircuitSchematic from './CircuitSchematic'
import { buildCircuitContext } from './circuitContext'

export default function CircuitSummary({ project, demo, targetRef, judgement, roleLabels = [], missing = [], providedConditions = '', analysisStatus = 'idle' }: {
  project: Project; targetRef: string
  demo?: DemoCircuit
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
  return <section className="panel circuit-summary" aria-label="회로 보기">
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
    <div id="circuit-visual-panel" role={hasOriginal ? 'tabpanel' : undefined} aria-labelledby={hasOriginal ? `circuit-${view}-tab` : undefined}>
    {hasOriginal && view === 'original' ? <CircuitSchematic key={project.id} schematic={demo!.schematic} circuitName={demo!.name} targetRef={target} /> : target ? <CircuitContextDiagram key={target} context={context!} analysisStatus={analysisStatus} />
      : targetRef && context ? <CircuitContextDiagram key={targetRef} context={context} analysisStatus={analysisStatus} />
        : <p>현재 프로젝트에서 검토할 부품을 선택하세요.</p>}
    </div>
  </section>
}
