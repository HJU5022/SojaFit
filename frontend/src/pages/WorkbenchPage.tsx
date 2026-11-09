import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { getProject } from '../api/projects'
import type { Project } from '../api/projects'
import { errorMessage } from '../api/client'
import ProjectSidebar from '../components/ProjectSidebar'
import CircuitSetup from '../components/CircuitSetup'
import CircuitSummary from '../components/CircuitSummary'
import PricePanel from '../components/PricePanel'

export default function WorkbenchPage() {
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const rawId = params.get('projectId') ?? ''
  const id = /^[1-9][0-9]*$/.test(rawId) && Number.isSafeInteger(Number(rawId)) ? Number(rawId) : null
  const targetRef = params.get('targetRef') ?? ''
  const selection = useRef({ signature: params.toString(), version: 0 })
  if (selection.current.signature !== params.toString()) {
    selection.current = { signature: params.toString(), version: selection.current.version + 1 }
  }
  const version = selection.current.version
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      // 다른 로그인 세션이 소유 프로젝트 캐시를 이어받지 않게 즉시 폐기한다.
      client.removeQueries({ queryKey: ['projects'], exact: true })
      client.removeQueries({ queryKey: ['project'] })
      client.removeQueries({ queryKey: ['demo-circuits'], exact: true })
    }
  }, [client])
  const detail = useQuery({ queryKey: ['project', id], queryFn: ({ signal }) => getProject(id!, signal), enabled: id !== null, retry: false, gcTime: 0 })
  function selectProject(projectId: number) {
    selection.current.version++
    setParams(current => { const next = new URLSearchParams(current); next.set('projectId', String(projectId)); next.delete('targetRef'); return next })
  }
  function created(project: Project) {
    if (mounted.current && selection.current.version === version) selectProject(project.id)
  }
  function deleted(projectId: number) {
    if (!mounted.current) return
    const next = new URLSearchParams(selection.current.signature)
    if (next.get('projectId') === String(projectId)) {
      next.delete('projectId'); next.delete('targetRef'); setParams(next, { replace: true })
    }
  }
  return <><h1>회로 작업대</h1><p>회로의 역할과 부품 대체 근거를 함께 검토합니다.</p>
    <div className="workbench-grid">
      <ProjectSidebar selectedId={id} project={detail.isError ? undefined : detail.data} onSelect={selectProject} onDeleted={deleted} />
      <div className="workbench-main">
        <CircuitSetup onCreated={created} />
        {id !== null && detail.isPending && <p role="status">회로를 불러오는 중입니다.</p>}
        {detail.error ? <p role="alert">{errorMessage(detail.error)}</p> : detail.data && <CircuitSummary project={detail.data} targetRef={targetRef} onTarget={ref => {
          setParams(current => { const next = new URLSearchParams(current); if (ref) next.set('targetRef', ref); else next.delete('targetRef'); return next })
        }} />}
        <PricePanel parts={[]} />
      </div>
    </div>
  </>
}
