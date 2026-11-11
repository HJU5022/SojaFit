import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { getProject, listProjects } from '../api/projects'
import type { Project } from '../api/projects'
import { deleteThread, listJudgeRoles, listThreads } from '../api/conversations'
import type { CandidateDto, JudgementDto, ThreadDto } from '../api/conversations'
import { errorMessage } from '../api/client'
import ProjectSidebar from '../components/ProjectSidebar'
import CircuitSetup from '../components/CircuitSetup'
import CircuitSummary from '../components/CircuitSummary'
import ConversationPanel, { SavedConversationPanel } from '../components/ConversationPanel'
import EvidencePanel from '../components/EvidencePanel'
import JudgementTable from '../components/JudgementTable'
import ApprovalPanel from '../components/ApprovalPanel'
import ApprovedCasesPanel from '../components/ApprovedCasesPanel'
import AccessibleDialog from '../components/AccessibleDialog'
import AccountMenu from '../components/AccountMenu'
import { ProcessingIcon } from '../components/RunStatus'
import { candidatesOf } from '../components/circuitContext'
import type { RunState } from '../hooks/useRunStream'

type ResultTab = 'circuit' | 'evidence' | 'judgement' | 'activity' | 'actions'
type User = { user_id: number; role: 'user' | 'admin'; email?: string }
type ResizeSide = 'rail' | 'information'

const clamp = (value: number, minimum: number, maximum: number) => Math.min(maximum, Math.max(minimum, value))

function statusText(state: RunState) {
  if (state.status === 'running') return `${state.stage} 진행 중`
  if (state.status === 'requires_input') return '추가 정보 필요'
  if (state.status === 'completed') return '판정 완료'
  if (state.status === 'refused') return '요청 거절'
  if (state.status === 'failed') return '분석 오류'
  return '분석 대기'
}

function ActivityPanel({ states }: { states: RunState[] }) {
  return <section className="panel activity-panel" aria-labelledby="activity-heading"><h2 id="activity-heading">분석 진행 기록</h2>
    {states.length === 0 ? <p>아직 분석을 시작하지 않았습니다.</p> : <ol>{states.map((state, index) => <li key={`${state.status}-${'stage' in state ? state.stage : ''}-${index}`}>
      <span className={`activity-dot activity-${state.status}`} aria-hidden="true" /><strong>{statusText(state)}</strong>
    </li>)}</ol>}
    <p className="panel-note">실제 수신한 실행 상태만 표시합니다.</p>
  </section>
}

function EmptyConversationPanel({ loading = false }: { loading?: boolean }) {
  return <section className="conversation-panel empty-conversation" aria-label="에이전트 대화">
    <div className="conversation-stream" aria-live="polite">{loading && <p role="status">회로를 불러오는 중입니다.</p>}</div>
    <div className="composer composer-disabled">
      <label htmlFor="d5-question">질문</label><div className="composer-input-row"><textarea id="d5-question" rows={3} disabled placeholder="상단에서 프로젝트와 부품을 선택하세요." /><button type="button" className="composer-send" aria-label="질문 전송" title="질문 전송" disabled><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6" /></svg></button></div>
    </div>
  </section>
}

export default function WorkbenchPage({ user, onLogout, logoutBusy = false }: { user?: User; onLogout?: () => Promise<void>; logoutBusy?: boolean }) {
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [reduceMotion, setReduceMotion] = useState(() => window.localStorage?.getItem('sojafit-reduce-motion') === 'true')
  const rawId = params.get('projectId') ?? ''
  const id = /^[1-9][0-9]*$/.test(rawId) && Number.isSafeInteger(Number(rawId)) ? Number(rawId) : null
  const targetRef = params.get('targetRef') ?? ''
  const historyId = params.get('threadId') ?? ''
  const historyKey = `${id}:${historyId}`
  const selection = useRef({ signature: params.toString(), version: 0 })
  if (selection.current.signature !== params.toString()) selection.current = { signature: params.toString(), version: selection.current.version + 1 }
  const version = selection.current.version
  const mounted = useRef(true)
  const projectButton = useRef<HTMLButtonElement>(null)
  const [projectDialog, setProjectDialog] = useState(false)
  const [projectDrawer, setProjectDrawer] = useState(false)
  const [projectsExpanded, setProjectsExpanded] = useState(false)
  const [railExpanded, setRailExpanded] = useState(true)
  const [railWidth, setRailWidth] = useState(208)
  const [resultTab, setResultTab] = useState<ResultTab>('circuit')
  const [panelCollapsed, setPanelCollapsed] = useState(true)
  const [panelWidth, setPanelWidth] = useState(360)
  const [search, setSearch] = useState('')
  const [liveRunState, setRunState] = useState<RunState>({ status: 'idle' })
  const [restoredHistory, setRestoredHistory] = useState<{ key: string; target: string; state: RunState } | null>(null)
  const runState: RunState = historyId ? restoredHistory?.key === historyKey ? restoredHistory.state : { status: 'idle' } : liveRunState
  const displayedTarget = historyId ? restoredHistory?.key === historyKey ? restoredHistory.target : '' : targetRef
  const restoreHistory = useCallback((target: string, state: RunState) => setRestoredHistory({ key: historyKey, target, state }), [historyKey])
  const [activity, setActivity] = useState<RunState[]>([])
  const lastActivity = useRef('idle')
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number | null>(null)
  const [providedConditions, setProvidedConditions] = useState('')
  const [conversationVersion, setConversationVersion] = useState(0)
  const [activeThreadId, setActiveThreadId] = useState('')
  const [conversationBusy, setConversationBusy] = useState(false)
  const pinKey = `sojafit-pinned-threads:${user?.user_id ?? 'local'}:${id}`
  const [pinState, setPinState] = useState<{ key: string; ids: string[] }>({ key: '', ids: [] })
  const [pinNotice, setPinNotice] = useState('')
  const pinnedIds = pinState.key === pinKey ? pinState.ids : []
  const pinned = new Set(pinnedIds)
  const [deleteTarget, setDeleteTarget] = useState<{ thread: ThreadDto; projectId: number } | null>(null)
  const [threadDeleting, setThreadDeleting] = useState(false)
  const [threadDeleteError, setThreadDeleteError] = useState('')
  const [isMobile, setIsMobile] = useState(false)
  const [isCompact, setIsCompact] = useState(false)
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth)
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const resize = useRef<{ side: ResizeSide; pointerId: number; startX: number; startWidth: number } | null>(null)
  useEffect(() => {
    setPinNotice(''); setDeleteTarget(null); setThreadDeleteError('')
    try {
      const stored: unknown = JSON.parse(window.localStorage.getItem(pinKey) ?? '[]')
      setPinState({ key: pinKey, ids: Array.isArray(stored) ? stored.filter((value): value is string => typeof value === 'string') : [] })
    } catch {
      setPinState({ key: pinKey, ids: [] })
      setPinNotice('고정 설정을 읽지 못했습니다. 이 화면에서만 고정할 수 있습니다.')
    }
  }, [pinKey])
  function savePins(ids: string[]) {
    setPinState({ key: pinKey, ids })
    try { window.localStorage.setItem(pinKey, JSON.stringify(ids)); setPinNotice('') }
    catch { setPinNotice('고정 설정을 저장하지 못했습니다. 이 화면에서만 유지됩니다.') }
  }
  useEffect(() => {
    const update = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])
  useEffect(() => {
    const query = window.matchMedia?.('(max-width: 767px)')
    const compact = window.matchMedia?.('(max-width: 1199px)')
    if (!query || !compact) return
    const update = () => {
      setIsMobile(query.matches); setIsCompact(compact.matches)
      setRailExpanded(!query.matches)
      setPanelCollapsed(true)
    }
    update()
    query.addEventListener?.('change', update)
    compact.addEventListener?.('change', update)
    return () => { query.removeEventListener?.('change', update); compact.removeEventListener?.('change', update) }
  }, [])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      client.removeQueries({ queryKey: ['projects'], exact: true }); client.removeQueries({ queryKey: ['project'] })
      client.removeQueries({ queryKey: ['demo-circuits'], exact: true }); client.removeQueries({ queryKey: ['judge-roles'], exact: true })
    }
  }, [client])
  const detail = useQuery({ queryKey: ['project', id], queryFn: ({ signal }) => getProject(id!, signal), enabled: id !== null, retry: false, gcTime: 0 })
  const projects = useQuery({ queryKey: ['projects'], queryFn: ({ signal }) => listProjects(signal), retry: false, gcTime: 0 })
  const threads = useQuery({ queryKey: ['threads', id], queryFn: ({ signal }) => listThreads(id!, signal), enabled: id !== null, retry: false, gcTime: 0 })
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, gcTime: 0 })
  const orderedThreads = [...(Array.isArray(threads.data) ? threads.data : [])].sort((a, b) => Number(pinned.has(b.id)) - Number(pinned.has(a.id)))
  function sessionIsProcessing(thread: ThreadDto) {
    if (thread.id === activeThreadId && !historyId) return runState.status === 'running' || (conversationBusy && runState.status === 'idle')
    if (thread.id === historyId && runState.status !== 'idle') return runState.status === 'running'
    return thread.status === 'running'
  }
  function selectProject(projectId: number) {
    if (conversationBusy || threadDeleting) return
    if (isMobile) setRailExpanded(false)
    if (projectId === id) return
    setRunState({ status: 'idle' }); setActiveThreadId('')
    selection.current.version++
    setPanelCollapsed(isCompact)
    setParams(current => { const next = new URLSearchParams(current); next.set('projectId', String(projectId)); next.delete('targetRef'); next.delete('threadId'); return next })
  }
  function selectTarget(ref: string) {
    if (conversationBusy || historyId) return
    setRunState({ status: 'idle' }); setActiveThreadId('')
    setParams(current => { const next = new URLSearchParams(current); if (ref) next.set('targetRef', ref); else next.delete('targetRef'); return next })
  }
  function created(project: Project) {
    if (mounted.current && selection.current.version === version) {
      client.setQueryData(['project', project.id], project)
      selectProject(project.id); setProjectDialog(false); setProjectDrawer(true)
    }
  }
  function deleted(projectId: number) {
    if (!mounted.current) return
    const next = new URLSearchParams(selection.current.signature)
    if (next.get('projectId') === String(projectId)) { next.delete('projectId'); next.delete('targetRef'); next.delete('threadId'); setParams(next, { replace: true }); setPanelCollapsed(true); setRunState({ status: 'idle' }); setActiveThreadId('') }
    setProjectDrawer(false); queueMicrotask(() => projectButton.current?.focus())
  }
  const receiveRun = useCallback((state: RunState) => {
    setRunState(state)
    if (state.status === 'completed' || state.status === 'refused') {
      setResultTab('judgement')
    }
    const signature = `${state.status}-${'stage' in state ? state.stage : ''}`
    if (signature !== lastActivity.current) { lastActivity.current = signature; setActivity(current => [...current, state]) }
  }, [])
  function newConversation() {
    if (conversationBusy || threadDeleting) return
    resetConversation()
  }
  function resetConversation() {
    if (isMobile) setRailExpanded(false)
    setConversationVersion(value => value + 1)
    setActiveThreadId(''); setRunState({ status: 'idle' }); setProvidedConditions('')
    setActivity([]); lastActivity.current = 'idle'; setSelectedCandidateIndex(null)
    setParams(current => { const next = new URLSearchParams(current); next.delete('threadId'); return next })
  }
  function selectHistory(threadId: string) {
    if (conversationBusy || threadDeleting) return
    if (isMobile) setRailExpanded(false)
    if (threadId === historyId) return
    setRestoredHistory(null); setRunState({ status: 'idle' }); setActiveThreadId('')
    setPanelCollapsed(isCompact); setResultTab('judgement'); setSelectedCandidateIndex(null)
    setParams(current => { const next = new URLSearchParams(current); next.set('threadId', threadId); return next })
  }
  async function confirmThreadDeletion() {
    if (!deleteTarget || threadDeleting || conversationBusy) return
    const selected = deleteTarget
    const requestedVersion = selection.current.version
    setThreadDeleting(true); setThreadDeleteError('')
    try {
      await deleteThread(selected.thread.id)
      if (!mounted.current || selection.current.version !== requestedVersion) return
      client.setQueryData<ThreadDto[]>(['threads', selected.projectId], current => current?.filter(thread => thread.id !== selected.thread.id))
      client.removeQueries({ queryKey: ['thread-history', selected.projectId, selected.thread.id] })
      client.removeQueries({ queryKey: ['saved-run', selected.projectId, selected.thread.id] })
      savePins(pinnedIds.filter(threadId => threadId !== selected.thread.id))
      if (selected.thread.id === (historyId || activeThreadId)) { resetConversation(); setPanelCollapsed(true) }
      setDeleteTarget(null)
      void client.invalidateQueries({ queryKey: ['threads', selected.projectId] })
      queueMicrotask(() => (document.querySelector<HTMLButtonElement>('.workspace-project-heading button') ?? document.querySelector<HTMLButtonElement>('.workspace-navigation-toggle'))?.focus())
    } catch (error) {
      if (mounted.current && selection.current.version === requestedVersion) setThreadDeleteError(errorMessage(error))
    } finally { if (mounted.current) setThreadDeleting(false) }
  }
  function closeThreadDeletion() {
    const threadId = deleteTarget?.thread.id
    setDeleteTarget(null)
    queueMicrotask(() => document.getElementById(`session-${threadId}`)?.focus())
  }
  const result = runState.status === 'completed' || runState.status === 'refused' ? runState.result : null
  const judgement = result?.judgement && 'kind' in result.judgement ? result.judgement as JudgementDto : undefined
  const candidates = useMemo(() => candidatesOf(judgement), [judgement])
  const candidate = selectedCandidateIndex === null ? undefined : candidates[selectedCandidateIndex] as CandidateDto | undefined
  useEffect(() => { setSelectedCandidateIndex(null) }, [id, targetRef, result])
  useEffect(() => { setProvidedConditions(''); setActivity([]); lastActivity.current = 'idle' }, [id, targetRef, historyId])
  const parts = detail.data?.connections.parts ?? detail.data?.connections.components ?? []
  const target = parts.find(part => part.ref === displayedTarget)
  const normalizedSearch = search.trim().toLocaleLowerCase()
  const searchProjects = normalizedSearch ? (projects.data ?? []).filter(item => item.name.toLocaleLowerCase().includes(normalizedSearch)) : []
  const searchParts = normalizedSearch ? parts.filter(part => `${part.ref} ${part.value}`.toLocaleLowerCase().includes(normalizedSearch)) : []
  const resultTabItems = [['circuit', '회로'], ['evidence', '근거'], ['judgement', '후보 비교'], ['activity', '진행 기록'], ['actions', '승인·견적']] as const
  function moveTab(current: number, direction: number) {
    const next = (current + direction + resultTabItems.length) % resultTabItems.length
    setResultTab(resultTabItems[next][0])
    tabRefs.current[next]?.focus()
  }
  function moveSearchOption(event: KeyboardEvent<HTMLElement>) {
    const options = Array.from(document.querySelectorAll<HTMLElement>('#workbench-search-results [role="option"]'))
    const current = options.indexOf(event.currentTarget)
    if (event.key === 'Escape') {
      event.preventDefault(); setSearch(''); document.getElementById('workbench-search')?.focus(); return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    options[(current + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length]?.focus()
  }
  const panelMaximum = Math.max(320, Math.min(480, viewportWidth - (railExpanded ? railWidth : 58) - 560))
  const informationWidth = Math.min(panelWidth, panelMaximum)
  function startResize(side: ResizeSide, event: ReactPointerEvent<HTMLElement>) {
    if (isCompact) return
    event.preventDefault()
    resize.current = { side, pointerId: event.pointerId, startX: event.clientX, startWidth: side === 'rail' ? railWidth : informationWidth }
    event.currentTarget.setPointerCapture?.(event.pointerId)
  }
  function continueResize(side: ResizeSide, event: ReactPointerEvent<HTMLElement>) {
    const active = resize.current
    if (!active || active.side !== side || active.pointerId !== event.pointerId) return
    const delta = side === 'rail' ? event.clientX - active.startX : active.startX - event.clientX
    if (side === 'rail') setRailWidth(clamp(active.startWidth + delta, 160, 320))
    else setPanelWidth(clamp(active.startWidth + delta, 320, panelMaximum))
  }
  function finishResize(event: ReactPointerEvent<HTMLElement>) {
    if (resize.current?.pointerId === event.pointerId) resize.current = null
    event.currentTarget.releasePointerCapture?.(event.pointerId)
  }
  function resizeWithKeyboard(side: ResizeSide, event: KeyboardEvent<HTMLElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const direction = event.key === 'ArrowRight' ? 10 : -10
    if (side === 'rail') setRailWidth(value => clamp(value + direction, 160, 320))
    else setPanelWidth(clamp(informationWidth - direction, 320, panelMaximum))
  }
  const layoutStyle = { '--rail-width': `${railExpanded ? railWidth : 58}px`, '--info-width': `${informationWidth}px` } as CSSProperties
  const navigation = <nav className={`function-rail${railExpanded ? ' expanded' : ''}`} aria-label="작업 메뉴">
      <button className="rail-toggle" aria-expanded={railExpanded} aria-label={railExpanded ? '작업 메뉴 접기' : '작업 메뉴 펼치기'} onClick={() => setRailExpanded(value => !value)}><span aria-hidden="true">☰</span><span className="rail-label">작업 메뉴</span></button>
      {railExpanded && <section className="workspace-project-navigation" aria-label="프로젝트와 대화">
        <div className="workspace-project-heading"><h2>현재 프로젝트</h2><button ref={projectButton} className="icon-button secondary" aria-label="프로젝트 추가" title="프로젝트 추가" disabled={conversationBusy || threadDeleting} onClick={() => setProjectDialog(true)}><svg aria-hidden="true" viewBox="0 0 20 20"><path d="M10 4v12M4 10h12" /></svg></button></div>
        {projects.isPending && <p role="status">프로젝트를 불러오는 중입니다.</p>}
        <ul id="workspace-projects" className="workspace-project-list" aria-label="저장된 프로젝트">{(projectsExpanded ? projects.data ?? [] : (projects.data ?? []).slice(0, 2)).map(project => <li key={project.id}><button disabled={conversationBusy} aria-current={project.id === id ? 'true' : undefined} title={project.name} onClick={() => selectProject(project.id)}>{project.name}</button></li>)}</ul>
        {(projects.data?.length ?? 0) >= 3 && <button className="workspace-project-more" aria-expanded={projectsExpanded} aria-controls="workspace-projects" onClick={() => setProjectsExpanded(value => !value)}>{projectsExpanded ? '접기' : `더보기 (${projects.data!.length - 2})`}</button>}
        {projects.data?.length === 0 && <p>저장된 프로젝트가 없습니다.</p>}
        {projects.error && !projectDrawer && <p role="alert">{errorMessage(projects.error)}</p>}
        <div className="workspace-project-heading"><h2>이전 대화</h2><button className="icon-button secondary" aria-label="새 대화" title="현재 프로젝트에서 새 대화" disabled={conversationBusy || !detail.data} onClick={newConversation}><svg aria-hidden="true" viewBox="0 0 20 20"><path d="M10 4v12M4 10h12" /></svg></button></div>{id === null && <p>프로젝트를 선택하면 이전 대화를 볼 수 있습니다.</p>}
        {id !== null && threads.isPending && <p role="status">대화 목록을 불러오는 중입니다.</p>}
        {threads.error && <div><p role="alert">{errorMessage(threads.error)}</p><button className="secondary" onClick={() => void threads.refetch()}>목록 다시 불러오기</button></div>}
        <ul className="workspace-session-list" aria-label="이전 대화">{orderedThreads.map(thread => <li key={thread.id}><button id={`session-${thread.id}`} aria-busy={sessionIsProcessing(thread)} disabled={conversationBusy || threadDeleting} onClick={() => selectHistory(thread.id)} aria-current={thread.id === (historyId || activeThreadId) ? 'true' : undefined} title={thread.title || `대화 ${thread.id.slice(0, 8)}`}>
          {pinned.has(thread.id) && <><svg className="session-pin" aria-hidden="true" viewBox="0 0 24 24"><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6ZM12 14v7" /></svg><span className="sr-only">고정된 대화</span></>}
          <span className="workspace-session-title">{thread.title || `대화 ${thread.id.slice(0, 8)}`}</span>{sessionIsProcessing(thread) ? <span className="session-progress" title="분석 진행 중"><ProcessingIcon /><span className="sr-only">분석 진행 중</span></span> : thread.id === (historyId || activeThreadId) && <span className="workspace-current-dot" aria-hidden="true" />}{thread.id === (historyId || activeThreadId) && <span className="sr-only">현재 대화</span>}</button>
          <div className="workspace-session-actions" role="group" aria-label={`${thread.title || `대화 ${thread.id.slice(0, 8)}`} 관리`}>
            <button aria-label={pinned.has(thread.id) ? '대화 고정 해제' : '대화 고정'} title={pinned.has(thread.id) ? '이 브라우저에서 고정 해제' : '이 브라우저에 고정'} disabled={threadDeleting} onClick={event => { const trigger = event.currentTarget; savePins(pinned.has(thread.id) ? pinnedIds.filter(threadId => threadId !== thread.id) : [...pinnedIds, thread.id]); queueMicrotask(() => { if (trigger.isConnected) { document.getElementById(`session-${thread.id}`)?.focus(); trigger.focus() } }) }}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M9 3h6l-1 6 3 3v2H7v-2l3-3-1-6ZM12 14v7" /></svg></button>
            <button className="session-delete" aria-label="대화 삭제" title={thread.status === 'running' ? '실행 중인 대화는 삭제할 수 없습니다.' : '대화 삭제'} disabled={conversationBusy || threadDeleting || thread.status === 'running'} onClick={() => { if (id !== null) { setThreadDeleteError(''); setDeleteTarget({ thread, projectId: id }) } }}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14M10 10v7M14 10v7" /></svg></button>
          </div></li>)}</ul>
        {pinNotice && <p role="status">{pinNotice}</p>}
        {threads.data?.length === 0 && <p>저장된 대화가 없습니다.</p>}
        {conversationBusy && <p role="status">분석과 추가 입력을 마친 뒤 대화를 전환할 수 있습니다.</p>}
      </section>}
      <div className="rail-bottom"><a href="#workbench-help" aria-label="도움말"><span className="rail-icon" aria-hidden="true">?</span><span className="rail-label">도움말</span></a>{user?.role === 'admin' && <Link to="/admin/users" aria-label="관리자 메뉴"><span className="rail-icon" aria-hidden="true">⚙</span><span className="rail-label">관리자</span></Link>}</div>
      {railExpanded && <div className="panel-resizer rail-resizer" role="separator" aria-label="작업 메뉴 너비 조절" aria-orientation="vertical" aria-valuemin={160} aria-valuemax={320} aria-valuenow={railWidth} title="드래그하여 작업 메뉴 너비 조절" tabIndex={0} onPointerDown={event => startResize('rail', event)} onPointerMove={event => continueResize('rail', event)} onPointerUp={finishResize} onPointerCancel={finishResize} onKeyDown={event => resizeWithKeyboard('rail', event)} />}
    </nav>
  const information = <aside className={`information-console${panelCollapsed ? ' collapsed' : ''}`} aria-label="회로와 분석 정보">
      {!panelCollapsed && !isCompact && <div className="panel-resizer information-resizer" role="separator" aria-label="회로 및 분석 정보 너비 조절" aria-orientation="vertical" aria-valuemin={320} aria-valuemax={panelMaximum} aria-valuenow={informationWidth} title="드래그하여 회로 및 분석 정보 너비 조절" tabIndex={0} onPointerDown={event => startResize('information', event)} onPointerMove={event => continueResize('information', event)} onPointerUp={finishResize} onPointerCancel={finishResize} onKeyDown={event => resizeWithKeyboard('information', event)} />}
      <div className="console-toolbar"><button className="icon-button secondary" aria-label={panelCollapsed ? '정보 패널 펼치기' : '정보 패널 접기'} onClick={() => setPanelCollapsed(value => !value)}>{panelCollapsed ? '‹' : '›'}</button></div>
      {!panelCollapsed && <><div className="result-tabs" role="tablist" aria-label="정보 보기">{resultTabItems.map(([key, label], index) => <button id={`tab-${key}`} ref={node => { tabRefs.current[index] = node }} key={key} role="tab" tabIndex={resultTab === key ? 0 : -1} aria-selected={resultTab === key} aria-controls={`panel-${key}`} onKeyDown={event => { if (event.key === 'ArrowRight') moveTab(index, 1); if (event.key === 'ArrowLeft') moveTab(index, -1) }} onClick={() => setResultTab(key)}>{label}</button>)}</div>
        <div className="console-content">
          <div id="panel-circuit" aria-labelledby="tab-circuit" className={`right-tab-panel ${resultTab === 'circuit' ? 'active' : ''}`} role="tabpanel" tabIndex={0}>{detail.data ? <CircuitSummary project={detail.data} targetRef={displayedTarget} readOnly={!!historyId || conversationBusy} judgement={judgement} roleLabels={Array.isArray(roles.data) ? roles.data : []} missing={runState.status === 'requires_input' ? runState.interrupt.missing ?? [] : []} providedConditions={providedConditions} analysisStatus={runState.status} onTarget={selectTarget} /> : <section className="panel"><h2>회로</h2><p>선택한 프로젝트가 없습니다.</p></section>}</div>
          <div id="panel-evidence" aria-labelledby="tab-evidence" className={`right-tab-panel ${resultTab === 'evidence' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><EvidencePanel evidence={result?.evidence ?? []} candidate={candidate} /></div>
          <div id="panel-judgement" aria-labelledby="tab-judgement" className={`right-tab-panel ${resultTab === 'judgement' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><JudgementTable judgement={result?.judgement} selectedIndex={selectedCandidateIndex} onSelectCandidate={(_item, index) => { setSelectedCandidateIndex(index); setResultTab('evidence') }} /></div>
          <div id="panel-activity" aria-labelledby="tab-activity" className={`right-tab-panel ${resultTab === 'activity' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><ActivityPanel states={historyId ? runState.status === 'idle' ? [] : [runState] : activity} /></div>
          <div id="panel-actions" aria-labelledby="tab-actions" className={`right-tab-panel ${resultTab === 'actions' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><ApprovalPanel key={`${historyKey}:${'runId' in runState ? runState.runId : ''}`} runId={runState.status === 'completed' ? runState.runId : undefined} judgement={runState.status === 'completed' ? runState.result.judgement : undefined} /><ApprovedCasesPanel /></div>
        </div></>}
    </aside>
  return <div className={`workbench-shell workspace-ready${panelCollapsed ? ' console-collapsed' : ''}${reduceMotion ? ' motion-reduced' : ''}`} style={layoutStyle}>
    <header className="app-topbar workbench-topbar">
      {isMobile && <button className="workspace-navigation-toggle secondary" aria-label="작업 메뉴 펼치기" aria-expanded={railExpanded} onClick={() => setRailExpanded(true)}>☰</button>}
      <a className="brand workbench-brand" href="/app"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="142" height="40" /></a>
      <button type="button" className="workbench-context" title="프로젝트와 부품 선택" disabled={conversationBusy || threadDeleting} aria-label={`프로젝트 선택: ${detail.data?.name ?? '프로젝트 없음'}`} onClick={() => setProjectDrawer(true)}><strong>{detail.data?.name ?? '프로젝트 없음'}</strong><span>{target ? `${target.ref} · ${target.value || '품번 확인 안 됨'}` : '대상 부품 미선택'}</span></button>
      <div className="workbench-search"><label className="sr-only" htmlFor="workbench-search">프로젝트 또는 부품 찾기</label><input id="workbench-search" type="search" aria-haspopup="listbox" aria-controls="workbench-search-results" aria-expanded={Boolean(normalizedSearch)} value={search} onChange={event => setSearch(event.target.value)} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); document.querySelector<HTMLElement>('#workbench-search-results [role="option"]')?.focus() } }} placeholder="프로젝트 또는 부품 찾기" />
        {normalizedSearch && <div id="workbench-search-results" className="search-results" role="listbox" aria-label="검색 결과">{searchProjects.map(item => <button role="option" tabIndex={0} key={`project-${item.id}`} onKeyDown={moveSearchOption} onClick={() => { selectProject(item.id); setSearch('') }}>프로젝트 · {item.name}</button>)}{searchParts.map(part => <button role="option" tabIndex={0} key={`part-${part.ref}`} onKeyDown={moveSearchOption} onClick={() => { selectTarget(part.ref); setResultTab('circuit'); setSearch('') }}>{part.ref} · {part.value || '확인 안 됨'}</button>)}{searchProjects.length + searchParts.length === 0 && <p>현재 불러온 항목에서 찾지 못했습니다.</p>}</div>}
      </div>
      <AccountMenu user={user} onLogout={onLogout} logoutBusy={logoutBusy} onMotionChange={setReduceMotion} />
    </header>
    {isMobile ? railExpanded && <AccessibleDialog title="프로젝트와 대화" className="workspace-navigation-drawer" onClose={() => setRailExpanded(false)}>{navigation}</AccessibleDialog> : navigation}

    <div className="analysis-surface" role="main" aria-label="분석 대화 작업면">
      <div className="analysis-heading"><div><h1>{id === null ? 'SojaFit 에이전트' : '회로 작업대'}</h1><p>{displayedTarget ? `${displayedTarget} 교체 조건과 데이터시트 근거를 검토합니다.` : '프로젝트를 선택하거나 회로를 등록해 검토를 시작하세요.'}</p></div><div className="analysis-heading-actions">{isCompact && <button className="secondary" aria-label="정보 패널 펼치기" onClick={() => setPanelCollapsed(false)}>상세</button>}{displayedTarget && <span className="target-badge" title="선택한 부품">{displayedTarget}</span>}{!isCompact && (runState.status === 'completed' || runState.status === 'refused') && <button className="result-link" onClick={() => { setResultTab('judgement'); setPanelCollapsed(false) }}>결과 보기</button>}</div></div>
      {id !== null && <ol className="workbench-steps" aria-label="분석 진행 단계"><li className="complete">프로젝트</li><li className={displayedTarget ? 'complete' : 'current'}>대상 선택</li><li className={displayedTarget ? 'current' : ''}>질문</li><li className={result ? 'complete' : ''}>결과 검토</li><li className={result ? 'current' : ''}>승인·견적</li></ol>}
      {id !== null && detail.isPending && <p role="status">회로를 불러오는 중입니다.</p>}
      {detail.error && <p role="alert">{errorMessage(detail.error)}</p>}
      {roles.error && <p role="alert">역할 정보를 불러오지 못했습니다. {errorMessage(roles.error)}</p>}
      {id !== null && detail.data ? historyId
        ? <SavedConversationPanel key={historyKey} projectId={id} threadId={historyId} onRestore={restoreHistory}
            onShowActivity={() => { setResultTab('activity'); setPanelCollapsed(false) }} onShowActions={() => { setResultTab('actions'); setPanelCollapsed(false) }}
            onShowEvidence={() => { setResultTab('evidence'); setPanelCollapsed(false) }} onShowJudgement={() => { setResultTab('judgement'); setPanelCollapsed(false) }} />
        : <ConversationPanel key={`${id}-${targetRef}-${conversationVersion}`} projectId={id} demoId={detail.data.demo_id} targetRef={targetRef} roleLabels={Array.isArray(roles.data) ? roles.data : []}
            onResult={receiveRun} onConditions={setProvidedConditions} onThreadChange={setActiveThreadId} onBusyChange={setConversationBusy}
            onShowActivity={() => { setResultTab('activity'); setPanelCollapsed(false) }} onShowActions={() => { setResultTab('actions'); setPanelCollapsed(false) }}
            onShowEvidence={() => { setResultTab('evidence'); setPanelCollapsed(false) }} onShowJudgement={() => { setResultTab('judgement'); setPanelCollapsed(false) }} />
        : <EmptyConversationPanel loading={id !== null && detail.isPending} />}
      <p id="workbench-help" className="workbench-help sr-only">분석 진행 상태는 서버에서 받은 실제 단계만 표시하며, 실행 시간이나 완료율을 예측하지 않습니다.</p>
    </div>
    {isCompact ? !panelCollapsed && <AccessibleDialog title="회로와 분석 정보" className="workspace-detail-drawer" onClose={() => setPanelCollapsed(true)}>{information}</AccessibleDialog> : information}

    {projectDialog && <AccessibleDialog title="프로젝트 만들기" onClose={() => setProjectDialog(false)} className="project-dialog"><CircuitSetup key={version} onCreated={created} /></AccessibleDialog>}
    {deleteTarget && <AccessibleDialog title="대화 삭제" onClose={closeThreadDeletion} dismissible={!threadDeleting} closeOnBackdrop={false}>
      <p className="thread-delete-title">{deleteTarget.thread.title || '새 대화'}</p><p>이 대화의 메시지·분석 결과·체크포인트와 연결된 승인·견적·사례가 함께 삭제되며 복구할 수 없습니다. 프로젝트와 다른 대화는 유지됩니다.</p>
      {threadDeleteError && <p role="alert">{threadDeleteError}</p>}
      <div className="dialog-actions"><button className="secondary" disabled={threadDeleting} onClick={closeThreadDeletion}>취소</button><button disabled={threadDeleting} onClick={() => void confirmThreadDeletion()}>{threadDeleting ? '삭제 중…' : '삭제 확인'}</button></div>
    </AccessibleDialog>}
    {projectDrawer && <AccessibleDialog title="내 프로젝트" onClose={() => setProjectDrawer(false)} className="project-drawer">
      {id !== null && detail.isPending && <p role="status">프로젝트 정보를 불러오는 중입니다.</p>}
      {detail.error && <p role="alert">{errorMessage(detail.error)}</p>}
      <ProjectSidebar selectedId={id} project={detail.isError ? undefined : detail.data} onSelect={selectProject} onDeleted={deleted}
        targetRef={displayedTarget} busy={conversationBusy || threadDeleting} targetLocked={!!historyId}
        onTarget={ref => { selectTarget(ref); setProjectDrawer(false) }} />
    </AccessibleDialog>}
    <button className="mobile-project-toggle secondary" onClick={() => setProjectDrawer(true)}>프로젝트 열기</button>
  </div>
}
