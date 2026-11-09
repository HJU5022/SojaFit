import type { Project } from '../api/projects'

export default function CircuitSummary({ project, targetRef, onTarget }: {
  project: Project; targetRef: string; onTarget: (ref: string) => void
}) {
  const parts = project.connections.parts ?? project.connections.components ?? []
  const target = parts.some(part => part.ref === targetRef) ? targetRef : ''
  return <section className="panel" aria-label="회로 요약">
    <h2>{project.name}</h2>
    <p>{project.source_kind === 'demo' ? '공개 데모 회로' : '업로드한 회로'} · 서버에서 확인한 연결 정보</p>
    <p>부품 {parts.length}개 · 넷 {project.connections.nets.length}개</p>
    <label htmlFor="target-ref">대상 부품</label>
    <select id="target-ref" value={target} onChange={event => onTarget(event.target.value)}>
      <option value="">대상을 선택하세요</option>
      {parts.map(part => <option key={part.ref} value={part.ref}>{part.ref} · {part.value || '값 없음'}</option>)}
    </select>
    {target ? <p>선택한 대상: {target}</p> : <p>검토할 부품의 참조 번호를 선택하세요.</p>}
  </section>
}
