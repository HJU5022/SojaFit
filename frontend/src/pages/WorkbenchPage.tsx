import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { ChevronRight, CircleUserRound, FilePlus2, Folders, LogOut, Maximize2, Pencil, Settings, ShieldCheck, Users, Menu, Search, SquarePen, Trash2, X } from 'lucide-react'
import { attachNetlist, createEmptyProject, createDemo, deleteProject, getProject, listDemos, listProjects, renameProject, uploadProject } from '../api/projects'
import type { ProjectSummary } from '../api/projects'
import { deleteThread, getRun, getThread, listThreads } from '../api/conversations'
import type { ThreadDto } from '../api/conversations'
import { errorMessage, requestIdProps } from '../api/client'
import type { ApiError, DuplicateProject } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { contextOf, isDiode, partIn, partsOf } from '../lib/circuit'
import { candidatesOf, VERDICT_LABELS, VERDICT_TONE } from '../lib/judgement'
import ApprovedCases from '../components/ApprovedCases'
import Review from '../components/Review'
import NetlistIntake from '../components/NetlistIntake'
import { ExternalSchematic, SchematicImage } from '../components/Schematic'
import '../styles/app.css'

// 이미 읽은 서버 판정만 색으로 표시해 실행 완료와 동일품을 혼동하지 않게 한다.
function ThreadStatus({ thread }: { thread: ThreadDto }) {
  const run = useQuery({ queryKey: ['run', thread.latest_run_id], queryFn: ({ signal }) => getRun(thread.latest_run_id!, signal), enabled: false })
  const candidate = candidatesOf(run.data?.result)[0]
  const label = candidate ? VERDICT_LABELS[candidate.verdict] : ({ completed: '검토 종료', running: '검토 중', requires_input: '추가 입력 필요', failed: '실행 실패', refused: '답변 거절' } as Record<string, string>)[thread.status ?? ''] ?? '검토 전'
  return <><span className={`state${candidate ? ` tone-${VERDICT_TONE[candidate.verdict]} state-verdict` : ` state-${thread.status ?? 'none'}`}`} aria-hidden="true" /><span className="sr-only">{label}: </span></>
}

function closeOutside(event: MouseEvent<HTMLDialogElement>) {
  if (event.target !== event.currentTarget) return
  const rect = event.currentTarget.getBoundingClientRect()
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.currentTarget.close()
}

export default function WorkbenchPage() {
  const { user, logout } = useAuth()
  const client = useQueryClient()
  const location = useLocation()
  const [params, setParams] = useSearchParams()
  const rawId = params.get('projectId') ?? ''
  const projectId = /^[1-9]\d*$/.test(rawId) ? Number(rawId) : null
  const targetRef = params.get('targetRef') ?? ''
  const threadId = params.get('threadId') ?? ''
  const [missingProjectId, setMissingProjectId] = useState<number | null>(null)
  const [filter, setFilter] = useState('')
  const [confirming, setConfirming] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [duplicates, setDuplicates] = useState<DuplicateProject[]>([])
  // 닫거나 이동한 뒤 끝난 요청이 이전 오류를 다시 띄우지 않게 한다.
  const errorVersion = useRef(0)
  const [busy, setBusy] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const navigation = useRef<HTMLElement>(null)
  const navToggle = useRef<HTMLButtonElement>(null)
  const creator = useRef<HTMLDialogElement>(null)
  const sheet = useRef<HTMLDialogElement>(null)
  const renamer = useRef<HTMLDialogElement>(null)
  const casesDialog = useRef<HTMLDialogElement>(null)
  const [renaming, setRenaming] = useState<ProjectSummary | null>(null)
  const [casesOpen, setCasesOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [askError, setAskError] = useState('')
  const [pending, setPending] = useState<{ ref: string; question: string } | null>(null) // 부품 목록에서 쓴 질문: 그 부품의 검토 화면이 열릴 때 한 번 보낸다

  const projects = useQuery({ queryKey: ['projects'], queryFn: ({ signal }) => listProjects(signal), retry: false })
  const canReadProject = projectId !== null && projectId !== missingProjectId
  const project = useQuery({ queryKey: ['project', projectId, threadId], queryFn: ({ signal }) => getProject(projectId!, signal, threadId), enabled: canReadProject, retry: false })
  const threads = useQuery({ queryKey: ['threads', projectId], queryFn: ({ signal }) => listThreads(projectId!, signal), enabled: canReadProject, retry: false })
  const thread = useQuery({ queryKey: ['thread', threadId], queryFn: ({ signal }) => getThread(threadId, signal), enabled: canReadProject && Boolean(threadId), retry: false })
  const demos = useQuery({ queryKey: ['demo-circuits'], queryFn: ({ signal }) => listDemos(signal), retry: false })
  const projectList = Array.isArray(projects.data) ? projects.data : []
  const threadList = Array.isArray(threads.data) ? threads.data : []
  const demoList = Array.isArray(demos.data) ? demos.data : []
  const demoOff = (demos.error as ApiError | null)?.code === 'NOT_FOUND' // 데모 모드가 아니면 404: 오류가 아니라 예제 없음
  const parts = partsOf(project.data)
  // 저장된 대화는 주소의 부품 선택값 없이도 열려야 한다. 대상은 서버 기록을 우선한다.
  const threadMismatch = Boolean(thread.data && thread.data.project_id !== projectId)
  const target = parts.find(part => part.ref === (threadId && !threadMismatch ? thread.data?.target_ref ?? targetRef : targetRef))
  const schematic = project.data?.source_kind === 'demo' ? demoList.find(demo => demo.id === project.data?.demo_id)?.schematic ?? null : null
  const query = filter.trim().toLowerCase()
  const filteredProjects = projectList.filter(item => item.name.toLowerCase().includes(query))
  const filteredParts = parts.filter(part => `${part.ref} ${part.value}`.toLowerCase().includes(query))
  const partGroups = [{ title: '판정 가능', eligible: true }, { title: '판정 범위 밖', eligible: false }]
  const clearError = useCallback(() => { errorVersion.current += 1; setError(null); setDuplicates([]) }, [])
  useEffect(() => { errorVersion.current += 1; setError(null); setMissingProjectId(null); return () => { errorVersion.current += 1 } }, [location.key])
  useEffect(() => {
    if (!navOpen) return
    function outside(event: PointerEvent) { if (event.target instanceof Node && !navigation.current?.contains(event.target)) setNavOpen(false) }
    function escape(event: globalThis.KeyboardEvent) { if (event.key === 'Escape') { setNavOpen(false); navToggle.current?.focus() } }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [navOpen])
  const go = useCallback((next: Record<string, string>, projectMissing = false) => {
    clearError(); setFilter(''); setPending(null); setNavOpen(false)
    setParams(next, { state: projectMissing ? { projectMissing: true } : null, replace: projectMissing })
  }, [clearError, setParams])
  const forgetProject = useCallback(async (id: number) => {
    // 화면 이동이 대기 중이어도 지운 활성 쿼리를 재생성하지 않는다.
    setMissingProjectId(id)
    await Promise.all([['projects'], ['project', id], ['threads', id]].map(queryKey => client.cancelQueries({ queryKey })))
    client.setQueryData<ProjectSummary[]>(['projects'], current => current?.filter(item => item.id !== id))
    client.removeQueries({ queryKey: ['project', id] }); client.removeQueries({ queryKey: ['threads', id] })
    void client.invalidateQueries({ queryKey: ['projects'] })
  }, [client])
  const missingProject = useCallback(async (id: number, version: number) => {
    await forgetProject(id)
    if (version !== errorVersion.current) return
    if (renamer.current?.open) renamer.current.close()
    setRenaming(null); setConfirming('')
    go({}, true)
  }, [forgetProject, go])
  useEffect(() => {
    if (projectId === null || (project.error as ApiError | null)?.code !== 'NOT_FOUND') return
    const controller = new AbortController(), version = errorVersion.current
    async function check() {
      if (threadId) {
        try { await getProject(projectId!, controller.signal); return }
        catch (reason) { if (controller.signal.aborted || (reason as ApiError).code !== 'NOT_FOUND') return }
      }
      if (!controller.signal.aborted) await missingProject(projectId!, version)
    }
    void check()
    return () => controller.abort()
  }, [project.error, projectId, threadId, missingProject])
  const onThread = (id: string, ref = target?.ref ?? targetRef) => go({ projectId: String(projectId), ...(ref ? { targetRef: ref } : {}), ...(id ? { threadId: id } : {}) })
  const onReviewThread = (id: string, ref = target?.ref ?? targetRef) => {
    if (id && project.data) client.setQueryData(['project', projectId, id], project.data)
    onThread(id, ref)
  }
  function openCreator() {
    clearError()
    creator.current?.querySelector('form')?.reset()
    creator.current?.showModal()
  }
  function ask(value: string) {
    const text = value.trim()
    if (!text) return
    const hit = partIn(text, parts.filter(isDiode))
    if (hit) { go({ projectId: String(projectId), targetRef: hit.ref, ...(threadId && !thread.data?.target_locked ? { threadId } : {}) }); setPending({ ref: hit.ref, question: text }); setQuestion(''); setAskError(''); return }
    const other = partIn(text, parts)
    setAskError(other ? `${other.ref}은(는) 현재 판정 범위 밖입니다. 지금은 다이오드만 판정합니다.` : '어느 부품에 대한 질문인지 알 수 없습니다. 부품 번호(예: D1)를 넣어 주세요.')
  }
  async function importNetlist(file: File, text: string, signal: AbortSignal) {
    if (projectId === null) return
    const version = errorVersion.current
    const attached = await attachNetlist(projectId, file, signal)
    signal.throwIfAborted()
    if (version !== errorVersion.current) return
    const nextParts = partsOf(attached.project)
    const hit = partIn(text, nextParts.filter(isDiode))
    client.setQueryData(['project', projectId, attached.thread_id], attached.project)
    await Promise.all([client.invalidateQueries({ queryKey: ['projects'] }), client.invalidateQueries({ queryKey: ['threads', projectId] })])
    signal.throwIfAborted()
    if (version !== errorVersion.current) return
    go({ projectId: String(projectId), threadId: attached.thread_id, ...(hit ? { targetRef: hit.ref } : {}) })
    setQuestion(text); setAskError('')
    if (hit && text) setPending({ ref: hit.ref, question: text })
  }
  async function removeThread(id: string) {
    if (confirming !== id) { setConfirming(id); return }
    clearError()
    const version = errorVersion.current
    try { await deleteThread(id); await client.invalidateQueries({ queryKey: ['threads', projectId] }); if (version === errorVersion.current && id === threadId) onThread('') }
    catch (reason) { if (version === errorVersion.current) setError(reason) } finally { setConfirming('') }
  }
  useEffect(() => { if (renaming) renamer.current?.showModal() }, [renaming])
  useEffect(() => { if (casesOpen) casesDialog.current?.showModal() }, [casesOpen])
  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = String(new FormData(event.currentTarget).get('name') ?? '').trim()
    if (busy || !renaming || !name) return
    setBusy(true); clearError()
    const version = errorVersion.current
    try { await renameProject(renaming.id, name); await client.invalidateQueries({ queryKey: ['projects'] }); await client.invalidateQueries({ queryKey: ['project', renaming.id] }); if (version === errorVersion.current) renamer.current?.close() }
    catch (reason) {
      if ((reason as ApiError).code === 'NOT_FOUND') await missingProject(renaming.id, version)
      else if (version === errorVersion.current) setError(reason)
    } finally { setBusy(false) }
  }
  async function removeProject(id: number) {
    const key = `project-${id}`
    if (confirming !== key) { setConfirming(key); return }
    clearError()
    const version = errorVersion.current
    try { await deleteProject(id); await forgetProject(id) }
    catch (reason) {
      if ((reason as ApiError).code === 'NOT_FOUND') await missingProject(id, version)
      else if (version === errorVersion.current) setError(reason)
    } finally { setConfirming('') }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const data = new FormData(event.currentTarget)
    const file = data.get('netlist')
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null
    const allowDuplicate = duplicates.length > 0 && submitter?.name === 'allow_duplicate'
    setBusy(true); clearError()
    const version = errorVersion.current
    try {
      const made = file instanceof File && file.size > 0 ? await uploadProject(String(data.get('name') ?? '').trim(), file, undefined, allowDuplicate) : data.get('demo') ? await createDemo(String(data.get('demo')), String(data.get('name') ?? '').trim(), undefined, allowDuplicate) : await createEmptyProject(String(data.get('name') ?? '').trim(), allowDuplicate)
      await client.invalidateQueries({ queryKey: ['projects'] })
      if (version === errorVersion.current) { creator.current?.close(); go({ projectId: String(made.id) }) }
    } catch (reason) {
      if (version === errorVersion.current) {
        if ((reason as ApiError)?.duplicates?.length) setDuplicates((reason as ApiError).duplicates!)
        else setError(reason)
      }
    } finally { setBusy(false) }
  }

  if (!user) return null
  return <div className="app">
    <nav ref={navigation} className={`rail${navOpen ? ' rail-open' : ''}`} aria-label="프로젝트와 검토">
      <div className="rail-top"><a className="brand" href="/app"><img src="/assets/sojafit-icon.svg" alt="" width={22} height={22} />SojaFit</a>
        <div className="rail-tools"><button className="icon-btn" onClick={openCreator} aria-label="새 프로젝트" title="새 프로젝트"><FilePlus2 aria-hidden="true" /></button>
          <button ref={navToggle} className="icon-btn nav-toggle" aria-label={navOpen ? '탐색 닫기' : '탐색 열기'} aria-expanded={navOpen} aria-controls="rail-content" onClick={() => setNavOpen(value => !value)}>{navOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</button></div></div>
      <div className="rail-content" id="rail-content">
      <button className="rail-row" aria-current={projectId === null ? 'true' : undefined} onClick={() => go({})}><Folders aria-hidden="true" />프로젝트</button>
      <button className="rail-row" onClick={() => { clearError(); setNavOpen(false); setCasesOpen(true) }}><ShieldCheck aria-hidden="true" />승인 사례</button>
      {project.data && <>
        <h2>{project.data.name}</h2>
        <button className="rail-row" aria-current={!target && !threadId ? 'true' : undefined} onClick={() => go({ projectId: String(projectId) })}><Search aria-hidden="true" />부품 고르기</button>
        {target && <button className="rail-row" aria-current={!threadId ? 'true' : undefined} onClick={() => onThread('')}><SquarePen aria-hidden="true" />새 검토</button>}
        <h2>검토 기록</h2>
        {threads.isPending && <div className="skeleton" role="status"><span className="sr-only">검토 기록을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
        {!threads.isPending && !threads.error && threadList.length === 0 && <p className="rail-notice">검토 기록이 없습니다. 부품을 고르고 질문을 보내 주세요.</p>}
        <ul>{threadList.map(thread => <li key={thread.id} onMouseLeave={() => setConfirming('')}>
          <button className="rail-row" title={thread.title || '제목 없는 검토'} aria-current={thread.id === threadId ? 'true' : undefined} onClick={() => onThread(thread.id)}><ThreadStatus thread={thread} /><span>{thread.title || '제목 없는 검토'}</span></button>
          <button className={`rail-del${confirming === thread.id ? ' on' : ''}`} onClick={() => void removeThread(thread.id)} onBlur={() => setConfirming('')}
            aria-label={`${thread.title || '검토'} ${confirming === thread.id ? '삭제 확인' : '삭제'}`}>{confirming === thread.id ? '삭제' : <Trash2 aria-hidden="true" />}</button>
        </li>)}</ul>
        {threads.error && <p className="rail-notice" role="alert">검토 기록을 불러오지 못했습니다.<button className="btn" onClick={() => void threads.refetch()}>다시 불러오기</button></p>}
      </>}
      <button className="rail-row rail-user" popoverTarget="user-menu"><CircleUserRound aria-hidden="true" /><span>{user.email}</span></button>
      </div>
      <div id="user-menu" popover="auto" className="menu"><p>{user.email}<small>{user.role === 'admin' ? '관리자' : '일반 사용자'}</small></p>
        <Link className="rail-row" to="/settings"><Settings aria-hidden="true" />내 설정</Link>
        {user.role === 'admin' && <Link className="rail-row" to="/admin/users"><Users aria-hidden="true" />사용자 관리</Link>}
        <button className="rail-row" onClick={() => void logout()}><LogOut aria-hidden="true" />로그아웃</button></div>
    </nav>

    <main className="main">
      <header className="bar">
        <ol className="crumbs"><li><button onClick={() => go({})}>프로젝트</button></li>
          {project.data && <li><ChevronRight aria-hidden="true" /><button onClick={() => go({ projectId: String(projectId) })}>{project.data.name}</button></li>}
          {target && <li><ChevronRight aria-hidden="true" /><span className="ref">{target.ref}</span><span className="crumb-value">{target.value}</span></li>}</ol>
        {project.data && <span className="fine">{project.data.circuit_version === 0 ? '넷리스트 없음' : `회로 v${project.data.circuit_version ?? 1}`}</span>}
        {project.data && parts.length > 0 && !demos.isPending && (target || !schematic) && <button className="btn" onClick={() => { clearError(); sheet.current?.showModal() }}><Maximize2 aria-hidden="true" />원본 회로도</button>}
      </header>
      {projects.error && projectId === null && <div className="notice inset" role="alert"><p {...requestIdProps(projects.error)}>프로젝트 목록을 불러오지 못했습니다. {errorMessage(projects.error)}</p><button className="btn" onClick={() => void projects.refetch()}>프로젝트 다시 불러오기</button></div>}
      {location.state?.projectMissing === true && <div className="notice notice-dismissible inset" role="status"><p>삭제되었거나 더 이상 접근할 수 없는 프로젝트입니다. 최신 목록을 확인해 주세요.</p><button type="button" className="icon-btn" aria-label="프로젝트 안내 닫기" onClick={() => setParams(params, { replace: true, state: null })}><X aria-hidden="true" /></button></div>}
      {project.error && <div className="notice inset" role="alert"><p {...requestIdProps(project.error)}>회로를 불러오지 못했습니다. {errorMessage(project.error)}</p><button className="btn" onClick={() => void project.refetch()}>회로 다시 불러오기</button></div>}
      {!creator.current?.open && !renaming && error ? <div className="notice notice-dismissible inset" role="alert" {...requestIdProps(error)}><p>삭제하지 못했습니다. {errorMessage(error)} 같은 삭제 버튼으로 다시 시도해 주세요.</p><button type="button" className="icon-btn" aria-label="오류 알림 닫기" onClick={clearError}><X aria-hidden="true" /></button></div> : null}
      {projectId !== null && threadId && (project.isPending || (!target && thread.isPending)) && <div className="skeleton inset" role="status"><span className="sr-only">검토할 회로와 대화 기록을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}

      {projectId === null && <section className="list">
        <div className="list-head"><h1 className="sr-only">프로젝트</h1><label className="filter"><Search aria-hidden="true" /><span className="sr-only">프로젝트 찾기</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="이름으로 찾기" /></label>
          <button className="btn btn-primary" onClick={openCreator}><FilePlus2 aria-hidden="true" />새 프로젝트</button></div>
        <table className="rows"><thead><tr><th scope="col">이름</th><th scope="col">종류</th><th scope="col">마지막 수정</th><th scope="col"><span className="sr-only">조작</span></th></tr></thead>
          <tbody>{filteredProjects.map(item => <tr key={item.id} onClick={() => go({ projectId: String(item.id) })} onMouseLeave={() => setConfirming('')}>
            <th scope="row"><button>{item.name}</button></th><td data-label="종류">{item.circuit_version === 0 ? '넷리스트 없음' : item.source_kind === 'demo' ? '예제 회로' : '올린 넷리스트'}</td><td data-label="마지막 수정">{item.updated_at.slice(0, 10)}</td>
            <td data-label="조작" onClick={event => event.stopPropagation()}><span className="row-actions row-actions-end">
              <button className="icon-btn" aria-label={`${item.name} 이름 바꾸기`} title="이름 바꾸기" onClick={() => { clearError(); setRenaming(item) }}><Pencil aria-hidden="true" /></button>
              <button className={confirming === `project-${item.id}` ? 'btn' : 'icon-btn'} aria-label={`${item.name} ${confirming === `project-${item.id}` ? '삭제 확인' : '삭제'}`} title="프로젝트 삭제" onClick={() => void removeProject(item.id)} onBlur={() => setConfirming('')}>{confirming === `project-${item.id}` ? '삭제 확인' : <Trash2 aria-hidden="true" />}</button>
            </span></td></tr>)}</tbody></table>
        {projects.isPending && <div className="skeleton" role="status"><span className="sr-only">프로젝트를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
        {!projects.isPending && !projects.error && projectList.length === 0 && <p className="empty">아직 프로젝트가 없습니다. 이름으로 프로젝트를 만들고 넷리스트는 나중에 첨부해도 됩니다.</p>}
        {!projects.isPending && projectList.length > 0 && !filteredProjects.length && <p className="empty">이름이 일치하는 프로젝트가 없습니다. 검색어를 바꾸거나 지워 주세요.</p>}
      </section>}

      {projectId !== null && project.data && !target && !threadMismatch && (!threadId || (thread.isSuccess && !thread.data.target_locked)) && <NetlistIntake key={`${projectId}:${threadId}`} question={question} setQuestion={text => { setQuestion(text); setAskError('') }} hasCircuit={parts.length > 0} onAsk={ask} onAttach={importNetlist}>
        {askError && <p className="notice" role="alert">{askError}</p>}
        {parts.length > 0 && <>
        <div className="list-head"><h1 className="sr-only">교체할 부품</h1><label className="filter"><Search aria-hidden="true" /><span className="sr-only">부품 찾기</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="참조 번호나 값으로 찾기" /></label></div>
        {partGroups.map(group => {
          const items = filteredParts.filter(part => isDiode(part) === group.eligible)
          if (!items.length) return null
          return <section className={`part-group${group.eligible ? '' : ' part-group-secondary'}`} key={group.title} aria-label={group.title}>
            <div className="section-head"><h2>{group.title}<span className="group-count">{items.length}</span></h2><span>{group.eligible ? '다이오드' : '현재 다이오드만 판정합니다.'}</span></div>
            <table className="rows"><thead><tr><th scope="col">참조</th><th scope="col">값</th><th scope="col">풋프린트</th></tr></thead>
              <tbody>{items.map(part => <tr key={part.ref} className={group.eligible ? undefined : 'dim-row'} onClick={() => { go({ projectId: String(projectId), targetRef: part.ref, ...(threadId && !thread.data?.target_locked ? { threadId } : {}) }); if (question.trim()) setPending({ ref: part.ref, question: question.trim() }) }}>
                <th scope="row"><button>{part.ref}<span className="sr-only"> {part.value} 선택</span></button></th><td data-label="값">{part.value}</td><td data-label="풋프린트">{part.footprint.replace(/^import_input:/, '') || '넷리스트에 없음'}</td></tr>)}</tbody></table>
          </section>
        })}
        {project.isPending && <div className="skeleton" role="status"><span className="sr-only">회로를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
        {!project.isPending && !project.error && !filteredParts.length && <p className="empty">{parts.length ? '참조 번호나 값이 일치하는 부품이 없습니다. 검색어를 바꾸거나 지워 주세요.' : '넷리스트에 부품이 없습니다. 새 프로젝트에서 부품이 있는 파일을 올려 주세요.'}</p>}
        </>}
      </NetlistIntake>}

      {projectId !== null && target && !threadMismatch && <Review key={`${projectId}:${project.data?.circuit_version ?? 1}`} projectId={projectId} demoId={project.data?.demo_id ?? null} target={target} nets={contextOf(project.data, target.ref)}
        counts={{ parts: parts.length, nets: project.data?.connections.nets.length ?? 0 }} threadId={threadId} reviewer={user.email} initialQuestion={pending?.ref === target.ref ? pending.question : undefined} onThread={onReviewThread} onAttach={importNetlist} />}
      {projectId !== null && threadId && !target && thread.error && <div className="notice inset" role="alert"><p {...requestIdProps(thread.error)}>대화 기록을 불러오지 못했습니다. {errorMessage(thread.error)}</p><button className="btn" onClick={() => void thread.refetch()}>대화 다시 불러오기</button></div>}
      {threadId && threadMismatch && <p className="notice inset" role="alert">이 프로젝트의 검토 기록이 아닙니다. 왼쪽 검토 기록에서 다시 선택해 주세요.</p>}
      {projectId !== null && !target && threadId && project.data && thread.isSuccess && thread.data.target_locked && !threadMismatch && <p className="empty inset">이 검토의 대상 부품을 회로에서 찾지 못했습니다. <button className="btn" onClick={() => go({ projectId: String(projectId) })}>부품 고르기</button></p>}
    </main>

    <dialog ref={renamer} className="dialog" aria-labelledby="renamer-title" onClick={closeOutside} onClose={() => { clearError(); setRenaming(null) }}>
      {renaming && <form onSubmit={rename}>
        <h2 id="renamer-title">프로젝트 이름 바꾸기</h2>
        <label className="field"><span>프로젝트 이름</span><input className="input" name="name" required maxLength={80} autoComplete="off" autoFocus defaultValue={renaming.name} /></label>
        {error ? <div className="notice notice-dismissible" role="alert" {...requestIdProps(error)}><p>이름을 바꾸지 못했습니다. {errorMessage(error)}</p><button type="button" className="icon-btn" aria-label="오류 알림 닫기" onClick={clearError}><X aria-hidden="true" /></button></div> : null}
        <div className="dialog-foot"><button type="button" className="btn" onClick={() => renamer.current?.close()}>취소</button><button className="btn btn-primary" disabled={busy}>{busy ? '저장 중' : '이름 저장'}</button></div>
      </form>}
    </dialog>
    <dialog ref={casesDialog} className="dialog dialog-wide" aria-labelledby="cases-title" onClick={closeOutside} onClose={() => setCasesOpen(false)}>
      {casesOpen && <div className="dialog-body"><h2 id="cases-title">승인 사례</h2><ApprovedCases />
        <div className="dialog-foot"><button type="button" className="btn" autoFocus onClick={() => casesDialog.current?.close()}>닫기</button></div></div>}
    </dialog>
    <dialog ref={creator} className="dialog" aria-labelledby="creator-title" onClick={closeOutside} onClose={clearError}><form onSubmit={create} onChange={() => setDuplicates([])}>
      <h2 id="creator-title">새 프로젝트</h2>
      <label className="field"><span>프로젝트 이름</span><input className="input" name="name" required maxLength={80} autoComplete="off" autoFocus disabled={busy} /></label>
      <label className="field"><span>KiCad 넷리스트 (선택, .net, 5 MiB 이하)</span><input className="input" name="netlist" type="file" accept=".net" disabled={busy} /></label>
      <p className="property-note">파일 없이 먼저 만들고 채팅에서 넷리스트를 첨부할 수 있습니다.</p>
      {demos.isPending && <div className="skeleton" role="status"><span className="sr-only">예제 회로를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
      {demos.error && !demoOff && <div className="notice" role="alert"><p>예제 회로 목록을 불러오지 못했습니다.</p><button type="button" className="btn" onClick={() => void demos.refetch()}>예제 다시 불러오기</button></div>}
      {!demos.isPending && !demos.error && !demoList.length && <p className="property-note">예제 회로가 없습니다. 파일 없이 먼저 시작할 수 있습니다.</p>}
      {demoList.length > 0 && <label className="field"><span>파일이 없으면 예제 회로로 시작</span><select className="input" name="demo" defaultValue="" disabled={busy}><option value="">파일 없이 시작</option>{demoList.map(demo => <option key={demo.id} value={demo.id}>{demo.name}</option>)}</select></label>}
      {duplicates.length > 0 && <div className="notice duplicate-projects" role="alert"><p>같은 이름이나 넷리스트를 사용하는 프로젝트가 있습니다. 기존 프로젝트를 열거나 새로 만들 수 있습니다.</p>
        {duplicates.map(item => <div key={item.id}><p>{item.name} · {item.matches.map(match => match === 'name' ? '이름 중복' : '넷리스트 중복').join(' · ')}</p><button type="button" className="btn" onClick={() => { creator.current?.close(); go({ projectId: String(item.id) }) }}>기존 프로젝트 열기: {item.name}</button></div>)}
      </div>}
      {error ? <div className="notice notice-dismissible" role="alert" {...requestIdProps(error)}><p>프로젝트를 만들지 못했습니다. {errorMessage(error)} 입력을 확인하고 만들기로 다시 시도해 주세요.</p><button type="button" className="icon-btn" aria-label="오류 알림 닫기" onClick={clearError}><X aria-hidden="true" /></button></div> : null}
      <div className="dialog-foot"><button type="button" className="btn" onClick={() => creator.current?.close()}>취소</button><button className="btn btn-primary" disabled={busy || duplicates.length > 0}>{busy ? '만드는 중' : '만들기'}</button>{duplicates.length > 0 && <button className="btn btn-primary" name="allow_duplicate" disabled={busy}>중복을 확인하고 새로 만들기</button>}</div>
    </form></dialog>

    <dialog ref={sheet} className="dialog sheet" aria-labelledby="sheet-title" onClick={closeOutside}>
      <header><h2 id="sheet-title">{project.data?.name} 원본 회로도</h2>
        <button className="icon-btn" onClick={() => sheet.current?.close()} aria-label="닫기"><X aria-hidden="true" /></button></header>
      {schematic ? <SchematicImage key={schematic.image_url} schematic={schematic} name={project.data?.name ?? ''} /> : project.data && <ExternalSchematic key={`${project.data.id}:${project.data.circuit_version}:${threadId}`} name={project.data.name} context={{ projectId: project.data.id, circuitVersion: project.data.circuit_version ?? 0, threadId: threadId || undefined }} />}
    </dialog>
  </div>
}
