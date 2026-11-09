import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { getProject } from '../api/projects'
import type { Project } from '../api/projects'
import { listJudgeRoles } from '../api/conversations'
import type { CandidateDto, JudgementDto } from '../api/conversations'
import { errorMessage } from '../api/client'
import ProjectSidebar from '../components/ProjectSidebar'
import CircuitSetup from '../components/CircuitSetup'
import CircuitSummary from '../components/CircuitSummary'
import PricePanel from '../components/PricePanel'
import ConversationPanel from '../components/ConversationPanel'
import EvidencePanel from '../components/EvidencePanel'
import JudgementTable from '../components/JudgementTable'
import ApprovalPanel from '../components/ApprovalPanel'
import ApprovedCasesPanel from '../components/ApprovedCasesPanel'
import { candidatesOf } from '../components/circuitContext'
import type { RunState } from '../hooks/useRunStream'

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
  const drawerButton = useRef<HTMLButtonElement>(null)
  const [drawer, setDrawer] = useState(false)
  const [resultTab, setResultTab] = useState<'evidence' | 'judgement' | 'actions'>('evidence')
  const [runState, setRunState] = useState<RunState>({ status: 'idle' })
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number | null>(null)
  const [providedConditions, setProvidedConditions] = useState('')
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      // 다른 로그인 세션이 소유 프로젝트 캐시를 이어받지 않게 즉시 폐기한다.
      client.removeQueries({ queryKey: ['projects'], exact: true })
      client.removeQueries({ queryKey: ['project'] })
      client.removeQueries({ queryKey: ['demo-circuits'], exact: true })
      client.removeQueries({ queryKey: ['judge-roles'], exact: true })
    }
  }, [client])
  const detail = useQuery({ queryKey: ['project', id], queryFn: ({ signal }) => getProject(id!, signal), enabled: id !== null, retry: false, gcTime: 0 })
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, gcTime: 0 })
  const roleLabels = Array.isArray(roles.data) ? roles.data : []
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
    setDrawer(false)
    queueMicrotask(() => drawerButton.current?.focus())
  }
  const receiveRun = useCallback((state: RunState) => setRunState(state), [])
  const result = runState.status === 'completed' || runState.status === 'refused' ? runState.result : null
  const judgement = result?.judgement && 'kind' in result.judgement ? result.judgement as JudgementDto : undefined
  const candidates = useMemo(() => candidatesOf(judgement), [judgement])
  const candidate = selectedCandidateIndex === null ? undefined : candidates[selectedCandidateIndex] as CandidateDto | undefined
  useEffect(() => { setSelectedCandidateIndex(null) }, [id, targetRef, result])
  useEffect(() => { setProvidedConditions('') }, [id, targetRef])
  return <><h1>회로 작업대</h1><p>회로의 역할과 부품 대체 근거를 함께 검토합니다.</p>
    <button ref={drawerButton} className="mobile-project-toggle secondary" aria-expanded={drawer} onClick={() => setDrawer(true)}>프로젝트 열기</button>
    {drawer && <div className="drawer-backdrop" role="dialog" aria-modal="true" aria-label="내 프로젝트"><div className="drawer-panel">
      <button className="secondary drawer-close" onClick={() => { setDrawer(false); drawerButton.current?.focus() }}>닫기</button>
      <ProjectSidebar selectedId={id} project={detail.isError ? undefined : detail.data} onSelect={projectId => { selectProject(projectId); setDrawer(false) }} onDeleted={deleted} />
    </div></div>}
    <div className="workbench-grid">
      <div className="project-rail"><ProjectSidebar selectedId={id} project={detail.isError ? undefined : detail.data} onSelect={selectProject} onDeleted={deleted} /></div>
      <div className="workbench-main">
        {/* 선택 세대가 바뀌면 생성 폼과 진행 요청도 함께 폐기한다. */}
        <CircuitSetup key={version} onCreated={created} />
        {id !== null && detail.isPending && <p role="status">회로를 불러오는 중입니다.</p>}
        {detail.error ? <p role="alert">{errorMessage(detail.error)}</p> : detail.data && <CircuitSummary project={detail.data} targetRef={targetRef}
          judgement={judgement} roleLabels={roleLabels}
          missing={runState.status === 'requires_input' ? runState.interrupt.missing ?? [] : []} providedConditions={providedConditions}
          analysisStatus={runState.status} onTarget={ref => {
          setParams(current => { const next = new URLSearchParams(current); if (ref) next.set('targetRef', ref); else next.delete('targetRef'); return next })
        }} />}
        {roles.error && <p role="alert">역할 정보를 불러오지 못했습니다. {errorMessage(roles.error)}</p>}
        {id !== null && detail.data && <ConversationPanel key={`${id}-${targetRef}`} projectId={id} demoId={detail.data.demo_id} targetRef={targetRef}
          roleLabels={roleLabels} onResult={receiveRun} onConditions={setProvidedConditions} />}
      </div>
      <aside className="workbench-results" aria-label="분석 결과">
        <div className="result-tabs" role="tablist" aria-label="결과 보기">
          {([['evidence', '근거'], ['judgement', '판정'], ['actions', '가격과 승인']] as const).map(([key, label]) => <button key={key} role="tab" aria-selected={resultTab === key} onClick={() => setResultTab(key)}>{label}</button>)}
        </div>
        <div className={`right-tab-panel ${resultTab === 'evidence' ? 'active' : ''}`} role="tabpanel"><EvidencePanel evidence={result?.evidence ?? []} candidate={candidate} /></div>
        <div className={`right-tab-panel ${resultTab === 'judgement' ? 'active' : ''}`} role="tabpanel"><JudgementTable judgement={result?.judgement}
          selectedIndex={selectedCandidateIndex} onSelectCandidate={(_candidate, index) => { setSelectedCandidateIndex(index); setResultTab('evidence') }} /></div>
        <div className={`right-tab-panel ${resultTab === 'actions' ? 'active' : ''}`} role="tabpanel"><PricePanel parts={result?.price_parts ?? []} />
          <ApprovalPanel runId={runState.status === 'completed' ? runState.runId : undefined} judgement={runState.status === 'completed' ? runState.result.judgement : undefined} />
          <ApprovedCasesPanel /></div>
      </aside>
      </div>
  </>
}
