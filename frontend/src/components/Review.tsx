import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUp, Check, CircleDashed, FileText, LoaderCircle, Paperclip, X, RotateCw, Square } from 'lucide-react'
import { getRun, listDemoQuestions, listJudgeRoles } from '../api/conversations'
import type { ResultDto } from '../api/conversations'
import type { CircuitPart } from '../api/projects'
import { errorMessage, requestIdProps } from '../api/client'
import { useConversation } from '../hooks/useConversation'
import { useNetlistFiles } from '../hooks/useNetlistFiles'
import type { ContextNet } from '../lib/circuit'
import { VERDICT_LABELS, VERDICT_TONE, candidatesOf, documentEvidenceOf, judgementOf, withoutCorpusCitations } from '../lib/judgement'
import { INPUT_LABELS, inputPlaceholder } from '../lib/inputLabels'
import ContextDiagram from './ContextDiagram'
import ChatPane from './ChatPane'
import ReviewDetails from './ReviewDetails'
import type { DetailTab } from './ReviewDetails'
import SafeMarkdown from './SafeMarkdown'

const PROPS_KEY = 'sojafit:props-width'
const PROPS_DEFAULT = 280, PROPS_MIN = 240, PROPS_MAX = 480

type Props = { projectId: number; demoId: string | null; target: CircuitPart; nets: ContextNet[]; counts: { parts: number; nets: number }; threadId: string; reviewer: string; initialQuestion?: string
  onThread: (threadId: string, targetRef?: string) => void; onAttach: (file: File, question: string, signal: AbortSignal) => Promise<void> }

function Reply({ result, selectedPart, onSelect, onEvidence }: { result: ResultDto; selectedPart?: string; onSelect: (part: string) => void; onEvidence: () => void }) {
  if (result.status === 'running' || result.status === 'requires_input' || result.status === 'failed') return <div className="activity-reply" role="group" aria-label="AI 답변"><div className="activity-body">
    <p>{result.status === 'requires_input' ? '추가 조건 입력을 기다리고 있습니다.' : result.status === 'running' ? '검토가 진행 중입니다.' : '검토를 완료하지 못했습니다.'}</p>
    {result.error && <p className="notice" role="alert">{errorMessage(result.error)}</p>}
  </div></div>
  const candidates = candidatesOf(result)
  const uncertain = candidates.some(item => item.missing?.length || item.uncertain?.length)
  // shortcut: 서버 render_judgement의 고정 경계만 제거한다. 답변 형식이 바뀌면 별도 설명 필드를 계약에 추가한다.
  const prose = result.answer.replace(/\r\n?/g, '\n').replace(/^역할: [^\n]* \(근거: [^\n]*\)\n[\s\S]*?^같은 동작은 보장하지 않습니다\.[ \t]*$/gm, '').trim()
  const displayText = (text: string) => withoutCorpusCitations(text, result.evidence)
  return <div className="activity-reply" role="group" aria-label="AI 답변">
    <div className="activity-body">
      {result.refusal ? <p>{displayText(result.refusal)}</p> : candidates.length ? <div className="candidate-summary">
        <p>{candidates.length === 1 ? `${candidates[0].part} 검토 결과는 ‘${VERDICT_LABELS[candidates[0].verdict]}’입니다.` : `후보 ${candidates.length}개의 검토 결과를 정리했어요.`}</p>
        {candidates.length === 1 && candidates[0].board_change === true && <p>기판 수정이 필요하니 장착 조건도 함께 확인해 주세요.</p>}
        {uncertain && <p>문서에서 확인하지 못했거나 불확실한 항목이 있어요. 상세의 확인 사항을 함께 봐 주세요.</p>}
        {judgementOf(result)?.capped && <p>검색이 후보 수 상한에 닿았어요. 패키지나 분류 조건을 더 정하면 범위를 좁힐 수 있어요.</p>}
        <p>부품의 상세 보기를 누르면 판정과 조건 대조, 데이터시트 근거를 함께 확인할 수 있어요.</p>
        <ul className="candidate-links" aria-label="부품별 상세 보기">{candidates.map(item => <li key={item.part}><button className="candidate-link" aria-controls="candidate-details" aria-expanded={selectedPart === item.part} onClick={() => onSelect(item.part)}>
          <strong>{item.part}</strong><span className={`dot tone-${VERDICT_TONE[item.verdict]}`}>{VERDICT_LABELS[item.verdict]}</span><span>상세 보기</span><ArrowRight aria-hidden="true" />
        </button></li>)}</ul>
        {prose && <SafeMarkdown text={prose} renderText={displayText} />}
      </div> : result.answer ? <SafeMarkdown text={result.answer} renderText={displayText} /> : <p>{result.status === 'failed' ? '실행에 실패했습니다.' : '결과에 판정이 없습니다.'}</p>}
      {documentEvidenceOf(result).length > 0 && <button className="candidate-link" aria-controls="candidate-details" onClick={onEvidence}><FileText aria-hidden="true" />문서 근거 보기<ArrowRight aria-hidden="true" /></button>}
    </div></div>
}

// 선택하지 않은 지난 질문의 답. 선택된 질문과 같은 ['run', id] 캐시를 써서 실행마다 한 번만 읽는다.
function PastReply({ runId, selectedPart, onSelect, onEvidence }: { runId: string; selectedPart?: string; onSelect: (part: string) => void; onEvidence: () => void }) {
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId, signal), retry: false, staleTime: Infinity })
  if (run.data) return <Reply result={run.data.result} selectedPart={selectedPart} onSelect={onSelect} onEvidence={onEvidence} />
  return <p className="fine">{run.isError ? '답변을 불러오지 못했습니다.' : '답변을 불러오는 중입니다.'}</p>
}

// 대화에서 후보를 고르면 같은 질문의 판정과 근거를 속성 칸에 보인다.
export default function Review({ projectId, demoId, target, nets, counts, threadId, reviewer, initialQuestion, onThread, onAttach }: Props) {
  const chat = useConversation({ projectId, targetRef: target.ref, threadId, onThread })
  // StrictMode의 첫 effect 정리가 끝난 뒤 실제로 남은 화면에서 한 번만 보낸다.
  const sentInitial = useRef(false)
  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active && initialQuestion && !sentInitial.current) { sentInitial.current = true; void chat.send({ question: initialQuestion }) } })
    return () => { active = false }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps -- 처음 열릴 때만
  const { history, live, stages, state, running, waiting, picked } = chat
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [role, setRole] = useState('')
  const activeRunId = 'runId' in state ? state.runId : ''
  useEffect(() => { setAnswers({}); setRole('') }, [activeRunId])
  const attachmentPending = chat.files.length > 0
  const input = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const attachments = useNetlistFiles(chat.files, chat.setFiles, input, running || chat.loading, `${threadId}:${target.ref}`, chat.text, onAttach)
  const [selected, setSelected] = useState<DetailTab | null>(null)
  const [detailTabs, setDetailTabs] = useState<DetailTab[]>([])
  useEffect(() => {
    setDetailTabs(current => current.map(tab => {
      const index = history.findIndex(item => item.runId === tab.runId)
      if (index < 0) return tab
      const label = `${tab.part ?? '문서 근거'} · 질문 ${index + 1}`
      return label === tab.label ? tab : { ...tab, label }
    }))
  }, [history])
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [focusDetails, setFocusDetails] = useState(false)
  const detailTrigger = useRef<HTMLElement | null>(null)
  const selectionContext = useRef({ threadId, targetRef: target.ref })
  const viewport = useRef<HTMLDivElement>(null)
  const [scrollable, setScrollable] = useState(false)
  const [propsWidth, setPropsWidth] = useState(() => {
    try { const saved = Number(localStorage.getItem(PROPS_KEY)); return saved >= PROPS_MIN && saved <= PROPS_MAX ? saved : PROPS_DEFAULT } catch { return PROPS_DEFAULT }
  })
  function resizeProps(width: number) {
    const next = Math.min(PROPS_MAX, Math.max(PROPS_MIN, Math.round(width)))
    setPropsWidth(next)
    try { localStorage.setItem(PROPS_KEY, String(next)) } catch { /* 저장소를 막은 브라우저에서는 이번 화면에서만 유지한다 */ }
  }
  // 개념도가 실제로 넘칠 때만 키보드 스크롤용 초점을 준다.
  useEffect(() => {
    const element = viewport.current
    if (!element) return
    const check = () => setScrollable(element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)
    check()
    const observer = new ResizeObserver(check)
    observer.observe(element)
    return () => observer.disconnect()
  }, [nets])
  const turn = picked !== null ? history.find(item => item.runId === picked) : live ? null : history[history.length - 1]
  const liveResult = !turn && (state.status === 'completed' || state.status === 'refused') ? state.result : undefined
  const runId = turn?.runId ?? (liveResult && 'runId' in state ? state.runId : '')
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId!, signal), enabled: Boolean(runId), retry: false, staleTime: Infinity })
  // 키 없는 데모에서만 있는 목록이다. 없으면(404) 버튼을 숨긴다.
  const demoQuestions = useQuery({ queryKey: ['demo-questions'], queryFn: ({ signal }) => listDemoQuestions(signal), retry: false, staleTime: Infinity, enabled: demoId !== null })
  const recorded = Array.isArray(demoQuestions.data) ? demoQuestions.data.filter(item => item.demo_id === demoId) : []
  const recordedHere = recorded.filter(item => item.target === target.ref)
  const recordedResume = live ? recordedHere.find(item => item.question === live.question)?.resume ?? null : null
  const result: ResultDto | undefined = liveResult ?? (turn ? run.data?.result : undefined)
  const selectedPart = detailsOpen && selected && selected.runId === runId ? selected.part ?? undefined : undefined
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, staleTime: Infinity })
  // [왜] 대체품 찾기는 사용 조건과 원하는 정격이 있어야 비교할 기준이 생긴다. 예시도 조건을 함께 적는다
  const examples = [`${target.ref}을 SS34로 바꿔도 되나요? 입력 최대 12V, ${target.ref} 전류 최대 1A, 주변 온도 25°C예요.`,
    `${target.ref}의 대체 후보를 찾아 주세요. 입력 최대 12V, 전류 최대 1A, 주변 온도 25°C예요. 역전압 정격 20V 이상, 평균 전류 정격 1A 이상이면 됩니다.`]
  function selectPart(id: string | undefined, part: string | null, index: number | null) {
    if (!id) return
    const tab = { key: `${id}/${part ?? ''}`, runId: id, part, label: `${part ?? '문서 근거'} · 질문 ${(index ?? history.length) + 1}` }
    detailTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    setDetailTabs(current => current.some(item => item.key === tab.key) ? current : [...current, tab])
    setSelected(tab)
    setDetailsOpen(true)
    setFocusDetails(true)
  }
  function closeDetail(tab: DetailTab) {
    const index = detailTabs.indexOf(tab)
    const next = detailTabs.filter(item => item.key !== tab.key)
    setDetailTabs(next)
    if (selected?.key === tab.key) setSelected(next[Math.min(index, next.length - 1)] ?? null)
    setFocusDetails(false)
  }
  function dismissDetails() { setDetailsOpen(false); setSelected(null); setFocusDetails(false); detailTrigger.current?.focus({ preventScroll: true }) }
  const response = result && <Reply result={result} selectedPart={selectedPart} onSelect={part => selectPart(runId, part, turn ? history.indexOf(turn) : null)} onEvidence={() => selectPart(runId, null, turn ? history.indexOf(turn) : null)} />
  useEffect(() => {
    const previous = selectionContext.current
    if (previous.targetRef !== target.ref || (previous.threadId && previous.threadId !== threadId)) { setSelected(null); setDetailTabs([]); setDetailsOpen(false); input.current?.focus({ preventScroll: true }) }
    selectionContext.current = { threadId, targetRef: target.ref }
  }, [threadId, target.ref])
  useEffect(() => { if (!selected) input.current?.focus({ preventScroll: true }) }, [target.ref, threadId])
  function send() {
    if (running || chat.loading || attachments.busy) return
    if (attachmentPending) return attachments.send()
    return chat.send()
  }
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 한글 조합 중의 Enter는 글자 확정이다. 전송하지 않는다.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send() }
  }

  // 질문을 보내기 전에는 제목과 입력창만 보인다. 회로 · 조건 대조 · 속성은 검토가 시작되면 나타난다.
  const started = history.length > 0 || Boolean(live) || chat.loading
  return <div ref={root} className={`review${started ? '' : ' review-idle'}`} style={{ '--props': `${propsWidth}px` } as CSSProperties}>
    {attachments.dragging && <div className="attachment-drop-guide" role="status" aria-label="파일 놓기"><Paperclip aria-hidden="true" /><p>.net·.txt 파일을 놓으면 채팅에 첨부됩니다.</p><p className="fine">파일당 5 MiB 이하 · 전송 전에 확인할 수 있습니다.</p></div>}
    <div className="review-body" role="region" aria-label="검토 내용">
    <div className="review-main">
    <ChatPane context={`${threadId}:${target.ref}`} input={input} older={{ before: chat.before, loading: chat.loadingOlder, error: chat.olderError, load: chat.loadOlder }} composer={<>
      {attachments.error ? <div className="notice notice-dismissible" role="alert"><p>{errorMessage(attachments.error)}</p><button type="button" className="icon-btn" aria-label="첨부 안내 닫기" onClick={() => attachments.setError(null)}><X aria-hidden="true" /></button></div> : null}
      <form className="composer" onSubmit={(event) => { event.preventDefault(); void send() }}>
        <label className="sr-only" htmlFor="question">질문</label>
        <textarea id="question" ref={input} rows={2} readOnly={attachments.busy} aria-describedby="composer-hint" value={chat.text} onChange={event => chat.setText(event.target.value)} onKeyDown={onKey} placeholder={waiting ? "위 조건 질문에 먼저 답하거나 '모두 모름으로 계속'을 눌러 주세요." : "후보 품번과 사용 조건을 적어 주세요."} />
        <input ref={picker} type="file" accept=".net,.txt" multiple hidden onChange={event => { attachments.attach(Array.from(event.target.files ?? [])); event.target.value = '' }} />
          <button type="button" className="btn btn-icon" disabled={running || chat.loading || attachments.busy} onClick={() => picker.current?.click()} aria-label="파일 첨부 (.net, .txt)" title="파일 첨부 (.net, .txt)"><Paperclip aria-hidden="true" /></button>
        {running && state.status !== 'stopped' && state.status !== 'failed' ? <button type="button" className="btn btn-icon" onClick={chat.stream.cancel} aria-label="응답 받기 중단"><Square aria-hidden="true" /></button>
          : <button className="btn btn-icon" disabled={running || chat.loading || attachments.busy || (!attachmentPending && (waiting || !chat.text.trim()))} aria-label="질문 보내기"><ArrowUp aria-hidden="true" /></button>}
      </form>
      {chat.files.length > 0 && <ul className="chips" aria-label="첨부한 파일">{chat.files.map((file, index) => <li key={`${file.name}-${index}`}><FileText aria-hidden="true" /><span>{file.name}</span>
        <button type="button" className="icon-btn" disabled={attachments.busy} aria-label={`${file.name} 첨부 취소`} onClick={() => chat.setFiles(chat.files.filter((_, at) => at !== index))}><X aria-hidden="true" /></button></li>)}</ul>}
      {attachmentPending && <p className="composer-hint">{attachments.busy ? '넷리스트를 읽는 중입니다…' : '전송하면 같은 프로젝트의 새 회로 버전·새 대화로 이어집니다.'}</p>}
      <p id="composer-hint" className="composer-hint meta-fields"><span>Enter로 보내기</span><span>Shift + Enter로 줄바꿈</span></p>

    </>}>
    <div className="doc review-context">
      <header className="doc-head">
        <h1><span className="ref">{target.ref}</span><span>{target.value}</span></h1>
      </header>
      <p className="doc-lead">{state.status === 'stopped' ? '응답 수신을 중단했습니다. 실행 상태를 확인해 주세요.' : running ? '검토 중입니다. 결과를 받으면 대화에서 확인할 수 있습니다.' : `${target.ref}을 다른 부품으로 바꿔도 되는지 검토합니다. 후보 품번과 사용 조건을 적어 보내세요.`}</p>
      {result && <p className="fine">같은 동작은 보장하지 않습니다. 판정은 데이터시트 값과 입력한 조건으로 계산한 결과입니다.</p>}

      <section aria-labelledby="circuit-title"><div className="section-head"><h2 id="circuit-title">회로</h2><span>선택 부품의 연결</span></div>
        <div className="panel circuit-panel">
          <div ref={viewport} className="diagram-viewport" tabIndex={scrollable ? 0 : undefined} role="region" aria-label="회로 연결 개념도"><ContextDiagram targetRef={target.ref} targetValue={target.value} nets={nets} /></div>
        </div></section>

    </div>
      <section className="talk" aria-labelledby="activity-title"><h2 id="activity-title">활동</h2>
        <ol className="activity">
          {chat.loading && <li className="skeleton" role="status"><span className="sr-only">검토 기록을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></li>}
          {history.map((item, index) => <li className="activity-entry" key={item.runId} data-turn={item.runId}>
            <div className="activity-message" role="group" aria-label={`내 메시지 ${index + 1}`}><div className="activity-body">
              <button className="activity-turn" aria-current={turn === item ? 'true' : undefined} onClick={() => chat.setPicked(item.runId)}>{item.question}</button>
            </div></div>{turn === item ? response : <PastReply runId={item.runId} selectedPart={selected?.runId === item.runId ? selected.part ?? undefined : undefined} onSelect={part => selectPart(item.runId, part, index)} onEvidence={() => selectPart(item.runId, null, index)} />}
          </li>)}
          {live && <li className="activity-entry"><div className="activity-message" role="group" aria-label={`내 메시지 ${history.length + 1}`}><div className="activity-body">
            <button className="activity-turn" aria-current={picked === null ? 'true' : undefined} onClick={() => chat.setPicked(null)}>{live.question}</button>
          </div></div>
            {stages.length > 0 && <ol className="activity-steps" aria-label="AI 진행 상태">{stages.map((stage, index) => <li className="activity-stage" key={stage}>
              {index === stages.length - 1 && state.status === 'running' ? <LoaderCircle className="spin" aria-hidden="true" /> : index === stages.length - 1 && state.status !== 'completed' ? <CircleDashed aria-hidden="true" /> : <Check aria-hidden="true" />}<span>{stage}</span>
            </li>)}</ol>}
            {!turn && response}</li>}
          {!history.length && !live && !chat.loading && <li className="activity-stage"><CircleDashed aria-hidden="true" /><span>아직 질문이 없습니다. 아래 예시로 시작할 수 있습니다.</span></li>}
        </ol>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{live && (state.status === 'stopped' ? '응답 수신 중단' : running ? `AI: ${stages[stages.length - 1] || '검토 시작'}` : state.status === 'completed' ? '검토 결과를 받았습니다.' : state.status === 'requires_input' ? '추가 입력이 필요합니다.' : state.status === 'failed' ? '실행에 실패했습니다.' : state.status === 'refused' ? '답변이 거절되었습니다.' : '')}</div>
        {state.status === 'stopped' && <div className="notice"><p>응답 수신 중단. 서버의 검토는 계속될 수 있습니다. 상태를 확인한 뒤 다음 질문을 보내 주세요.</p>
          {state.checking === false && !state.error && <p>서버에서 아직 검토 중입니다. 잠시 후 실행 상태를 다시 확인해 주세요.</p>}
          {state.error && <p role="alert" {...requestIdProps(state.error)}>실행 상태를 확인하지 못했습니다. {errorMessage(state.error)}</p>}
          {state.runId ? <button className="btn" disabled={state.checking} onClick={() => void chat.stream.refresh(state.runId, true)}><RotateCw aria-hidden="true" />{state.checking ? '실행 상태 확인 중' : '실행 상태 다시 확인'}</button>
            : <><p>실행 번호를 받기 전에 중단했습니다. 대화를 새로고침해 저장된 상태를 확인해 주세요. 작성 중인 질문은 지워집니다.</p><button className="btn" onClick={() => window.location.reload()}>대화 새로고침</button></>}
        </div>}
        {state.status === 'failed' && <div className="notice" role="alert"><p {...requestIdProps(state.error)}>검토 실행에 실패했습니다. {errorMessage(state.error)}{!state.runId && ' 아래 질문을 입력해 다시 보내 주세요.'}</p>{state.runId && <button className="btn" onClick={() => void chat.stream.refresh(state.runId!)}><RotateCw aria-hidden="true" />실행 상태 다시 확인</button>}</div>}
        {run.error && <div className="notice" role="alert"><p {...requestIdProps(run.error)}>검토 결과를 불러오지 못했습니다. {errorMessage(run.error)}</p><button className="btn" onClick={() => void run.refetch()}>결과 다시 불러오기</button></div>}
        {state.status === 'requires_input' && state.error && <div className="notice" role="alert"><p {...requestIdProps(state.error)}>검토를 계속하지 못했습니다. {errorMessage(state.error)}</p><p className="fine">분석은 자동으로 다시 실행하지 않습니다.</p></div>}
        {state.status === 'requires_input' && <form className="ask" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget)
          void chat.stream.resume(state.runId, { answers: Object.fromEntries((state.interrupt.missing ?? []).map(code => [code, String(data.get(code) ?? '').trim()]).filter(([, value]) => value)), role: String(data.get('role') ?? '') || undefined }) }}>
          <h3>{state.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</h3>
          <p className="fine">모르는 값은 비워 두세요. 빈 칸은 '모름'으로 검토합니다.</p>
          {(state.interrupt.role_choices ?? []).map((code, index) => <label key={code} className="choice"><input type="radio" name="role" value={code} checked={role ? role === code : index === 0} onChange={() => setRole(code)} />{(Array.isArray(roles.data) ? roles.data.find(item => item.code === code)?.name : '') || '역할'}</label>)}
          {(state.interrupt.missing ?? []).map(code => <label className="field" key={code}><span>{INPUT_LABELS[code] ?? '추가 조건'}</span><input className="input" name={code} autoComplete="off" placeholder={inputPlaceholder(code)} value={answers[code] ?? ''} onChange={event => { const value = event.currentTarget.value; setAnswers(current => ({ ...current, [code]: value })) }} /></label>)}
          <div className="form-actions"><button className="btn btn-primary">이 값으로 계속 검토</button>
            <button type="button" className="btn" onClick={event => void chat.stream.resume(state.runId, { answers: {}, role: String(new FormData(event.currentTarget.form!).get('role') ?? '') || undefined })}>모두 모름으로 계속</button>
            {recordedResume && <button type="button" className="btn" onClick={() => void chat.stream.resume(state.runId, { answers: recordedResume.answers, role: recordedResume.role || undefined })}>기록한 답으로 계속하기</button>}</div></form>}
        {chat.error ? <div className="notice" role="alert"><p {...requestIdProps(chat.error)}>검토 기록을 불러오거나 질문을 보내지 못했습니다. {errorMessage(chat.error)} 새로고침하면 작성 중인 질문은 지워집니다.</p><button className="btn" onClick={() => window.location.reload()}>페이지 새로고침</button></div> : null}
        {!history.length && !live && recorded.length > 0 && <div className="demo-questions"><p className="composer-hint">키 없는 데모는 기록한 질문만 재생합니다.{recordedHere.length === 0 && ` 이 회로에서 기록한 질문이 있는 부품은 ${[...new Set(recorded.map(item => item.target))].join(', ')}입니다.`}</p>
          {recordedHere.length > 0 && <ul className="examples">{recordedHere.map(item => <li key={item.id}><button disabled={attachmentPending} title={item.conditions} onClick={() => void chat.send({ question: item.question, conditions: item.conditions })}>{item.question}</button></li>)}</ul>}</div>}
        {!history.length && !live && recorded.length === 0 && <ul className="examples">{examples.map(example => <li key={example}><button onClick={() => { chat.setText(example); input.current?.focus() }}>{example}</button></li>)}</ul>}
      </section>
    </ChatPane>
    </div>

    {/* 끌어서 속성 칸 너비를 바꾼다. 두 번 누르면 기본 너비로 돌아간다. */}
    <div className="props-resize" role="separator" aria-orientation="vertical" aria-label="속성 칸 너비 조절" title="끌어서 너비 조절, 두 번 눌러 기본값" tabIndex={0}
      aria-valuenow={propsWidth} aria-valuemin={PROPS_MIN} aria-valuemax={PROPS_MAX}
      onPointerDown={event => event.currentTarget.setPointerCapture(event.pointerId)}
      onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId) && root.current) resizeProps(root.current.getBoundingClientRect().right - event.clientX) }}
      onDoubleClick={() => resizeProps(PROPS_DEFAULT)}
      onKeyDown={event => { if (event.key === 'ArrowLeft') { event.preventDefault(); resizeProps(propsWidth + 16) } else if (event.key === 'ArrowRight') { event.preventDefault(); resizeProps(propsWidth - 16) } }} />
    <ReviewDetails tabs={detailTabs} selected={selected} open={detailsOpen} onSelect={tab => { setSelected(tab); setFocusDetails(false) }} onClose={closeDetail} onDismiss={dismissDetails}
      focus={focusDetails} onFocused={() => setFocusDetails(false)} runId={runId || ''} result={result} target={target} nets={nets} counts={counts} reviewer={reviewer} />
    </div>

  </div>
}
