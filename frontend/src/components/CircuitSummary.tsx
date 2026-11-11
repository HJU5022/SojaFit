import type { Project } from '../api/projects'
import type { JudgementDto, RoleLabel } from '../api/conversations'
import CircuitContextDiagram from './CircuitContextDiagram'
import { buildCircuitContext } from './circuitContext'

export default function CircuitSummary({ project, targetRef, onTarget, judgement, roleLabels = [], missing = [], providedConditions = '', analysisStatus = 'idle', readOnly = false }: {
  project: Project; targetRef: string; onTarget: (ref: string) => void
  judgement?: JudgementDto
  roleLabels?: RoleLabel[]
  missing?: string[]
  providedConditions?: string
  readOnly?: boolean
  analysisStatus?: 'idle' | 'running' | 'requires_input' | 'completed' | 'refused' | 'failed'
}) {
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
    {target ? <><p>선택한 대상: {target}</p><CircuitContextDiagram key={target} context={context!} analysisStatus={analysisStatus} /></>
      : targetRef && context ? <CircuitContextDiagram key={targetRef} context={context} analysisStatus={analysisStatus} />
        : <p>검토할 부품의 참조 번호를 선택하세요.</p>}
  </section>
}
