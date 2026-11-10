import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent, PointerEvent as ReactPointerEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { getProject, listProjects } from '../api/projects'
import type { Project } from '../api/projects'
import { listJudgeRoles } from '../api/conversations'
import type { CandidateDto, JudgementDto } from '../api/conversations'
import { errorMessage } from '../api/client'
import ProjectSidebar from '../components/ProjectSidebar'
import CircuitSetup from '../components/CircuitSetup'
import CircuitSummary from '../components/CircuitSummary'
import ConversationPanel from '../components/ConversationPanel'
import EvidencePanel from '../components/EvidencePanel'
import JudgementTable from '../components/JudgementTable'
import ApprovalPanel from '../components/ApprovalPanel'
import ApprovedCasesPanel from '../components/ApprovedCasesPanel'
import AccessibleDialog from '../components/AccessibleDialog'
import LandingServiceIntroduction from '../components/LandingServiceIntroduction'
import { candidatesOf } from '../components/circuitContext'
import type { RunState } from '../hooks/useRunStream'

type ResultTab = 'circuit' | 'evidence' | 'judgement' | 'activity' | 'actions'
type RailItem = { key: string; label: string; icon: string; action: () => void; current?: boolean }
type User = { user_id: number; role: 'user' | 'admin' }
type ResizeSide = 'rail' | 'information'
type LandingDraft = { question: string; conditions: string }

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

function EmptyConversationPanel({ onCreate, loading = false }: { onCreate: () => void; loading?: boolean }) {
  return <section className="conversation-panel empty-conversation" aria-labelledby="conversation-heading"><div className="conversation-title"><div><span className="eyebrow">분석 대화</span><h2 id="conversation-heading">대체 가능성 분석 흐름</h2></div><span className="target-badge">대상 미선택</span></div>
    <div className="conversation-stream" aria-live="polite"><article className="conversation-card input-card"><span className="card-kicker">시작 안내</span><h3>{loading ? '회로를 불러오는 중입니다.' : '프로젝트를 먼저 만드세요'}</h3><p>{loading ? '회로와 부품 정보를 확인한 뒤 질문 입력을 활성화합니다.' : '프로젝트가 없습니다. 데모 또는 파일로 시작하세요.'}</p>{!loading && <button className="secondary" onClick={onCreate}>프로젝트 만들기</button>}</article></div>
    <div className="composer composer-disabled"><div className="composer-context"><strong>대상 미선택</strong><span>프로젝트와 대상 부품을 먼저 선택하세요.</span></div>
      <label htmlFor="d5-question">질문</label><textarea id="d5-question" rows={3} disabled placeholder="프로젝트를 만들면 질문할 수 있습니다." />
      <label htmlFor="d5-conditions">사용 조건 (선택)</label><textarea id="d5-conditions" rows={2} disabled />
      <div className="composer-actions"><button disabled>분석하기</button></div>
    </div>
  </section>
}

const landingSuggestions = [
  'D1을 SS34로 바꿔도 되나요?',
  '12V 전원 회로에 맞는 정류 다이오드를 찾아줘',
  'LM7805를 대체할 부품과 근거를 비교해줘',
  '1N4001보다 순방향 전압이 낮은 후보를 찾아줘',
  '5V 1A 조건에 맞는 LDO를 비교해줘',
  '역전압 여유가 충분한 다이오드를 찾아줘',
  '발열을 줄일 쇼트키 다이오드를 추천해줘',
  'TO-220 패키지 호환 부품을 비교해줘',
  '드롭아웃 전압이 더 낮은 레귤레이터를 찾아줘',
  '주변 온도 60도에서 열 여유를 확인해줘',
  '핀 배열이 같은 대체 부품을 찾아줘',
  '현재 풋프린트에 맞는 패키지를 비교해줘',
  '부하 전류 여유가 충분한 후보를 보여줘',
  '동작 온도 범위를 데이터시트로 확인해줘',
  '판정 근거가 있는 후보만 비교해줘',
  '출력 커패시터 조건이 맞는지 확인해줘',
  'F1과 같은 역할의 퓨즈 후보를 찾아줘',
  'Rds(on)이 더 낮은 MOSFET을 비교해줘',
  '역회복 시간이 짧은 다이오드를 찾아줘',
  '커넥터의 허용 전류가 충분한지 확인해줘',
  '12V 라인에 맞는 TVS 다이오드를 비교해줘',
  '효율이 더 나은 벅 레귤레이터 후보를 찾아줘',
  '단일 전원에서 동작하는 OP AMP를 찾아줘',
  '3.3V UART용 레벨 시프터를 비교해줘',
  '정전류 LED 드라이버 후보를 찾아줘',
  '슬립 전류가 낮은 MCU를 비교해줘',
  'ESR 조건이 맞는 커패시터를 찾아줘',
  '코일 전압이 같은 릴레이 후보를 비교해줘',
  '서지 전류를 견디는 정류기를 찾아줘',
  '단종 부품을 대체할 호환 후보를 찾아줘',
]

function shuffledSuggestions() {
  const items = [...landingSuggestions]
  for (let index = items.length - 1; index > 0; index -= 1) {
    const target = Math.floor(Math.random() * (index + 1))
    ;[items[index], items[target]] = [items[target], items[index]]
  }
  return [items.slice(0, 10), items.slice(10, 20), items.slice(20, 30)]
}

function InitialLanding({ draft, onDraft, onCreate, onOpenProjects }: {
  draft: LandingDraft
  onDraft: (draft: LandingDraft) => void
  onCreate: () => void
  onOpenProjects: () => void
}) {
  const questionRef = useRef<HTMLTextAreaElement>(null)
  const suggestionLanes = useMemo(shuffledSuggestions, [])
  return <section className="initial-landing" aria-labelledby="landing-heading">
    <div className="landing-circuit" aria-hidden="true" />
    <div className="landing-hero" id="landing-start">
      <div className="landing-mark" aria-hidden="true"><svg viewBox="0 0 48 20"><path d="M5 10h15l8-6v12l-8-6h23" /><circle cx="5" cy="10" r="3" /><circle cx="43" cy="10" r="3" /></svg><span>SOJAFIT</span></div>
      <h1 id="landing-heading">회로에 맞는 대체 부품을 찾아보세요</h1>
      <p className="landing-intro">부품과 사용 조건을 자연어로 적으면 프로젝트를 만든 뒤 데이터시트 근거와 대체 가능성을 함께 검토합니다.</p>
      <div className="landing-composer">
        <label htmlFor="landing-question">질문</label>
        <textarea ref={questionRef} id="landing-question" rows={3} maxLength={4000} value={draft.question} onChange={event => onDraft({ ...draft, question: event.target.value })} placeholder="예: D1을 SS34로 바꿔도 되나요?" />
        <label htmlFor="landing-conditions">사용 조건 (선택)</label>
        <textarea id="landing-conditions" rows={2} maxLength={2000} value={draft.conditions} onChange={event => onDraft({ ...draft, conditions: event.target.value })} placeholder="예: 12V, 1A, 주변 온도 60°C" />
        <div className="landing-actions"><button type="button" className="secondary" onClick={onOpenProjects}>기존 프로젝트 열기</button><button type="button" disabled={!draft.question.trim()} onClick={onCreate}>분석 시작</button></div>
      </div>
      <div className="landing-suggestions" aria-label="빠른 시작 질문">
        <span className="quick-start-label">빠른 시작</span>
        {suggestionLanes.map((lane, laneIndex) => <div className={`suggestion-lane direction-${laneIndex === 1 ? 'right' : 'left'}`} key={`lane-${laneIndex}`}>
          <div className="suggestion-track">
            {[false, true].map(copy => <div className={`suggestion-group${copy ? ' suggestion-copy' : ''}`} aria-hidden={copy || undefined} key={copy ? 'copy' : 'source'}>
              {lane.map((suggestion, suggestionIndex) => <button type="button" className={`suggestion-chip tone-${suggestionIndex % 5}`} tabIndex={copy ? -1 : 0} key={suggestion} onClick={() => onDraft({ ...draft, question: suggestion })}>{suggestion}</button>)}
            </div>)}
          </div>
        </div>)}
      </div>
    </div>
    <LandingServiceIntroduction onStart={() => { questionRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'center' }); questionRef.current?.focus() }} />
  </section>
}

export default function WorkbenchPage({ user, onLogout, logoutBusy = false }: { user?: User; onLogout?: () => Promise<void>; logoutBusy?: boolean }) {
  const client = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const [personalSettingsOpen, setPersonalSettingsOpen] = useState(false)
  const [reduceMotion, setReduceMotion] = useState(() => window.localStorage?.getItem('sojafit-reduce-motion') === 'true')
  const rawId = params.get('projectId') ?? ''
  const id = /^[1-9][0-9]*$/.test(rawId) && Number.isSafeInteger(Number(rawId)) ? Number(rawId) : null
  const targetRef = params.get('targetRef') ?? ''
  const selection = useRef({ signature: params.toString(), version: 0 })
  if (selection.current.signature !== params.toString()) selection.current = { signature: params.toString(), version: selection.current.version + 1 }
  const version = selection.current.version
  const mounted = useRef(true)
  const projectButton = useRef<HTMLButtonElement>(null)
  const [projectDialog, setProjectDialog] = useState(false)
  const [projectDrawer, setProjectDrawer] = useState(false)
  const [railExpanded, setRailExpanded] = useState(true)
  const [railWidth, setRailWidth] = useState(220)
  const [resultTab, setResultTab] = useState<ResultTab>('circuit')
  const [panelCollapsed, setPanelCollapsed] = useState(id === null)
  const [panelWidth, setPanelWidth] = useState(430)
  const [search, setSearch] = useState('')
  const [runState, setRunState] = useState<RunState>({ status: 'idle' })
  const [activity, setActivity] = useState<RunState[]>([])
  const lastActivity = useRef('idle')
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number | null>(null)
  const [providedConditions, setProvidedConditions] = useState('')
  const [landingDraft, setLandingDraft] = useState<LandingDraft>({ question: '', conditions: '' })
  const [isMobile, setIsMobile] = useState(false)
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const resize = useRef<{ side: ResizeSide; pointerId: number; startX: number; startWidth: number } | null>(null)
  useEffect(() => {
    const query = window.matchMedia?.('(max-width: 900px)')
    if (!query) return
    const update = () => setIsMobile(query.matches)
    update()
    query.addEventListener?.('change', update)
    return () => query.removeEventListener?.('change', update)
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
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, gcTime: 0 })
  function selectProject(projectId: number) {
    selection.current.version++
    setPanelCollapsed(false)
    setParams(current => { const next = new URLSearchParams(current); next.set('projectId', String(projectId)); next.delete('targetRef'); return next })
  }
  function selectTarget(ref: string) {
    setParams(current => { const next = new URLSearchParams(current); if (ref) next.set('targetRef', ref); else next.delete('targetRef'); return next })
  }
  function created(project: Project) {
    if (mounted.current && selection.current.version === version) { selectProject(project.id); setProjectDialog(false) }
  }
  function deleted(projectId: number) {
    if (!mounted.current) return
    const next = new URLSearchParams(selection.current.signature)
    if (next.get('projectId') === String(projectId)) { next.delete('projectId'); next.delete('targetRef'); setParams(next, { replace: true }); setPanelCollapsed(true) }
    setProjectDrawer(false); queueMicrotask(() => projectButton.current?.focus())
  }
  const receiveRun = useCallback((state: RunState) => {
    setRunState(state)
    if (state.status === 'completed' || state.status === 'refused') {
      setResultTab('judgement')
      setPanelCollapsed(false)
    }
    const signature = `${state.status}-${'stage' in state ? state.stage : ''}`
    if (signature !== lastActivity.current) { lastActivity.current = signature; setActivity(current => [...current, state]) }
  }, [])
  const result = runState.status === 'completed' || runState.status === 'refused' ? runState.result : null
  const judgement = result?.judgement && 'kind' in result.judgement ? result.judgement as JudgementDto : undefined
  const candidates = useMemo(() => candidatesOf(judgement), [judgement])
  const candidate = selectedCandidateIndex === null ? undefined : candidates[selectedCandidateIndex] as CandidateDto | undefined
  useEffect(() => { setSelectedCandidateIndex(null) }, [id, targetRef, result])
  useEffect(() => { setProvidedConditions(''); setActivity([]); lastActivity.current = 'idle' }, [id, targetRef])
  const parts = detail.data?.connections.parts ?? detail.data?.connections.components ?? []
  const target = parts.find(part => part.ref === targetRef)
  const normalizedSearch = search.trim().toLocaleLowerCase()
  const searchProjects = normalizedSearch ? (projects.data ?? []).filter(item => item.name.toLocaleLowerCase().includes(normalizedSearch)) : []
  const searchParts = normalizedSearch ? parts.filter(part => `${part.ref} ${part.value}`.toLocaleLowerCase().includes(normalizedSearch)) : []
  const rail: RailItem[] = [
    { key: 'projects', label: '프로젝트', icon: '▦', action: () => setProjectDrawer(true) },
    { key: 'circuit', label: '회로', icon: '⌁', current: resultTab === 'circuit', action: () => { setResultTab('circuit'); setPanelCollapsed(false) } },
    { key: 'evidence', label: '근거', icon: '⌕', current: resultTab === 'evidence', action: () => { setResultTab('evidence'); setPanelCollapsed(false) } },
    { key: 'judgement', label: '후보 비교', icon: '≋', current: resultTab === 'judgement', action: () => { setResultTab('judgement'); setPanelCollapsed(false) } },
    { key: 'actions', label: '승인·견적', icon: '✓', current: resultTab === 'actions', action: () => { setResultTab('actions'); setPanelCollapsed(false) } },
  ]
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
  const panelMaximum = Math.max(320, Math.min(Math.floor(window.innerWidth / 2), window.innerWidth - (railExpanded ? railWidth : 58) - 480))
  function startResize(side: ResizeSide, event: ReactPointerEvent<HTMLElement>) {
    if (isMobile) return
    event.preventDefault()
    resize.current = { side, pointerId: event.pointerId, startX: event.clientX, startWidth: side === 'rail' ? railWidth : panelWidth }
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
    else setPanelWidth(value => clamp(value - direction, 320, panelMaximum))
  }
  const layoutStyle = { '--rail-width': `${railExpanded ? railWidth : 58}px`, '--info-width': `${panelWidth}px` } as CSSProperties
  return <div className={`workbench-shell${panelCollapsed ? ' console-collapsed' : ''}${reduceMotion ? ' motion-reduced' : ''}`} style={layoutStyle}>
    <header className="workbench-topbar">
      <a className="brand workbench-brand" href="/app"><svg aria-hidden="true" viewBox="0 0 48 20"><path d="M5 10h15l8-6v12l-8-6h23" /><circle cx="5" cy="10" r="3" /><circle cx="43" cy="10" r="3" /></svg>SOJAFIT</a>
      <button type="button" className="workbench-context" aria-label={`프로젝트 선택: ${detail.data?.name ?? '프로젝트 없음'}`} onClick={() => setProjectDrawer(true)}><strong>{detail.data?.name ?? '프로젝트 없음'}</strong><span>{target ? `${target.ref} · ${target.value || '품번 확인 안 됨'}` : '대상 부품 미선택'}</span></button>
      <div className="workbench-search"><label className="sr-only" htmlFor="workbench-search">프로젝트 또는 부품 찾기</label><input id="workbench-search" type="search" aria-haspopup="listbox" aria-controls="workbench-search-results" aria-expanded={Boolean(normalizedSearch)} value={search} onChange={event => setSearch(event.target.value)} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); document.querySelector<HTMLElement>('#workbench-search-results [role="option"]')?.focus() } }} placeholder="프로젝트 또는 부품 찾기" />
        {normalizedSearch && <div id="workbench-search-results" className="search-results" role="listbox" aria-label="검색 결과">{searchProjects.map(item => <button role="option" tabIndex={0} key={`project-${item.id}`} onKeyDown={moveSearchOption} onClick={() => { selectProject(item.id); setSearch('') }}>프로젝트 · {item.name}</button>)}{searchParts.map(part => <button role="option" tabIndex={0} key={`part-${part.ref}`} onKeyDown={moveSearchOption} onClick={() => { selectTarget(part.ref); setResultTab('circuit'); setSearch('') }}>{part.ref} · {part.value || '확인 안 됨'}</button>)}{searchProjects.length + searchParts.length === 0 && <p>현재 불러온 항목에서 찾지 못했습니다.</p>}</div>}
      </div>
      <div className="workbench-account"><span className={`run-chip run-${runState.status}`}>{statusText(runState)}</span><button className="account-menu-trigger secondary" aria-haspopup="menu" aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen(value => !value)}><span aria-hidden="true">○</span><span>{user ? `사용자 ${user.user_id}` : '계정'}</span></button>{accountMenuOpen && <div className="account-menu-popover" role="menu" aria-label="계정 메뉴">{user ? <><div className="account-menu-summary"><strong>사용자 {user.user_id}</strong><span>{user.role === 'admin' ? '관리자' : '일반 사용자'}</span></div><button role="menuitem" onClick={() => { setAccountMenuOpen(false); setPersonalSettingsOpen(true) }}>개인 설정</button><Link role="menuitem" to="/settings" onClick={() => setAccountMenuOpen(false)}>내 설정 관리</Link>{user.role === 'admin' && <Link role="menuitem" to="/admin/users" onClick={() => setAccountMenuOpen(false)}>사용자 관리</Link>}<button role="menuitem" disabled={logoutBusy} onClick={() => { setAccountMenuOpen(false); void onLogout?.() }}>{logoutBusy ? '로그아웃 중…' : '로그아웃'}</button></> : <Link role="menuitem" to="/login" onClick={() => setAccountMenuOpen(false)}>로그인</Link>}</div>}</div>
    </header>
    <nav className={`function-rail${railExpanded ? ' expanded' : ''}`} aria-label="작업 메뉴">
      <button className="rail-toggle" aria-expanded={railExpanded} aria-label={railExpanded ? '작업 메뉴 접기' : '작업 메뉴 펼치기'} onClick={() => setRailExpanded(value => !value)}><span aria-hidden="true">☰</span><span className="rail-label">작업 메뉴</span></button>
      {rail.map(item => <button key={item.key} className={item.current ? 'active' : ''} aria-label={item.label} title={item.label} onClick={item.action}><span className="rail-icon" aria-hidden="true">{item.icon}</span><span className="rail-label">{item.label}</span></button>)}
      <div className="rail-bottom"><a href="#workbench-help" aria-label="도움말"><span className="rail-icon" aria-hidden="true">?</span><span className="rail-label">도움말</span></a>{user?.role === 'admin' && <Link to="/admin/users" aria-label="관리자 메뉴"><span className="rail-icon" aria-hidden="true">⚙</span><span className="rail-label">관리자</span></Link>}</div>
      {railExpanded && <div className="panel-resizer rail-resizer" role="separator" aria-label="작업 메뉴 너비 조절" aria-orientation="vertical" aria-valuemin={160} aria-valuemax={320} aria-valuenow={railWidth} title="드래그하여 작업 메뉴 너비 조절" tabIndex={0} onPointerDown={event => startResize('rail', event)} onPointerMove={event => continueResize('rail', event)} onPointerUp={finishResize} onPointerCancel={finishResize} onKeyDown={event => resizeWithKeyboard('rail', event)} />}
    </nav>
    <div className={`analysis-surface${id === null ? ' landing-mode' : ''}`} role="main" aria-label="분석 대화 작업면">
      {id !== null && <><div className="analysis-heading"><div><span className="eyebrow">부품 대체 분석</span><h1>회로 작업대</h1><p>{targetRef ? `${targetRef} 교체 조건과 데이터시트 근거를 검토합니다.` : '회로와 대상 부품을 선택해 분석을 시작하세요.'}</p></div><div className="analysis-heading-actions">{(runState.status === 'completed' || runState.status === 'refused') && <button className="result-link" onClick={() => { setResultTab('judgement'); setPanelCollapsed(false) }}>결과 보기</button>}<button ref={projectButton} className="secondary" onClick={() => setProjectDialog(true)}>프로젝트 만들기</button></div></div>
      <ol className="workbench-steps" aria-label="분석 진행 단계"><li className="complete">프로젝트</li><li className={targetRef ? 'complete' : 'current'}>대상 선택</li><li className={targetRef ? 'current' : ''}>질문</li><li className={result ? 'complete' : ''}>결과 검토</li><li className={result ? 'current' : ''}>승인·견적</li></ol></>}
      {id !== null && detail.isPending && <p role="status">회로를 불러오는 중입니다.</p>}
      {detail.error && <p role="alert">{errorMessage(detail.error)}</p>}
      {roles.error && <p role="alert">역할 정보를 불러오지 못했습니다. {errorMessage(roles.error)}</p>}
      {id === null ? <InitialLanding draft={landingDraft} onDraft={setLandingDraft} onCreate={() => setProjectDialog(true)} onOpenProjects={() => setProjectDrawer(true)} /> : detail.data ? <>{isMobile && <div className="mobile-target-picker"><label htmlFor="mobile-target-ref">질문 영역의 대상 부품</label><select id="mobile-target-ref" value={targetRef} onChange={event => selectTarget(event.target.value)}><option value="">대상을 선택하세요</option>{parts.map(part => <option key={part.ref} value={part.ref}>{part.ref} · {part.value || '확인 안 됨'}</option>)}</select></div>}<ConversationPanel key={`${id}-${targetRef}`} projectId={id} demoId={detail.data.demo_id} targetRef={targetRef} roleLabels={Array.isArray(roles.data) ? roles.data : []} initialQuestion={landingDraft.question} initialConditions={landingDraft.conditions} onResult={receiveRun} onConditions={setProvidedConditions} onShowEvidence={() => { setResultTab('evidence'); setPanelCollapsed(false) }} onShowJudgement={() => { setResultTab('judgement'); setPanelCollapsed(false) }} /></> : <EmptyConversationPanel loading={detail.isPending} onCreate={() => setProjectDialog(true)} />}
      <p id="workbench-help" className="workbench-help sr-only">분석 진행 상태는 서버에서 받은 실제 단계만 표시하며, 실행 시간이나 완료율을 예측하지 않습니다.</p>
    </div>
    <aside className={`information-console${panelCollapsed ? ' collapsed' : ''}`} aria-label="회로와 분석 정보">
      {!panelCollapsed && <div className="panel-resizer information-resizer" role="separator" aria-label="회로 및 분석 정보 너비 조절" aria-orientation="vertical" aria-valuemin={320} aria-valuemax={panelMaximum} aria-valuenow={panelWidth} title="드래그하여 회로 및 분석 정보 너비 조절" tabIndex={0} onPointerDown={event => startResize('information', event)} onPointerMove={event => continueResize('information', event)} onPointerUp={finishResize} onPointerCancel={finishResize} onKeyDown={event => resizeWithKeyboard('information', event)} />}
      <div className="console-toolbar"><strong>회로 및 분석 정보</strong><button className="icon-button secondary" aria-label={panelCollapsed ? '정보 패널 펼치기' : '정보 패널 접기'} onClick={() => setPanelCollapsed(value => !value)}>{panelCollapsed ? '‹' : '›'}</button></div>
      {!panelCollapsed && <><div className="result-tabs" role="tablist" aria-label="정보 보기">{resultTabItems.map(([key, label], index) => <button id={`tab-${key}`} ref={node => { tabRefs.current[index] = node }} key={key} role="tab" tabIndex={resultTab === key ? 0 : -1} aria-selected={resultTab === key} aria-controls={`panel-${key}`} onKeyDown={event => { if (event.key === 'ArrowRight') moveTab(index, 1); if (event.key === 'ArrowLeft') moveTab(index, -1) }} onClick={() => setResultTab(key)}>{label}</button>)}</div>
        <div className="console-content">
          <div id="panel-circuit" aria-labelledby="tab-circuit" className={`right-tab-panel ${resultTab === 'circuit' ? 'active' : ''}`} role="tabpanel" tabIndex={0}>{detail.data ? <CircuitSummary project={detail.data} targetRef={targetRef} judgement={judgement} roleLabels={Array.isArray(roles.data) ? roles.data : []} missing={runState.status === 'requires_input' ? runState.interrupt.missing ?? [] : []} providedConditions={providedConditions} analysisStatus={runState.status} onTarget={selectTarget} /> : <section className="panel"><h2>회로</h2><p>선택한 프로젝트가 없습니다.</p></section>}</div>
          <div id="panel-evidence" aria-labelledby="tab-evidence" className={`right-tab-panel ${resultTab === 'evidence' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><EvidencePanel evidence={result?.evidence ?? []} candidate={candidate} /></div>
          <div id="panel-judgement" aria-labelledby="tab-judgement" className={`right-tab-panel ${resultTab === 'judgement' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><JudgementTable judgement={result?.judgement} selectedIndex={selectedCandidateIndex} onSelectCandidate={(_item, index) => { setSelectedCandidateIndex(index); setResultTab('evidence') }} /></div>
          <div id="panel-activity" aria-labelledby="tab-activity" className={`right-tab-panel ${resultTab === 'activity' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><ActivityPanel states={activity} /></div>
          <div id="panel-actions" aria-labelledby="tab-actions" className={`right-tab-panel ${resultTab === 'actions' ? 'active' : ''}`} role="tabpanel" tabIndex={0}><ApprovalPanel runId={runState.status === 'completed' ? runState.runId : undefined} judgement={runState.status === 'completed' ? runState.result.judgement : undefined} /><ApprovedCasesPanel /></div>
        </div></>}
    </aside>
    {projectDialog && <AccessibleDialog title="프로젝트 만들기" onClose={() => setProjectDialog(false)} className="project-dialog"><CircuitSetup key={version} onCreated={created} /></AccessibleDialog>}
    {projectDrawer && <AccessibleDialog title="내 프로젝트" onClose={() => setProjectDrawer(false)} className="project-drawer"><ProjectSidebar selectedId={id} project={detail.isError ? undefined : detail.data} onSelect={projectId => { selectProject(projectId); setProjectDrawer(false) }} onDeleted={deleted} /></AccessibleDialog>}
    {personalSettingsOpen && <AccessibleDialog title="개인 설정" onClose={() => setPersonalSettingsOpen(false)}><div className="personal-settings"><p>이 화면 설정은 현재 브라우저에 저장됩니다.</p><label className="setting-toggle"><input type="checkbox" checked={reduceMotion} onChange={event => { const checked = event.target.checked; setReduceMotion(checked); window.localStorage?.setItem('sojafit-reduce-motion', String(checked)) }} />동작 효과 줄이기</label></div><div className="dialog-actions"><button onClick={() => setPersonalSettingsOpen(false)}>확인</button></div></AccessibleDialog>}
    <button className="mobile-project-toggle secondary" onClick={() => setProjectDrawer(true)}>프로젝트 열기</button>
  </div>
}
