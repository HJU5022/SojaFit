import { useCallback, useEffect, useRef, useState } from 'react'
import type { CSSProperties, FormEvent, KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowDown, ArrowRight, ArrowUp, Check, CircleDashed, ExternalLink, FileText, LoaderCircle, Paperclip, X, RotateCw, ShieldCheck, Square } from 'lucide-react'
import { getRun, listDemoQuestions, listJudgeRoles } from '../api/conversations'
import type { CandidateDto, ResultDto } from '../api/conversations'
import type { CircuitPart } from '../api/projects'
import { errorMessage, requestIdProps } from '../api/client'
import { approveMessage, createQuote } from '../api/quotes'
import type { ApprovalDto, QuoteDto } from '../api/quotes'
import { useConversation } from '../hooks/useConversation'
import type { ContextNet } from '../lib/circuit'
import { CHECK_LABELS, VERDICT_LABELS, VERDICT_TONE, candidatesOf, citationHref, citationText, documentEvidenceOf, formatValue, judgementOf, withoutCorpusCitations } from '../lib/judgement'
import { INPUT_LABELS, inputPlaceholder } from '../lib/inputLabels'
import ContextDiagram from './ContextDiagram'
import PriceLookup from './PriceLookup'
import SafeMarkdown from './SafeMarkdown'

const PROPS_KEY = 'sojafit:props-width'
const PROPS_DEFAULT = 280, PROPS_MIN = 240, PROPS_MAX = 480
const ATTACHMENT_MAX_BYTES = 5 * 1024 * 1024

type Props = { projectId: number; demoId: string | null; target: CircuitPart; nets: ContextNet[]; counts: { parts: number; nets: number }; threadId: string; reviewer: string; initialQuestion?: string
  onThread: (threadId: string, targetRef?: string) => void }

export function Checks({ candidate, resolved, showDocument = false }: { candidate: CandidateDto | undefined; resolved: boolean; showDocument?: boolean }) {
  const rows = candidate?.checks ?? []
  return <div className="table-scroll"><table className="checks">
    <caption className="sr-only">후보 {candidate?.part ?? '부품'}의 조건별 요구 값과 데이터시트 근거</caption>
    <thead><tr><th scope="col">항목</th><th scope="col">기준</th><th scope="col" className="num">요구</th><th scope="col" className="num">후보 값</th><th scope="col">결과</th><th scope="col">근거 위치</th></tr></thead>
    <tbody>{rows.length === 0 ? <tr className="checks-empty"><td colSpan={6}>{resolved ? '이 결과에는 조건별 대조 값이 없습니다. 아래 질문에 후보와 사용 조건을 보완해 주세요.' : '검토 후 대조 값이 표시됩니다. 아래에 후보와 사용 조건을 입력해 주세요.'}</td></tr>
      : rows.map((check) => {
        const href = citationHref(check.citation)
        const citation = check.citation
        const where = citation && ((showDocument && citation.document) || (citation.page != null && citation.page !== '') || citation.table || citation.row) ? <>
          {showDocument && citation.document && <span className="citation-document">{citation.document}</span>}
          {citation.page != null && citation.page !== '' && <span>{citation.page}쪽</span>}
          {citation.table && <span><span className="sr-only">표: </span>{citation.table}</span>}
          {citation.row && <span><span className="sr-only">행: </span>{citation.row}</span>}
        </> : <span>출처 위치 없음</span>
        const state = check.result ?? 'unverified'
        return <tr key={check.code}>
          <th scope="row">{check.code}</th>
          <td className="basis" data-label="기준">{check.basis}</td>
          <td className="num" data-label="요구">{check.threshold != null && check.op ? `${check.op === '>=' ? '≥' : check.op === '<=' ? '≤' : check.op} ` : ''}{formatValue(check.threshold, check.unit) || '값 없음'}</td>
          <td className="num strong" data-label="후보 값" title={check.condition ?? undefined}>{formatValue(check.value, check.unit) || '값 없음'}{showDocument && <p className="property-note">시험 조건: {check.condition || '표 기본 조건'}</p>}</td>
          <td data-label="결과"><span className={`result tone-${state === 'pass' ? 'identical' : state === 'fail' ? 'insufficient' : 'unverified'}`}>{CHECK_LABELS[state] ?? '확인 안 됨'}</span>{showDocument && check.why && <p className="property-note">{check.why}</p>}</td>
          <td data-label="근거" title={check.citation?.document ?? undefined}>{href ? <a className="citation-fields" href={href} target="_blank" rel="noreferrer">{where}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span className="citation-fields">{where}</span>}</td>
        </tr>
      })}</tbody>
  </table></div>
}

function Approval({ candidate, messageId, reviewer }: { candidate: CandidateDto; messageId: number | null; reviewer: string }) {
  const [approval, setApproval] = useState<ApprovalDto | null>(null)
  const [quote, setQuote] = useState<QuoteDto | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const approvable = candidate.verdict !== 'NOT_VERIFIED' && candidate.verdict !== 'NOT_SUFFICIENT'
  async function act(job: () => Promise<void>) { if (busy) return; setBusy(true); setError(null); try { await job() } catch (reason) { setError(reason) } finally { setBusy(false) } }
  function openQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const quantity = Math.max(1, Math.floor(Number(new FormData(event.currentTarget).get('quantity'))) || 1)
    void act(async () => setQuote(await createQuote(approval!.id, quantity)))
  }
  return <div className="approval">
    <p className="approval-state">{approval ? <ShieldCheck aria-hidden="true" /> : <CircleDashed aria-hidden="true" />}{approval ? '승인됨' : '승인 전'}</p>
    {approval && <p className="property-note">{reviewer}</p>}
    {quote && <p className="property-note">견적 {quote.part_number} × {quote.quantity}</p>}
    {!approval && <button className="btn btn-primary" disabled={busy || messageId === null || !approvable} onClick={() => void act(async () => setApproval(await approveMessage(messageId!, candidate.part, candidate.verdict)))}>{busy ? '저장 중' : '검토하고 승인'}</button>}
    {!approvable && <p className="property-note">이 판정은 승인 대상이 아닙니다.</p>}
    {approval && !quote && <form className="quote" onSubmit={openQuote}><label className="sr-only" htmlFor="quantity">수량</label><input id="quantity" name="quantity" className="input" type="number" min={1} defaultValue={1} inputMode="numeric" /><button className="btn btn-primary" disabled={busy}>견적 열기</button></form>}
    {error ? <p className="notice" role="alert" {...requestIdProps(error)}>{approval ? '견적을 저장하지 못했습니다. 견적 열기로 다시 시도해 주세요.' : '승인을 저장하지 못했습니다. 검토하고 승인으로 다시 시도해 주세요.'} {errorMessage(error)}</p> : null}
  </div>
}

function Reply({ result, selectedPart, onSelect, onEvidence }: { result: ResultDto; selectedPart?: string; onSelect: (part: string) => void; onEvidence: () => void }) {
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
      {documentEvidenceOf(result).length > 0 && <button className="candidate-link" aria-controls="evidence-heading" onClick={onEvidence}><FileText aria-hidden="true" />문서 근거 보기<ArrowRight aria-hidden="true" /></button>}
    </div></div>
}

// 선택하지 않은 지난 질문의 답. 선택된 질문과 같은 ['run', id] 캐시를 써서 실행마다 한 번만 읽는다.
function PastReply({ runId, selectedPart, onSelect, onEvidence }: { runId: string; selectedPart?: string; onSelect: (part: string) => void; onEvidence: () => void }) {
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId, signal), retry: false, staleTime: Infinity })
  if (run.data) return <Reply result={run.data.result} selectedPart={selectedPart} onSelect={onSelect} onEvidence={onEvidence} />
  return <p className="fine">{run.isError ? '답변을 불러오지 못했습니다.' : '답변을 불러오는 중입니다.'}</p>
}

// 대화에서 후보를 고르면 같은 질문의 판정과 근거를 속성 칸에 보인다.
export default function Review({ projectId, demoId, target, nets, counts, threadId, reviewer, initialQuestion, onThread }: Props) {
  const chat = useConversation({ projectId, targetRef: target.ref, threadId, onThread })
  const { setFiles } = chat
  // 부품 목록의 질문 칸에서 넘어온 질문을 한 번만 보낸다. ref는 StrictMode의 effect 재실행에도 남는다.
  const sentInitial = useRef(false)
  useEffect(() => { if (initialQuestion && !sentInitial.current) { sentInitial.current = true; void chat.send({ question: initialQuestion }) } }, []) // eslint-disable-line react-hooks/exhaustive-deps -- 처음 열릴 때만
  const { history, live, stages, state, running, waiting, picked } = chat
  const attachmentPending = chat.files.length > 0
  const input = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const body = useRef<HTMLDivElement>(null)
  const talk = useRef<HTMLElement>(null)
  const conversationEnd = useRef<HTMLSpanElement>(null)
  const [showJump, setShowJump] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [attachmentError, setAttachmentError] = useState<string | null>(null)
  const details = useRef<HTMLHeadingElement>(null)
  const evidenceHeading = useRef<HTMLHeadingElement>(null)
  const [selected, setSelected] = useState<{ runId: string; part: string | null } | null>(null)
  const selectionContext = useRef({ threadId, targetRef: target.ref })
  const viewport = useRef<HTMLDivElement>(null)
  const [scrollable, setScrollable] = useState(false)
  const [propsWidth, setPropsWidth] = useState(() => {
    try { const saved = Number(localStorage.getItem(PROPS_KEY)); return saved >= PROPS_MIN && saved <= PROPS_MAX ? saved : PROPS_DEFAULT } catch { return PROPS_DEFAULT }
  })
  const attachFiles = useCallback((incoming: File[]) => {
    const valid = incoming.filter(file => /\.(net|txt)$/i.test(file.name) && file.size > 0 && file.size <= ATTACHMENT_MAX_BYTES)
    setAttachmentError(valid.length !== incoming.length || !incoming.length ? '.net·.txt 형식의 비어 있지 않은 5 MiB 이하 파일만 첨부할 수 있습니다.' : null)
    setFiles(current => {
      const next = [...current]
      for (const file of valid) if (!next.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) next.push(file)
      return next
    })
    return valid.length > 0
  }, [setFiles])
  useEffect(() => { setAttachmentError(null) }, [threadId, target.ref])
  useEffect(() => {
    let depth = 0
    const reset = () => { depth = 0; setDragging(false) }
    const fileDrag = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes('Files')
    const dialogOpen = () => Boolean(document.querySelector('dialog[open]'))
    const nativePicker = (event: DragEvent) => event.target instanceof HTMLInputElement && event.target.type === 'file' && !event.target.disabled
    const blocked = !import.meta.env.DEV || running || chat.loading
    function enter(event: DragEvent) {
      if (!fileDrag(event)) return
      if (nativePicker(event)) { reset(); return }
      event.preventDefault()
      if (dialogOpen()) { reset(); return }
      if (!blocked) { depth++; setDragging(true) }
    }
    function over(event: DragEvent) {
      if (!fileDrag(event) || nativePicker(event)) return
      event.preventDefault()
      if (event.dataTransfer) event.dataTransfer.dropEffect = blocked || dialogOpen() ? 'none' : 'copy'
    }
    function leave() { if (depth > 0 && --depth === 0) setDragging(false) }
    function drop(event: DragEvent) {
      if (!fileDrag(event)) return
      reset()
      if (nativePicker(event)) return
      event.preventDefault()
      if (dialogOpen()) return
      if (blocked) { setAttachmentError(!import.meta.env.DEV ? '현재 운영에서는 질문 파일 첨부를 지원하지 않습니다. API 연동 확인 후 사용할 수 있습니다.' : '검토 기록 복원이나 진행 중인 응답이 끝난 뒤 파일을 첨부해 주세요.'); return }
      if (attachFiles(Array.from(event.dataTransfer?.files ?? []))) input.current?.focus({ preventScroll: true })
    }
    reset()
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    window.addEventListener('dragend', reset)
    window.addEventListener('blur', reset)
    return () => {
      window.removeEventListener('dragenter', enter)
      window.removeEventListener('dragover', over)
      window.removeEventListener('dragleave', leave)
      window.removeEventListener('drop', drop)
      window.removeEventListener('dragend', reset)
      window.removeEventListener('blur', reset)
    }
  }, [attachFiles, running, chat.loading, threadId, target.ref])
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
  const turn = picked !== null ? history[picked] : live ? null : history[history.length - 1]
  const liveResult = !turn && (state.status === 'completed' || state.status === 'refused') ? state.result : undefined
  const runId = turn?.runId ?? (liveResult && 'runId' in state ? state.runId : '')
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId!, signal), enabled: Boolean(runId), retry: false, staleTime: Infinity })
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, staleTime: Infinity })
  // 키 없는 데모에서만 있는 목록이다. 없으면(404) 버튼을 숨긴다.
  const demoQuestions = useQuery({ queryKey: ['demo-questions'], queryFn: ({ signal }) => listDemoQuestions(signal), retry: false, staleTime: Infinity, enabled: demoId !== null })
  const recorded = Array.isArray(demoQuestions.data) ? demoQuestions.data.filter(item => item.demo_id === demoId) : []
  const recordedHere = recorded.filter(item => item.target === target.ref)
  const recordedResume = live ? recordedHere.find(item => item.question === live.question)?.resume ?? null : null
  const result: ResultDto | undefined = liveResult ?? (turn ? run.data?.result : undefined)
  const candidates = candidatesOf(result)
  const selectedPart = selected && selected.runId === runId ? selected.part ?? undefined : undefined
  const candidate = candidates.find(item => item.part === selectedPart)
  const judgement = judgementOf(result)
  const role = candidate?.role ?? judgement?.roles?.[0] ?? ''
  const roleName = (Array.isArray(roles.data) ? roles.data.find(item => item.code === role)?.name : '') || role
  // [왜] 대체품 찾기는 사용 조건과 원하는 정격이 있어야 비교할 기준이 생긴다. 예시도 조건을 함께 적는다
  const examples = [`${target.ref}을 SS34로 바꿔도 되나요? 입력 최대 12V, ${target.ref} 전류 최대 1A, 주변 온도 25°C예요.`,
    `${target.ref}의 대체 후보를 찾아 주세요. 입력 최대 12V, 전류 최대 1A, 주변 온도 25°C예요. 역전압 정격 20V 이상, 평균 전류 정격 1A 이상이면 됩니다.`]
  const documents = documentEvidenceOf(result)
  const resultLoading = (running && !candidate) || chat.loading || (run.isFetching && !result)
  function selectPart(id: string | undefined, part: string | null, index: number | null) {
    if (!id) return
    chat.setPicked(index)
    setSelected({ runId: id, part })
  }
  const response = result && <Reply result={result} selectedPart={selectedPart} onSelect={part => selectPart(runId, part, turn ? history.indexOf(turn) : null)} onEvidence={() => selectPart(runId, null, turn ? history.indexOf(turn) : null)} />
  useEffect(() => {
    const previous = selectionContext.current
    if (previous.targetRef !== target.ref || (previous.threadId && previous.threadId !== threadId)) setSelected(null)
    selectionContext.current = { threadId, targetRef: target.ref }
  }, [threadId, target.ref])
  useEffect(() => {
    const heading = candidate ? details.current : selected && selected.runId === runId && selected.part === null ? evidenceHeading.current : null
    heading?.focus({ preventScroll: true })
    heading?.scrollIntoView?.({ block: 'start' })
  }, [selected, candidate, result, runId])
  useEffect(() => { if (!selected || selected.runId !== runId) input.current?.focus({ preventScroll: true }) }, [target.ref, threadId, selected])
  function updateJump() {
    if (body.current && conversationEnd.current) setShowJump(conversationEnd.current.getBoundingClientRect().bottom > body.current.getBoundingClientRect().bottom + 8)
  }
  useEffect(() => {
    updateJump()
    const observer = new ResizeObserver(updateJump)
    if (body.current) observer.observe(body.current)
    if (talk.current) observer.observe(talk.current)
    return () => observer.disconnect()
  }, [threadId, target.ref])
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 한글 조합 중의 Enter는 글자 확정이다. 전송하지 않는다.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!waiting && !attachmentPending) void chat.send() }
  }

  // 질문을 보내기 전에는 제목과 입력창만 보인다. 회로 · 조건 대조 · 속성은 검토가 시작되면 나타난다.
  const started = history.length > 0 || Boolean(live) || chat.loading
  return <div ref={root} className={`review${started ? '' : ' review-idle'}`} style={{ '--props': `${propsWidth}px` } as CSSProperties}>
    {dragging && <div className="attachment-drop-guide" role="status" aria-label="파일 놓기"><Paperclip aria-hidden="true" /><p>.net·.txt 파일을 놓으면 채팅에 첨부됩니다.</p><p className="fine">파일당 5 MiB 이하 · 전송 전에 확인할 수 있습니다.</p></div>}
    <div ref={body} className="review-body" role="region" aria-label="검토 내용" onScroll={updateJump}>
    <article className="doc" aria-label="대화 기록" onScroll={updateJump} tabIndex={0}>
      <header className="doc-head">
        <h1><span className="ref">{target.ref}</span><span>{target.value}</span></h1>
      </header>
      {result?.status === 'refused' ? <p className="notice">{withoutCorpusCitations(result.refusal || result.answer || '이 질문에는 답할 수 없습니다.', result.evidence)}</p>
        : result?.status === 'failed' ? <p className="notice" role="alert">이 검토는 실행에 실패해 결과가 없습니다. 새 검토로 다시 질문해 주세요.</p>
        : <p className="doc-lead">{running ? '검토 중입니다. 결과를 받으면 대화에서 확인할 수 있습니다.' : `${target.ref}을 다른 부품으로 바꿔도 되는지 검토합니다. 후보 품번과 사용 조건을 적어 보내세요.`}</p>}
      {result && <p className="fine">같은 동작은 보장하지 않습니다. 판정은 데이터시트 값과 입력한 조건으로 계산한 결과입니다.</p>}

      <section aria-labelledby="circuit-title"><div className="section-head"><h2 id="circuit-title">회로</h2><span>선택 부품의 연결</span></div>
        <div className="panel circuit-panel">
          <div ref={viewport} className="diagram-viewport" tabIndex={scrollable ? 0 : undefined} role="region" aria-label="회로 연결 개념도"><ContextDiagram targetRef={target.ref} targetValue={target.value} nets={nets} /></div>
        </div></section>

      <section ref={talk} className="talk" aria-labelledby="activity-title"><h2 id="activity-title">활동</h2>
        <ol className="activity">
          {chat.loading && <li className="skeleton" role="status"><span className="sr-only">검토 기록을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></li>}
          {history.map((item, index) => <li className="activity-entry" key={`${item.runId}-${index}`}>
            <div className="activity-message" role="group" aria-label={`내 메시지 ${index + 1}`}><div className="activity-body">
              <button className="activity-turn" aria-current={turn === item ? 'true' : undefined} onClick={() => chat.setPicked(index)}>{item.question}</button>
            </div></div>{turn === item ? response : <PastReply runId={item.runId} selectedPart={selected?.runId === item.runId ? selected.part ?? undefined : undefined} onSelect={part => selectPart(item.runId, part, index)} onEvidence={() => selectPart(item.runId, null, index)} />}
          </li>)}
          {live && <li className="activity-entry"><div className="activity-message" role="group" aria-label={`내 메시지 ${history.length + 1}`}><div className="activity-body">
            <button className="activity-turn" aria-current={picked === null ? 'true' : undefined} onClick={() => chat.setPicked(null)}>{live.question}</button>
          </div></div>
            {stages.length > 0 && <ol className="activity-steps" aria-label="AI 진행 상태">{stages.map((stage, index) => <li className="activity-stage" key={stage}>
              {index === stages.length - 1 && running ? <LoaderCircle className="spin" aria-hidden="true" /> : index === stages.length - 1 && state.status !== 'completed' ? <CircleDashed aria-hidden="true" /> : <Check aria-hidden="true" />}<span>{stage}</span>
            </li>)}</ol>}
            {!turn && response}</li>}
          {!history.length && !live && !chat.loading && <li className="activity-stage"><CircleDashed aria-hidden="true" /><span>아직 질문이 없습니다. 아래 예시로 시작할 수 있습니다.</span></li>}
        </ol>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{live && (running ? `AI: ${stages[stages.length - 1] || '검토 시작'}` : state.status === 'completed' ? '검토 결과를 받았습니다.' : state.status === 'requires_input' ? '추가 입력이 필요합니다.' : state.status === 'failed' ? '실행에 실패했습니다.' : state.status === 'refused' ? '답변이 거절되었습니다.' : '')}</div>
        {state.status === 'failed' && <div className="notice" role="alert"><p {...requestIdProps(state.error)}>검토 실행에 실패했습니다. {errorMessage(state.error)}{!state.runId && ' 아래 질문을 입력해 다시 보내 주세요.'}</p>{state.runId && <button className="btn" onClick={() => void chat.stream.refresh(state.runId!)}><RotateCw aria-hidden="true" />실행 상태 다시 확인</button>}</div>}
        {run.error && <div className="notice" role="alert"><p {...requestIdProps(run.error)}>검토 결과를 불러오지 못했습니다. {errorMessage(run.error)}</p><button className="btn" onClick={() => void run.refetch()}>결과 다시 불러오기</button></div>}
        {state.status === 'requires_input' && <form className="ask" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget)
          void chat.stream.resume(state.runId, { answers: Object.fromEntries((state.interrupt.missing ?? []).map(code => [code, String(data.get(code) ?? '').trim()]).filter(([, value]) => value)), role: String(data.get('role') ?? '') || undefined }) }}>
          <h3>{state.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</h3>
          <p className="fine">모르는 값은 비워 두세요. 빈 칸은 '모름'으로 검토합니다.</p>
          {(state.interrupt.role_choices ?? []).map((code, index) => <label key={code} className="choice"><input type="radio" name="role" value={code} defaultChecked={index === 0} />{(Array.isArray(roles.data) ? roles.data.find(item => item.code === code)?.name : '') || '역할'}</label>)}
          {(state.interrupt.missing ?? []).map(code => <label className="field" key={code}><span>{INPUT_LABELS[code] ?? '추가 조건'}</span><input className="input" name={code} autoComplete="off" placeholder={inputPlaceholder(code)} /></label>)}
          <div className="form-actions"><button className="btn btn-primary">이 값으로 계속 검토</button>
            <button type="button" className="btn" onClick={event => void chat.stream.resume(state.runId, { answers: {}, role: String(new FormData(event.currentTarget.form!).get('role') ?? '') || undefined })}>모두 모름으로 계속</button>
            {recordedResume && <button type="button" className="btn" onClick={() => void chat.stream.resume(state.runId, { answers: recordedResume.answers, role: recordedResume.role || undefined })}>기록한 답으로 계속하기</button>}</div></form>}
        {chat.error ? <div className="notice" role="alert"><p {...requestIdProps(chat.error)}>검토 기록을 불러오거나 질문을 보내지 못했습니다. {errorMessage(chat.error)} 새로고침하면 작성 중인 질문은 지워집니다.</p><button className="btn" onClick={() => window.location.reload()}>페이지 새로고침</button></div> : null}
        {!history.length && !live && recorded.length > 0 && <div className="demo-questions"><p className="composer-hint">키 없는 데모는 기록한 질문만 재생합니다.{recordedHere.length === 0 && ` 이 회로에서 기록한 질문이 있는 부품은 ${[...new Set(recorded.map(item => item.target))].join(', ')}입니다.`}</p>
          {recordedHere.length > 0 && <ul className="examples">{recordedHere.map(item => <li key={item.id}><button disabled={attachmentPending} title={item.conditions} onClick={() => void chat.send({ question: item.question, conditions: item.conditions })}>{item.question}</button></li>)}</ul>}</div>}
        {!history.length && !live && recorded.length === 0 && <ul className="examples">{examples.map(example => <li key={example}><button onClick={() => { chat.setText(example); input.current?.focus() }}>{example}</button></li>)}</ul>}
        <span ref={conversationEnd} className="conversation-end"><span className="sr-only">대화 끝</span></span>
      </section>
    </article>

    {/* 끌어서 속성 칸 너비를 바꾼다. 두 번 누르면 기본 너비로 돌아간다. */}
    <div className="props-resize" role="separator" aria-orientation="vertical" aria-label="속성 칸 너비 조절" title="끌어서 너비 조절, 두 번 눌러 기본값" tabIndex={0}
      aria-valuenow={propsWidth} aria-valuemin={PROPS_MIN} aria-valuemax={PROPS_MAX}
      onPointerDown={event => event.currentTarget.setPointerCapture(event.pointerId)}
      onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId) && root.current) resizeProps(root.current.getBoundingClientRect().right - event.clientX) }}
      onDoubleClick={() => resizeProps(PROPS_DEFAULT)}
      onKeyDown={event => { if (event.key === 'ArrowLeft') { event.preventDefault(); resizeProps(propsWidth + 16) } else if (event.key === 'ArrowRight') { event.preventDefault(); resizeProps(propsWidth - 16) } }} />
    <aside className="props" aria-label="부품 상세">
      <section className="property-group" id="candidate-details">
        {candidate ? <><h2 ref={details} className="candidate-heading" tabIndex={-1}>{candidate.part}</h2><p className="property-note">선택한 질문의 검토 결과</p></>
          : <><h2>부품 상세</h2><p className="property-note">채팅에서 부품의 상세 보기를 선택해 주세요.</p></>}
      </section>
      {candidate && <>
      <section className="property-group" aria-labelledby="approval-heading"><h2 id="approval-heading">승인</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">승인할 결과를 기다리는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : candidate ? <Approval key={`${runId}-${candidate.part}`} candidate={candidate} messageId={run.data?.message_id ?? null} reviewer={reviewer} /> : <p className="property-note">판정 후 승인할 수 있습니다. 질문에 후보와 사용 조건을 입력해 주세요.</p>}
      </section>
      <section className="property-group" aria-labelledby="verdict-heading"><h2 id="verdict-heading">판정</h2><dl>
        <div><dt>결과</dt><dd>{candidate ? <span className={`dot tone-${VERDICT_TONE[candidate.verdict]}`}>{VERDICT_LABELS[candidate.verdict]}</span> : running ? '검토 중' : result ? '판정 없음' : '결과 대기'}</dd></div>
        {candidate && <div><dt>기판 수정</dt><dd>{candidate.board_change === true ? '필요' : candidate.board_change === false ? '필요 없음' : '확인 안 됨'}</dd></div>}
        {(judgement?.input_conditions ?? []).map(item => <div key={item.code}><dt>{INPUT_LABELS[item.code] ?? '추가 조건'}</dt><dd>{item.value}</dd></div>)}
      </dl>
        {candidate.package_citation && <p className="property-note">패키지 근거: {citationHref(candidate.package_citation) ? <a href={citationHref(candidate.package_citation)} target="_blank" rel="noreferrer">{candidate.package_citation.document} {citationText(candidate.package_citation)}<span className="sr-only"> (새 탭)</span></a> : <span>{candidate.package_citation.document} {citationText(candidate.package_citation)}</span>}</p>}
      </section>
      <section className="property-group" aria-labelledby="checks-title"><h2 id="checks-title">조건 대조</h2>
        <Checks candidate={candidate} resolved showDocument />
        {[...(candidate.cautions ?? []), ...(candidate.missing ?? []).map(item => `문서에 없는 값: ${item}`), ...(candidate.uncertain ?? []).map(item => `확실하지 않은 값: ${item}`)].map(note => <p className="caution" key={note}>{note}</p>)}
      </section>
      </>}
      <section className="property-group" aria-labelledby="circuit-heading"><h2 id="circuit-heading">회로</h2><dl>
        {roles.isFetching && !roles.data && <div><dt>역할</dt><dd role="status"><span className="sr-only">역할 이름을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></dd></div>}
        {roleName && <div><dt>역할</dt><dd>{roleName}</dd></div>}
        <div><dt>현재 부품</dt><dd>{target.value}</dd></div>
        <div><dt>풋프린트</dt><dd>{target.footprint.replace(/^import_input:/, '') || '넷리스트에 없음'}</dd></div>
        {nets.map(net => <div key={net.name}><dt>핀 {net.pin}</dt><dd>{net.name}</dd></div>)}
        <div><dt>부품 수</dt><dd>{counts.parts}개</dd></div><div><dt>넷 수</dt><dd>{counts.nets}개</dd></div>
      </dl>{candidate && (judgement?.role_evidence ?? []).map(note => <p className="property-note" key={note}>역할 근거: {note}</p>)}{roles.error && <div className="notice" role="alert"><p>역할 이름을 불러오지 못했습니다.</p><button className="btn" onClick={() => void roles.refetch()}>역할 다시 불러오기</button></div>}</section>
      {(result?.price_parts ?? []).length > 0 && <section className="property-group" aria-labelledby="price-heading"><h2 id="price-heading">가격·재고</h2>
        <PriceLookup key={result!.price_parts.join(',')} parts={result!.price_parts} /></section>}
      {(!candidates.length || documents.length > 0) && <section className="property-group" aria-labelledby="evidence-heading"><h2 ref={evidenceHeading} id="evidence-heading" tabIndex={-1}>{candidates.length ? '추가 문서 근거' : '근거'}</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">근거를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : documents.length ? <ul className="document-list">{documents.map((item, index) => <li key={index}><FileText aria-hidden="true" /><div className="document-entry">
          {citationHref(item) ? <a href={citationHref(item)} target="_blank" rel="noreferrer">{item.document}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span>{item.document}</span>}
          <span className="property-note">{[citationText(item), item.section].filter(Boolean).join(' · ') || '출처 위치 없음'}</span></div></li>)}</ul> : <p className="property-note">{result ? '인용 문서가 없습니다. 질문에 후보 품번을 보완해 주세요.' : '검토 후 문서가 표시됩니다. 질문에 후보와 사용 조건을 입력해 주세요.'}</p>}
      </section>}
    </aside>
    </div>
    <div className="composer-dock">
      {showJump && <button type="button" className="btn btn-icon jump-latest" aria-label="대화 맨 아래로 이동" title="대화 맨 아래로 이동" onClick={() => { conversationEnd.current?.scrollIntoView?.({ block: 'end' }); input.current?.focus({ preventScroll: true }) }}><ArrowDown aria-hidden="true" /></button>}
      {attachmentError && <div className="notice notice-dismissible" role="alert"><p>{attachmentError}</p><button type="button" className="icon-btn" aria-label="첨부 안내 닫기" onClick={() => setAttachmentError(null)}><X aria-hidden="true" /></button></div>}
      <form className="composer" onSubmit={(event) => { event.preventDefault(); if (!attachmentPending) void chat.send() }}>
        <label className="sr-only" htmlFor="question">질문</label>
        <textarea id="question" ref={input} rows={2} aria-describedby="composer-hint" value={chat.text} onChange={event => chat.setText(event.target.value)} onKeyDown={onKey} placeholder={waiting ? "위 조건 질문에 먼저 답하거나 '모두 모름으로 계속'을 눌러 주세요." : "후보 품번과 사용 조건을 적어 주세요."} />
        {/* 첨부 UI는 개발 빌드에만 노출한다. 파일 전송 API는 연동 확인 대기 중이다. */}
        {import.meta.env.DEV && <><input ref={picker} type="file" accept=".net,.txt" multiple hidden onChange={event => { attachFiles(Array.from(event.target.files ?? [])); event.target.value = '' }} />
          <button type="button" className="btn btn-icon" disabled={running || chat.loading} onClick={() => picker.current?.click()} aria-label="파일 첨부 (.net, .txt)" title="파일 첨부 (.net, .txt)"><Paperclip aria-hidden="true" /></button></>}
        {running ? <button type="button" className="btn btn-icon" onClick={chat.stream.cancel} aria-label="응답 받기 중단"><Square aria-hidden="true" /></button>
          : <button className="btn btn-icon" disabled={chat.loading || waiting || attachmentPending || !chat.text.trim()} aria-label="질문 보내기"><ArrowUp aria-hidden="true" /></button>}
      </form>
      {chat.files.length > 0 && <ul className="chips" aria-label="첨부한 파일">{chat.files.map((file, index) => <li key={`${file.name}-${index}`}><FileText aria-hidden="true" /><span>{file.name}</span>
        <button type="button" className="icon-btn" aria-label={`${file.name} 첨부 취소`} onClick={() => chat.setFiles(chat.files.filter((_, at) => at !== index))}><X aria-hidden="true" /></button></li>)}</ul>}
      {attachmentPending && <p className="composer-hint">첨부 파일 전송은 준비 중입니다. 첨부를 해제하면 질문만 보낼 수 있습니다.</p>}
      <p id="composer-hint" className="composer-hint meta-fields"><span>Enter로 보내기</span><span>Shift + Enter로 줄바꿈</span></p>
    </div>
  </div>
}
