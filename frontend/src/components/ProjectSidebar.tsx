import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteProject, listProjects, renameProject } from '../api/projects'
import type { Project } from '../api/projects'
import { errorMessage } from '../api/client'

export default function ProjectSidebar({ selectedId, project, onSelect, onDeleted }: {
  selectedId: number | null; project?: Project; onSelect: (id: number) => void; onDeleted: (id: number) => void
}) {
  const projects = useQuery({ queryKey: ['projects'], queryFn: ({ signal }) => listProjects(signal), retry: false, gcTime: 0 })
  return <aside className="panel project-sidebar" aria-label="내 프로젝트">
    <h2>내 프로젝트</h2>
    {projects.isPending && <p role="status">프로젝트를 불러오는 중입니다.</p>}
    {projects.error ? <p role="alert">{errorMessage(projects.error)}</p> : <ul className="project-list">
      {projects.data?.map(project => <li key={project.id}><button aria-current={selectedId === project.id ? 'true' : undefined} onClick={() => onSelect(project.id)}>{project.name}</button></li>)}
    </ul>}
    {projects.data?.length === 0 && <p>프로젝트가 없습니다. 데모 또는 파일로 시작하세요.</p>}
    {project && <ProjectActions key={project.id} project={project} onDeleted={onDeleted} />}
  </aside>
}
function ProjectActions({ project, onDeleted }: { project: Project; onDeleted: (id: number) => void }) {
  const client = useQueryClient()
  const [name, setName] = useState(project.name)
  const [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function change(remove = false) {
    if (busy || (!remove && !name.trim())) return
    setBusy(true); setError(null)
    try {
      if (remove) {
        await deleteProject(project.id)
        onDeleted(project.id)
        await client.cancelQueries({ queryKey: ['project', project.id], exact: true })
        client.removeQueries({ queryKey: ['project', project.id], exact: true })
      } else await renameProject(project.id, name)
      void client.invalidateQueries({ queryKey: ['projects'], exact: true })
      void client.invalidateQueries({ queryKey: ['project', project.id], exact: true, refetchType: remove ? 'none' : 'active' })
    } catch (error) { setError(error) }
    finally { setBusy(false) }
  }
  return <div className="project-actions">
    <form onSubmit={event => { event.preventDefault(); void change() }}>
      <label htmlFor="rename-project">프로젝트 이름 변경</label>
      <input id="rename-project" maxLength={200} value={name} onChange={event => setName(event.target.value)} disabled={busy} />
      <button disabled={busy || !name.trim()}>이름 저장</button>
    </form>
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    <button className="secondary" disabled={busy} onClick={() => setConfirm(true)}>프로젝트 삭제</button>
    {confirm && <div role="group" aria-label="프로젝트 삭제 확인" className="delete-confirmation">
      <p>“{project.name}” 프로젝트를 삭제할까요? 이 작업은 되돌릴 수 없습니다.</p>
      <button className="danger" disabled={busy} onClick={() => void change(true)}>삭제 확인</button>
      <button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>취소</button>
    </div>}
  </div>
}
