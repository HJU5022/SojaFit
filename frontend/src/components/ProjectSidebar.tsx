import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteProject, listProjects, renameProject } from '../api/projects'
import type { Project } from '../api/projects'
import { errorMessage } from '../api/client'

export default function ProjectSidebar({ selectedId, project, onSelect, onDeleted, targetRef = '', onTarget, busy = false, targetLocked = false }: {
  selectedId: number | null; project?: Project; onSelect: (id: number) => void; onDeleted: (id: number) => void
  targetRef?: string; onTarget?: (ref: string) => void; busy?: boolean; targetLocked?: boolean
}) {
  const projects = useQuery({ queryKey: ['projects'], queryFn: ({ signal }) => listProjects(signal), retry: false, gcTime: 0 })
  const selected = project?.id === selectedId ? project : undefined
  const parts = selected?.connections.parts ?? selected?.connections.components ?? []
  return <aside className={onTarget ? 'project-sidebar project-manager' : 'panel project-sidebar'} aria-label="내 프로젝트">
    <nav className="project-manager-list" aria-label="프로젝트 목록">
    {!onTarget && <h2>내 프로젝트</h2>}
    {onTarget && <h3>프로젝트 목록</h3>}
    {projects.isPending && <p role="status">프로젝트를 불러오는 중입니다.</p>}
    {projects.error ? <div><p role="alert">{errorMessage(projects.error)}</p><button className="secondary" onClick={() => void projects.refetch()}>프로젝트 다시 불러오기</button></div> : <ul className="project-list">
      {projects.data?.map(project => <li key={project.id}><button disabled={busy} aria-current={selectedId === project.id ? 'true' : undefined} onClick={() => onSelect(project.id)}>{project.name}</button></li>)}
    </ul>}
    {projects.data?.length === 0 && <p>프로젝트가 없습니다. 데모 또는 파일로 시작하세요.</p>}
    </nav>
    <section className="project-manager-settings" aria-label="선택 프로젝트 설정">
    {selected && onTarget && <div className="project-manager-summary">
      <h3>현재 프로젝트</h3>
      <p className="project-manager-name">{selected.name}</p>
      <p>{selected.source_kind === 'demo' ? '데모 회로' : '업로드 회로'} · 부품 {parts.length}개 · 넷 {selected.connections.nets.length}개</p>
    </div>}
    {selected && onTarget && <div className="project-target-selection">
      <label htmlFor="project-target-ref">분석할 부품</label>
      <select id="project-target-ref" value={parts.some(part => part.ref === targetRef) ? targetRef : ''} disabled={busy || targetLocked || parts.length === 0} onChange={event => onTarget(event.target.value)}>
        <option value="">부품을 선택하세요</option>
        {parts.map(part => <option key={part.ref} value={part.ref}>{part.ref} · {part.value || '값 없음'}</option>)}
      </select>
      {parts.length === 0 && <p>선택할 수 있는 부품이 없습니다.</p>}
      {targetLocked && <p>저장된 대화의 대상은 고정됩니다. 새 대화에서 변경하세요.</p>}
    </div>}
    {selected && <ProjectActions key={selected.id} project={selected} onDeleted={onDeleted} />}
    {!selected && onTarget && <p className="project-manager-empty">왼쪽에서 관리할 프로젝트를 선택하세요.</p>}
    </section>
  </aside>
}
export function ProjectActions({ project, onDeleted, deleteOnly = false, onCancel, onBusyChange }: {
  project: Pick<Project, 'id' | 'name'>; onDeleted: (id: number) => void
  deleteOnly?: boolean; onCancel?: () => void; onBusyChange?: (busy: boolean) => void
}) {
  const client = useQueryClient()
  const [name, setName] = useState(project.name)
  const [confirm, setConfirm] = useState(deleteOnly)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const requests = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    requests.current = controller
    return () => { controller.abort(); onBusyChange?.(false) }
  }, [onBusyChange])
  async function change(remove = false) {
    const controller = requests.current
    if (busy || !controller || controller.signal.aborted || (!remove && !name.trim())) return
    setBusy(true); setError(null); onBusyChange?.(true)
    try {
      if (remove) {
        await deleteProject(project.id, controller.signal)
        if (controller.signal.aborted) return
        await client.cancelQueries({ queryKey: ['project', project.id], exact: true })
        if (controller.signal.aborted) return
        client.removeQueries({ queryKey: ['project', project.id], exact: true })
      } else await renameProject(project.id, name, controller.signal)
      if (controller.signal.aborted) return
      void client.invalidateQueries({ queryKey: ['projects'], exact: true })
      void client.invalidateQueries({ queryKey: ['project', project.id], exact: true, refetchType: remove ? 'none' : 'active' })
      if (remove) onDeleted(project.id)
    } catch (error) { if (!controller.signal.aborted) setError(error) }
    finally { if (!controller.signal.aborted) { setBusy(false); onBusyChange?.(false) } }
  }
  return <div className={deleteOnly ? 'project-delete-dialog' : 'project-actions'}>
    {!deleteOnly && <form onSubmit={event => { event.preventDefault(); void change() }}>
      <label htmlFor="rename-project">프로젝트 이름 변경</label>
      <div className="project-rename-row">
      <input id="rename-project" maxLength={200} value={name} onChange={event => setName(event.target.value)} disabled={busy} />
      <button className="secondary" disabled={busy || !name.trim()}>이름 저장</button>
      </div>
    </form>}
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <div className="project-delete-area">
    {!deleteOnly && <button className="secondary project-delete-button" disabled={busy} onClick={() => setConfirm(true)}>프로젝트 삭제</button>}
    {confirm && <div role="group" aria-label="프로젝트 삭제 확인" className="delete-confirmation">
      <p>“{project.name}” 프로젝트와 연결된 기록을 삭제할까요? 이 작업은 되돌릴 수 없습니다.</p>
      <button className="danger" disabled={busy} onClick={() => void change(true)}>삭제 확인</button>
      <button className="secondary" disabled={busy} onClick={() => { setConfirm(false); onCancel?.() }}>취소</button>
    </div>}
    </div>
  </div>
}
