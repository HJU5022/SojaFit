import { useEffect, useRef, useState } from 'react'
import type { FormEvent, MouseEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { ChevronRight, CircleUserRound, FilePlus2, Folders, LogOut, Maximize2, Pencil, Settings, ShieldCheck, Users, Menu, Minus, Plus, Search, SquarePen, Trash2, X } from 'lucide-react'
import { createDemo, deleteProject, getProject, listDemos, listProjects, renameProject, uploadProject } from '../api/projects'
import type { ProjectSummary } from '../api/projects'
import { deleteThread, getRun, listThreads } from '../api/conversations'
import type { ThreadDto } from '../api/conversations'
import { errorMessage } from '../api/client'
import type { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthProvider'
import { contextOf, isDiode, partsOf } from '../lib/circuit'
import { candidatesOf, VERDICT_LABELS, VERDICT_TONE } from '../lib/judgement'
import ApprovedCases from '../components/ApprovedCases'
import Review from '../components/Review'
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
  const [params, setParams] = useSearchParams()
  const rawId = params.get('projectId') ?? ''
  const projectId = /^[1-9]\d*$/.test(rawId) ? Number(rawId) : null
  const targetRef = params.get('targetRef') ?? ''
  const threadId = params.get('threadId') ?? ''
  const [filter, setFilter] = useState('')
  const [confirming, setConfirming] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [zoom, setZoom] = useState(100)
  const [navOpen, setNavOpen] = useState(false)
  const navigation = useRef<HTMLElement>(null)
  const navToggle = useRef<HTMLButtonElement>(null)
  const creator = useRef<HTMLDialogElement>(null)
  const sheet = useRef<HTMLDialogElement>(null)
  const renamer = useRef<HTMLDialogElement>(null)
  const casesDialog = useRef<HTMLDialogElement>(null)
  const [renaming, setRenaming] = useState<ProjectSummary | null>(null)
  const [casesOpen, setCasesOpen] = useState(false)

  const projects = useQuery({ queryKey: ['projects'], queryFn: ({ signal }) => listProjects(signal), retry: false })
  const project = useQuery({ queryKey: ['project', projectId], queryFn: ({ signal }) => getProject(projectId!, signal), enabled: projectId !== null, retry: false })
  const threads = useQuery({ queryKey: ['threads', projectId], queryFn: ({ signal }) => listThreads(projectId!, signal), enabled: projectId !== null, retry: false })
  const demos = useQuery({ queryKey: ['demo-circuits'], queryFn: ({ signal }) => listDemos(signal), retry: false })
  const projectList = Array.isArray(projects.data) ? projects.data : []
  const threadList = Array.isArray(threads.data) ? threads.data : []
  const demoList = Array.isArray(demos.data) ? demos.data : []
  const demoOff = (demos.error as ApiError | null)?.code === 'NOT_FOUND' // 데모 모드가 아니면 404: 오류가 아니라 예제 없음
  const parts = partsOf(project.data)
  const target = parts.find(part => part.ref === targetRef)
  const schematic = demoList.find(demo => demo.id === project.data?.demo_id)?.schematic ?? null
  const query = filter.trim().toLowerCase()
  const filteredProjects = projectList.filter(item => item.name.toLowerCase().includes(query))
  const filteredParts = parts.filter(part => `${part.ref} ${part.value}`.toLowerCase().includes(query))
  const partGroups = [{ title: '판정 가능', eligible: true }, { title: '판정 범위 밖', eligible: false }]
  useEffect(() => {
    if (!navOpen) return
    function outside(event: PointerEvent) { if (event.target instanceof Node && !navigation.current?.contains(event.target)) setNavOpen(false) }
    function escape(event: globalThis.KeyboardEvent) { if (event.key === 'Escape') { setNavOpen(false); navToggle.current?.focus() } }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [navOpen])
  if (!user) return null

  const go = (next: Record<string, string>) => { setFilter(''); setNavOpen(false); setParams(next) }
  const onThread = (id: string, ref?: string) => go({ projectId: String(projectId), ...((ref ?? targetRef) ? { targetRef: ref ?? targetRef } : {}), ...(id ? { threadId: id } : {}) })
  async function removeThread(id: string) {
    if (confirming !== id) { setConfirming(id); return }
    try { await deleteThread(id); await client.invalidateQueries({ queryKey: ['threads', projectId] }); if (id === threadId) onThread('') }
    catch (reason) { setError(reason) } finally { setConfirming('') }
  }
  useEffect(() => { if (renaming) renamer.current?.showModal() }, [renaming])
  useEffect(() => { if (casesOpen) casesDialog.current?.showModal() }, [casesOpen])
  async function rename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = String(new FormData(event.currentTarget).get('name') ?? '').trim()
    if (busy || !renaming || !name) return
    setBusy(true); setError(null)
    try { await renameProject(renaming.id, name); await client.invalidateQueries({ queryKey: ['projects'] }); await client.invalidateQueries({ queryKey: ['project', renaming.id] }); renamer.current?.close() }
    catch (reason) { setError(reason) } finally { setBusy(false) }
  }
  async function removeProject(id: number) {
    const key = `project-${id}`
    if (confirming !== key) { setConfirming(key); return }
    try { await deleteProject(id); client.removeQueries({ queryKey: ['project', id] }); client.removeQueries({ queryKey: ['threads', id] }); await client.invalidateQueries({ queryKey: ['projects'] }) }
    catch (reason) { setError(reason) } finally { setConfirming('') }
  }
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    const data = new FormData(event.currentTarget)
    const file = data.get('netlist')
    setBusy(true); setError(null)
    try {
      const made = file instanceof File && file.size > 0 ? await uploadProject(String(data.get('name') ?? '').trim(), file) : await createDemo(String(data.get('demo') ?? ''), String(data.get('name') ?? '').trim())
      await client.invalidateQueries({ queryKey: ['projects'] })
      creator.current?.close(); go({ projectId: String(made.id) })
    } catch (reason) { setError(reason) } finally { setBusy(false) }
  }

  return <div className="app">
    <nav ref={navigation} className={`rail${navOpen ? ' rail-open' : ''}`} aria-label="프로젝트와 검토">
      <div className="rail-top"><a className="brand" href="/app"><img src="/assets/sojafit-icon.svg" alt="" width={22} height={22} />SojaFit</a>
        <div className="rail-tools"><button className="icon-btn" onClick={() => { setError(null); creator.current?.showModal() }} aria-label="새 프로젝트" title="새 프로젝트"><FilePlus2 aria-hidden="true" /></button>
          <button ref={navToggle} className="icon-btn nav-toggle" aria-label={navOpen ? '탐색 닫기' : '탐색 열기'} aria-expanded={navOpen} aria-controls="rail-content" onClick={() => setNavOpen(value => !value)}>{navOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}</button></div></div>
      <div className="rail-content" id="rail-content">
      <button className="rail-row" aria-current={projectId === null ? 'true' : undefined} onClick={() => go({})}><Folders aria-hidden="true" />프로젝트</button>
      <button className="rail-row" onClick={() => { setNavOpen(false); setCasesOpen(true) }}><ShieldCheck aria-hidden="true" />승인 사례</button>
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
        {project.data && !demos.isPending && (target || !schematic) && <button className="btn" onClick={() => sheet.current?.showModal()}><Maximize2 aria-hidden="true" />원본 회로도</button>}
      </header>
      {projects.error && projectId === null && <div className="notice inset" role="alert"><p>프로젝트 목록을 불러오지 못했습니다. {errorMessage(projects.error)}</p><button className="btn" onClick={() => void projects.refetch()}>프로젝트 다시 불러오기</button></div>}
      {project.error && <div className="notice inset" role="alert"><p>회로를 불러오지 못했습니다. {errorMessage(project.error)}</p><button className="btn" onClick={() => void project.refetch()}>회로 다시 불러오기</button></div>}
      {!creator.current?.open && !renaming && error ? <p className="notice inset" role="alert">삭제하지 못했습니다. {errorMessage(error)} 같은 삭제 버튼으로 다시 시도해 주세요.</p> : null}
      {projectId !== null && threadId && project.isPending && <div className="skeleton inset" role="status"><span className="sr-only">검토할 회로를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}

      {projectId === null && <section className="list">
        <div className="list-head"><h1 className="sr-only">프로젝트</h1><label className="filter"><Search aria-hidden="true" /><span className="sr-only">프로젝트 찾기</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="이름으로 찾기" /></label>
          <button className="btn btn-primary" onClick={() => { setError(null); creator.current?.showModal() }}><FilePlus2 aria-hidden="true" />새 프로젝트</button></div>
        <table className="rows"><thead><tr><th scope="col">이름</th><th scope="col">종류</th><th scope="col">마지막 수정</th><th scope="col"><span className="sr-only">조작</span></th></tr></thead>
          <tbody>{filteredProjects.map(item => <tr key={item.id} onClick={() => go({ projectId: String(item.id) })} onMouseLeave={() => setConfirming('')}>
            <th scope="row"><button>{item.name}</button></th><td data-label="종류">{item.source_kind === 'demo' ? '예제 회로' : '올린 넷리스트'}</td><td data-label="마지막 수정">{item.updated_at.slice(0, 10)}</td>
            <td data-label="조작" onClick={event => event.stopPropagation()}><span className="row-actions row-actions-end">
              <button className="icon-btn" aria-label={`${item.name} 이름 바꾸기`} title="이름 바꾸기" onClick={() => { setError(null); setRenaming(item) }}><Pencil aria-hidden="true" /></button>
              <button className={confirming === `project-${item.id}` ? 'btn' : 'icon-btn'} aria-label={`${item.name} ${confirming === `project-${item.id}` ? '삭제 확인' : '삭제'}`} title="프로젝트 삭제" onClick={() => void removeProject(item.id)} onBlur={() => setConfirming('')}>{confirming === `project-${item.id}` ? '삭제 확인' : <Trash2 aria-hidden="true" />}</button>
            </span></td></tr>)}</tbody></table>
        {projects.isPending && <div className="skeleton" role="status"><span className="sr-only">프로젝트를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
        {!projects.isPending && !projects.error && projectList.length === 0 && <p className="empty">아직 프로젝트가 없습니다. KiCad 넷리스트를 올려 첫 프로젝트를 만드세요.</p>}
        {!projects.isPending && projectList.length > 0 && !filteredProjects.length && <p className="empty">이름이 일치하는 프로젝트가 없습니다. 검색어를 바꾸거나 지워 주세요.</p>}
      </section>}

      {projectId !== null && !target && !threadId && <section className="list">
        <div className="list-head"><h1 className="sr-only">교체할 부품</h1><label className="filter"><Search aria-hidden="true" /><span className="sr-only">부품 찾기</span><input value={filter} onChange={event => setFilter(event.target.value)} placeholder="참조 번호나 값으로 찾기" /></label></div>
        {partGroups.map(group => {
          const items = filteredParts.filter(part => isDiode(part) === group.eligible)
          if (!items.length) return null
          return <section className={`part-group${group.eligible ? '' : ' part-group-secondary'}`} key={group.title} aria-label={group.title}>
            <div className="section-head"><h2>{group.title}<span className="group-count">{items.length}</span></h2><span>{group.eligible ? '다이오드' : '현재 다이오드만 판정합니다.'}</span></div>
            <table className="rows"><thead><tr><th scope="col">참조</th><th scope="col">값</th><th scope="col">풋프린트</th></tr></thead>
              <tbody>{items.map(part => <tr key={part.ref} className={group.eligible ? undefined : 'dim-row'} onClick={() => go({ projectId: String(projectId), targetRef: part.ref })}>
                <th scope="row"><button>{part.ref}<span className="sr-only"> {part.value} 선택</span></button></th><td data-label="값">{part.value}</td><td data-label="풋프린트">{part.footprint.replace(/^import_input:/, '') || '넷리스트에 없음'}</td></tr>)}</tbody></table>
          </section>
        })}
        {project.isPending && <div className="skeleton" role="status"><span className="sr-only">회로를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
        {!project.isPending && !project.error && !filteredParts.length && <p className="empty">{parts.length ? '참조 번호나 값이 일치하는 부품이 없습니다. 검색어를 바꾸거나 지워 주세요.' : '넷리스트에 부품이 없습니다. 새 프로젝트에서 부품이 있는 파일을 올려 주세요.'}</p>}
      </section>}

      {projectId !== null && target && <Review key={projectId} projectId={projectId} demoId={project.data?.demo_id ?? null} target={target} nets={contextOf(project.data, target.ref)}
        counts={{ parts: parts.length, nets: project.data?.connections.nets.length ?? 0 }} threadId={threadId} reviewer={user.email} onThread={onThread} />}
      {projectId !== null && !target && threadId && project.data && <p className="empty inset">이 검토의 대상 부품을 회로에서 찾지 못했습니다. <button className="btn" onClick={() => go({ projectId: String(projectId) })}>부품 고르기</button></p>}
    </main>

    <dialog ref={renamer} className="dialog" aria-labelledby="renamer-title" onClick={closeOutside} onClose={() => setRenaming(null)}>
      {renaming && <form onSubmit={rename}>
        <h2 id="renamer-title">프로젝트 이름 바꾸기</h2>
        <label className="field"><span>프로젝트 이름</span><input className="input" name="name" required maxLength={80} autoComplete="off" autoFocus defaultValue={renaming.name} /></label>
        {error ? <p className="notice" role="alert">이름을 바꾸지 못했습니다. {errorMessage(error)}</p> : null}
        <div className="dialog-foot"><button type="button" className="btn" onClick={() => renamer.current?.close()}>취소</button><button className="btn btn-primary" disabled={busy}>{busy ? '저장 중' : '이름 저장'}</button></div>
      </form>}
    </dialog>
    <dialog ref={casesDialog} className="dialog dialog-wide" aria-labelledby="cases-title" onClick={closeOutside} onClose={() => setCasesOpen(false)}>
      {casesOpen && <div className="dialog-body"><h2 id="cases-title">승인 사례</h2><ApprovedCases />
        <div className="dialog-foot"><button type="button" className="btn" autoFocus onClick={() => casesDialog.current?.close()}>닫기</button></div></div>}
    </dialog>
    <dialog ref={creator} className="dialog" aria-labelledby="creator-title" onClick={closeOutside}><form onSubmit={create}>
      <h2 id="creator-title">새 프로젝트</h2>
      <label className="field"><span>프로젝트 이름</span><input className="input" name="name" required maxLength={80} autoComplete="off" autoFocus /></label>
      <label className="field"><span>KiCad 넷리스트 (.net, 5 MiB 이하)</span><input className="input" name="netlist" type="file" accept=".net" /></label>
      {demos.isPending && <div className="skeleton" role="status"><span className="sr-only">예제 회로를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
      {demos.error && !demoOff && <div className="notice" role="alert"><p>예제 회로 목록을 불러오지 못했습니다.</p><button type="button" className="btn" onClick={() => void demos.refetch()}>예제 다시 불러오기</button></div>}
      {!demos.isPending && !demos.error && !demoList.length && <p className="property-note">예제 회로가 없습니다. KiCad 넷리스트 파일을 선택해 주세요.</p>}
      {demoList.length > 0 && <label className="field"><span>파일이 없으면 예제 회로로 시작</span><select className="input" name="demo" defaultValue={demoList[0].id}>{demoList.map(demo => <option key={demo.id} value={demo.id}>{demo.name}</option>)}</select></label>}
      {error ? <p className="notice" role="alert">프로젝트를 만들지 못했습니다. {errorMessage(error)} 입력을 확인하고 만들기로 다시 시도해 주세요.</p> : null}
      <div className="dialog-foot"><button type="button" className="btn" onClick={() => creator.current?.close()}>취소</button><button className="btn btn-primary" disabled={busy}>{busy ? '만드는 중' : '만들기'}</button></div>
    </form></dialog>

    <dialog ref={sheet} className="dialog sheet" aria-labelledby="sheet-title" onClick={closeOutside}>
      <header><h2 id="sheet-title">{project.data?.name} 원본 회로도</h2>
        <div className="zoom" role="group" aria-label="확대와 축소"><button className="btn btn-icon" disabled={zoom <= 50} onClick={() => setZoom(value => Math.max(50, value - 25))} aria-label="축소"><Minus aria-hidden="true" /></button><output>{zoom}%</output>
          <button className="btn btn-icon" disabled={zoom >= 400} onClick={() => setZoom(value => Math.min(400, value + 25))} aria-label="확대"><Plus aria-hidden="true" /></button><button className="btn" onClick={() => setZoom(100)}>맞춤</button></div>
        <button className="icon-btn" onClick={() => sheet.current?.close()} aria-label="닫기"><X aria-hidden="true" /></button></header>
      {schematic ? <SchematicImage key={schematic.image_url} schematic={schematic} name={project.data?.name ?? ''} zoom={zoom} /> : <ExternalSchematic key={project.data?.id} name={project.data?.name ?? ''} zoom={zoom} />}
    </dialog>
  </div>
}
