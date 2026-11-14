import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, FormEvent, KeyboardEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUp, Check, CircleDashed, ExternalLink, FileText, LoaderCircle, Paperclip, X, RotateCw, ShieldCheck, Square } from 'lucide-react'
import { getRun, listDemoQuestions, listJudgeRoles } from '../api/conversations'
import type { CandidateDto, ResultDto } from '../api/conversations'
import type { CircuitPart } from '../api/projects'
import { errorMessage, requestIdProps } from '../api/client'
import { approveMessage, createQuote, getMessageApproval } from '../api/quotes'
import { useConversation } from '../hooks/useConversation'
import type { ContextNet } from '../lib/circuit'
import { CHECK_LABELS, VERDICT_LABELS, VERDICT_TONE, candidatesOf, citationHref, formatValue, judgementOf } from '../lib/judgement'
import { INPUT_LABELS } from '../lib/inputLabels'
import ContextDiagram from './ContextDiagram'
import PriceLookup from './PriceLookup'
import SafeMarkdown from './SafeMarkdown'

const PROPS_KEY = 'sojafit:props-width'
const PROPS_DEFAULT = 280, PROPS_MIN = 240, PROPS_MAX = 480

type Props = { projectId: number; demoId: string | null; target: CircuitPart; nets: ContextNet[]; counts: { parts: number; nets: number }; threadId: string; reviewer: string; initialQuestion?: string
  onThread: (threadId: string, targetRef?: string) => void }

export function Checks({ candidate, resolved }: { candidate: CandidateDto | undefined; resolved: boolean }) {
  const rows = candidate?.checks ?? []
  return <div className="table-scroll"><table className="checks">
    <caption className="sr-only">후보 {candidate?.part ?? '부품'}의 조건별 요구 값과 데이터시트 근거</caption>
    <thead><tr><th scope="col">항목</th><th scope="col">기준</th><th scope="col" className="num">요구</th><th scope="col" className="num">후보 값</th><th scope="col">결과</th><th scope="col">근거 위치</th></tr></thead>
    <tbody>{rows.length === 0 ? <tr className="checks-empty"><td colSpan={6}>{resolved ? '이 결과에는 조건별 대조 값이 없습니다. 아래 질문에 후보와 사용 조건을 보완해 주세요.' : '검토 후 대조 값이 표시됩니다. 아래에 후보와 사용 조건을 입력해 주세요.'}</td></tr>
      : rows.map((check) => {
        const href = citationHref(check.citation)
        const citation = check.citation
        const where = citation && ((citation.page != null && citation.page !== '') || citation.table || citation.row) ? <>
          {citation.page != null && citation.page !== '' && <span>{citation.page}쪽</span>}
          {citation.table && <span><span className="sr-only">표: </span>{citation.table}</span>}
          {citation.row && <span><span className="sr-only">행: </span>{citation.row}</span>}
        </> : <span>출처 위치 없음</span>
        const state = check.result ?? 'unverified'
        return <tr key={check.code}>
          <th scope="row">{check.code}</th>
          <td className="basis" data-label="기준">{check.basis}</td>
          <td className="num" data-label="요구">{check.threshold != null && check.op ? `${check.op === '>=' ? '≥' : check.op === '<=' ? '≤' : check.op} ` : ''}{formatValue(check.threshold, check.unit) || '값 없음'}</td>
          <td className="num strong" data-label="후보 값" title={check.condition ?? undefined}>{formatValue(check.value, check.unit) || '값 없음'}</td>
          <td data-label="결과"><span className={`result tone-${state === 'pass' ? 'identical' : state === 'fail' ? 'insufficient' : 'unverified'}`}>{CHECK_LABELS[state] ?? '확인 안 됨'}</span></td>
          <td data-label="근거" title={check.citation?.document ?? undefined}>{href ? <a className="citation-fields" href={href} target="_blank" rel="noreferrer">{where}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span className="citation-fields">{where}</span>}</td>
        </tr>
      })}</tbody>
  </table></div>
}

export function Approval({ candidate, messageId, reviewer }: { candidate: CandidateDto; messageId: number | null; reviewer: string }) {
  // [왜] 승인·견적은 서버가 정본이다. 새로고침해도 '승인 전'으로 돌아가지 않도록 화면 상태 대신 서버 값을 읽는다(가격은 저장하지 않는다, ADR 0009)
  const saved = useQuery({ queryKey: ['message-approval', messageId], queryFn: ({ signal }) => getMessageApproval(messageId!, signal), enabled: messageId !== null, retry: false, gcTime: 0 })
  const mine = saved.data?.approval?.candidate_part === candidate.part ? saved.data : null
  const approval = mine?.approval ?? null
  const quote = mine?.quotes.at(-1) ?? null
  const otherPart = saved.data?.approval && !mine ? saved.data.approval.candidate_part : null // 이 답에서 다른 후보를 이미 승인함
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function act(job: () => Promise<unknown>) {
    if (busy) return
    setBusy(true); setError(null)
    try { await job() } catch (reason) {
      // 이미 승인된 메시지(다른 탭·새로고침 전 승인)는 오류가 아니라 서버 상태를 다시 읽는다
      if ((reason as { code?: string } | null)?.code !== 'ALREADY_APPROVED') setError(reason)
    } finally { await saved.refetch(); setBusy(false) }
  }
  function openQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const quantity = Math.max(1, Math.floor(Number(new FormData(event.currentTarget).get('quantity'))) || 1)
    void act(() => createQuote(approval!.id, quantity))
  }
  return <div className="approval">
    <p className="approval-state">{approval ? <ShieldCheck aria-hidden="true" /> : <CircleDashed aria-hidden="true" />}{approval ? '승인됨' : otherPart ? '다른 후보 승인됨' : '승인 전'}</p>
    {approval && <p className="property-note">{reviewer}</p>}
    {otherPart && <p className="property-note">이 답에서는 {otherPart}를 이미 승인했습니다.</p>}
    {quote && <><p className="property-note">견적 {quote.part_number} × {quote.quantity}</p><PriceLookup key={quote.id} parts={[quote.part_number]} quantity={quote.quantity} /></>}
    {!approval && !otherPart && <button className="btn btn-primary" disabled={busy || messageId === null || saved.isPending} onClick={() => void act(() => approveMessage(messageId!, candidate.part, candidate.verdict))}>{busy ? '저장 중' : '검토하고 승인'}</button>}
    {approval && !quote && <form className="quote" onSubmit={openQuote}><label className="sr-only" htmlFor="quantity">수량</label><input id="quantity" name="quantity" className="input" type="number" min={1} defaultValue={1} inputMode="numeric" /><button className="btn btn-primary" disabled={busy}>견적 열기</button></form>}
    {saved.error ? <p className="notice" role="alert" {...requestIdProps(saved.error)}>저장된 승인 상태를 불러오지 못했습니다. {errorMessage(saved.error)}</p> : null}
    {error ? <p className="notice" role="alert" {...requestIdProps(error)}>{approval ? '견적을 저장하지 못했습니다. 견적 열기로 다시 시도해 주세요.' : '승인을 저장하지 못했습니다. 검토하고 승인으로 다시 시도해 주세요.'} {errorMessage(error)}</p> : null}
  </div>
}

function reply(result: ResultDto) {
  const candidate = candidatesOf(result)[0]
  return <div className="activity-reply"><span className="actor-avatar actor-agent" aria-hidden="true"><img src="/assets/sojafit-icon.svg" alt="" /></span>
    <div className="activity-body"><p className="activity-by"><strong>SojaFit</strong><span>검토 결과</span></p>
      {candidate && <p>{candidate.part}<span className={`result tone-${VERDICT_TONE[candidate.verdict]}`}>{VERDICT_LABELS[candidate.verdict]}</span></p>}
      {result.refusal ? <p>{result.refusal}</p> : result.answer ? <SafeMarkdown text={result.answer} />
        : !candidate && <p>{result.status === 'failed' ? '실행에 실패했습니다.' : '결과에 판정이 없습니다.'}</p>}</div></div>
}

// 선택하지 않은 지난 질문의 답. 선택된 질문과 같은 ['run', id] 캐시를 써서 실행마다 한 번만 읽는다.
function PastReply({ runId }: { runId: string }) {
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId, signal), retry: false, staleTime: Infinity })
  if (run.data) return reply(run.data.result)
  return <p className="fine">{run.isError ? '답변을 불러오지 못했습니다.' : '답변을 불러오는 중입니다.'}</p>
}

// 검토 한 건을 문서처럼 보인다: 왼쪽은 회로 · 조건 대조 · 활동, 오른쪽은 속성.
export default function Review({ projectId, demoId, target, nets, counts, threadId, reviewer, initialQuestion, onThread }: Props) {
  const chat = useConversation({ projectId, targetRef: target.ref, threadId, onThread })
  // 부품 목록의 질문 칸에서 넘어온 질문을 한 번만 보낸다. ref는 StrictMode의 effect 재실행에도 남는다.
  const sentInitial = useRef(false)
  useEffect(() => { if (initialQuestion && !sentInitial.current) { sentInitial.current = true; void chat.send({ question: initialQuestion }) } }, []) // eslint-disable-line react-hooks/exhaustive-deps -- 처음 열릴 때만
  const { history, live, stages, state, running, waiting, picked } = chat
  const input = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const root = useRef<HTMLDivElement>(null)
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
  const candidate = candidatesOf(result)[0]
  const judgement = judgementOf(result)
  const roleName = (Array.isArray(roles.data) ? roles.data.find(item => item.code === judgement?.roles?.[0])?.name : '') || judgement?.roles?.[0] || ''
  // [왜] 대체품 찾기는 사용 조건과 원하는 정격이 있어야 비교할 기준이 생긴다. 예시도 조건을 함께 적는다
  const examples = [`${target.ref}을 SS34로 바꿔도 되나요? 입력 최대 12V, ${target.ref} 전류 최대 1A, 주변 온도 25°C예요.`,
    `${target.ref}의 대체 후보를 찾아 주세요. 입력 최대 12V, 전류 최대 1A, 주변 온도 25°C예요. 역전압 정격 20V 이상, 평균 전류 정격 1A 이상이면 됩니다.`]
  const documents = [...new Map((result?.evidence ?? []).map(item => [item.document, item])).values()]
  const resultLoading = (running && !candidate) || chat.loading || (run.isFetching && !result)
  const initial = reviewer.trim().charAt(0).toUpperCase()
  const response = result && reply(result)
  useEffect(() => { input.current?.focus() }, [target.ref, threadId])
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    // 한글 조합 중의 Enter는 글자 확정이다. 전송하지 않는다.
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!waiting) void chat.send() }
  }

  // 질문을 보내기 전에는 제목과 입력창만 보인다. 회로 · 조건 대조 · 속성은 검토가 시작되면 나타난다.
  const started = history.length > 0 || Boolean(live) || chat.loading
  return <div ref={root} className={`review${started ? '' : ' review-idle'}`} style={{ '--props': `${propsWidth}px` } as CSSProperties}>
    <article className="doc">
      <header className={`doc-head${candidate ? ` tone-${VERDICT_TONE[candidate.verdict]}` : ''}`}>
        {candidate && <strong className={`verdict dot tone-${VERDICT_TONE[candidate.verdict]}`}>{VERDICT_LABELS[candidate.verdict]}</strong>}
        <h1><span className="ref">{target.ref}</span><span>{target.value}</span>{candidate && <><ArrowRight className="to" aria-label="교체 후보" /><span>{candidate.part}</span></>}</h1>
      </header>
      {result?.status === 'refused' ? <p className="notice">{result.refusal || result.answer || '이 질문에는 답할 수 없습니다.'}</p>
        : result?.status === 'failed' ? <p className="notice" role="alert">이 검토는 실행에 실패해 결과가 없습니다. 새 검토로 다시 질문해 주세요.</p>
        : <p className="doc-lead">{result?.answer ? result.answer.split('\n')[0] : running ? '검토 중입니다. 결과를 받으면 조건과 근거가 표시됩니다.' : `${target.ref}을 다른 부품으로 바꿔도 되는지 검토합니다. 후보 품번과 사용 조건을 적어 보내세요.`}</p>}

      <section aria-labelledby="circuit-title"><div className="section-head"><h2 id="circuit-title">회로</h2><span>선택 부품의 연결</span></div>
        <div className="panel circuit-panel">
          {candidate && <div className="circuit-comparison"><span><small>현재 부품</small><strong className="meta-fields"><span>{target.ref}</span><span>{target.value}</span></strong></span><ArrowRight aria-hidden="true" /><span><small>검토 후보</small><strong>{candidate.part}</strong></span></div>}
          <div ref={viewport} className="diagram-viewport" tabIndex={scrollable ? 0 : undefined} role="region" aria-label="회로 연결 개념도"><ContextDiagram targetRef={target.ref} targetValue={target.value} nets={nets} /></div>
        </div></section>

      <section aria-labelledby="checks-title"><h2 id="checks-title">조건 대조</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">검토 결과를 기다리는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div> : !run.error && !chat.error && state.status !== 'failed' ? <Checks candidate={candidate} resolved={Boolean(result)} /> : null}
        {candidate && [...(candidate.cautions ?? []), ...(candidate.missing ?? []).map(item => `문서에 없는 값: ${item}`), ...(candidate.uncertain ?? []).map(item => `확실하지 않은 값: ${item}`)].map(note => <p className="caution" key={note}>{note}</p>)}
        {result && <p className="fine">같은 동작은 보장하지 않습니다. 판정은 데이터시트 값과 입력한 조건으로 계산한 결과입니다.</p>}
        {run.error && <div className="notice" role="alert"><p {...requestIdProps(run.error)}>검토 결과를 불러오지 못했습니다. {errorMessage(run.error)}</p><button className="btn" onClick={() => void run.refetch()}>결과 다시 불러오기</button></div>}
      </section>

      <section className="talk" aria-labelledby="activity-title"><h2 id="activity-title">활동</h2>
        <ol className="activity">
          {chat.loading && <li className="skeleton" role="status"><span className="sr-only">검토 기록을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></li>}
          {history.map((item, index) => <li className="activity-entry" key={`${item.runId}-${index}`}>
            <div className="activity-message"><span className="actor-avatar" aria-hidden="true">{initial}</span><div className="activity-body">
              <p className="activity-by"><strong title={reviewer}>{reviewer}</strong><span>질문 {index + 1}</span>{turn === item && <span>선택됨</span>}</p>
              <button className="activity-turn" aria-current={turn === item ? 'true' : undefined} onClick={() => chat.setPicked(index)}>{item.question}</button>
            </div></div>{turn === item ? response : <PastReply runId={item.runId} />}
          </li>)}
          {live && <li className="activity-entry"><div className="activity-message"><span className="actor-avatar" aria-hidden="true">{initial}</span><div className="activity-body">
            <p className="activity-by"><strong title={reviewer}>{reviewer}</strong><span>질문 {history.length + 1}</span>{picked === null && <span>선택됨</span>}</p>
            <button className="activity-turn" aria-current={picked === null ? 'true' : undefined} onClick={() => chat.setPicked(null)}>{live.question}</button>
          </div></div>
            {stages.length > 0 && <ol className="activity-steps">{stages.map((stage, index) => <li className="activity-stage" key={stage}>
              {index === stages.length - 1 && running ? <LoaderCircle className="spin" aria-hidden="true" /> : index === stages.length - 1 && state.status !== 'completed' ? <CircleDashed aria-hidden="true" /> : <Check aria-hidden="true" />}<span>SojaFit</span><span>{stage}</span>
            </li>)}</ol>}
            {!turn && response}</li>}
          {!history.length && !live && !chat.loading && <li className="activity-stage"><CircleDashed aria-hidden="true" /><span>아직 질문이 없습니다. 아래 예시로 시작할 수 있습니다.</span></li>}
        </ol>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{live && (running ? `SojaFit: ${stages[stages.length - 1] || '검토 시작'}` : state.status === 'completed' ? '검토 결과를 받았습니다.' : state.status === 'requires_input' ? '추가 입력이 필요합니다.' : state.status === 'failed' ? '실행에 실패했습니다.' : state.status === 'refused' ? '답변이 거절되었습니다.' : '')}</div>
        {state.status === 'failed' && <div className="notice" role="alert"><p {...requestIdProps(state.error)}>검토 실행에 실패했습니다. {errorMessage(state.error)}{!state.runId && ' 아래 질문을 입력해 다시 보내 주세요.'}</p>{state.runId && <button className="btn" onClick={() => void chat.stream.refresh(state.runId!)}><RotateCw aria-hidden="true" />실행 상태 다시 확인</button>}</div>}
        {state.status === 'requires_input' && <form className="ask" onSubmit={(event) => { event.preventDefault(); const data = new FormData(event.currentTarget)
          void chat.stream.resume(state.runId, { answers: Object.fromEntries((state.interrupt.missing ?? []).map(code => [code, String(data.get(code) ?? '').trim()]).filter(([, value]) => value)), role: String(data.get('role') ?? '') || undefined }) }}>
          <h3>{state.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</h3>
          <p className="fine">모르는 값은 비워 두세요. 빈 칸은 '모름'으로 검토합니다.</p>
          {(state.interrupt.role_choices ?? []).map((code, index) => <label key={code} className="choice"><input type="radio" name="role" value={code} defaultChecked={index === 0} />{(Array.isArray(roles.data) ? roles.data.find(item => item.code === code)?.name : '') || '역할'}</label>)}
          {(state.interrupt.missing ?? []).map(code => <label className="field" key={code}><span>{INPUT_LABELS[code] ?? '추가 조건'}</span><input className="input" name={code} autoComplete="off" placeholder="단위까지 적어 주세요. 예: 12 V" /></label>)}
          <div className="form-actions"><button className="btn btn-primary">이 값으로 계속 검토</button>
            <button type="button" className="btn" onClick={event => void chat.stream.resume(state.runId, { answers: {}, role: String(new FormData(event.currentTarget.form!).get('role') ?? '') || undefined })}>모두 모름으로 계속</button>
            {recordedResume && <button type="button" className="btn" onClick={() => void chat.stream.resume(state.runId, { answers: recordedResume.answers, role: recordedResume.role || undefined })}>기록한 답으로 계속하기</button>}</div></form>}
        {chat.error ? <div className="notice" role="alert"><p {...requestIdProps(chat.error)}>검토 기록을 불러오거나 질문을 보내지 못했습니다. {errorMessage(chat.error)} 새로고침하면 작성 중인 질문은 지워집니다.</p><button className="btn" onClick={() => window.location.reload()}>페이지 새로고침</button></div> : null}
        {!history.length && !live && recorded.length > 0 && <div className="demo-questions"><p className="composer-hint">키 없는 데모는 기록한 질문만 재생합니다.{recordedHere.length === 0 && ` 이 회로에서 기록한 질문이 있는 부품은 ${[...new Set(recorded.map(item => item.target))].join(', ')}입니다.`}</p>
          {recordedHere.length > 0 && <ul className="examples">{recordedHere.map(item => <li key={item.id}><button title={item.conditions} onClick={() => void chat.send({ question: item.question, conditions: item.conditions })}>{item.question}</button></li>)}</ul>}</div>}
        {!history.length && !live && recorded.length === 0 && <ul className="examples">{examples.map(example => <li key={example}><button onClick={() => { chat.setText(example); input.current?.focus() }}>{example}</button></li>)}</ul>}
        <form className="composer" onSubmit={(event) => { event.preventDefault(); void chat.send() }}>
          <label className="sr-only" htmlFor="question">질문</label>
          <textarea id="question" ref={input} rows={2} aria-describedby="composer-hint" value={chat.text} onChange={event => chat.setText(event.target.value)} onKeyDown={onKey} placeholder={waiting ? "위 조건 질문에 먼저 답하거나 '모두 모름으로 계속'을 눌러 주세요." : "후보 품번과 사용 조건을 적어 주세요."} />
          {/* 서버가 개발 환경에서만 첨부를 받는다. 운영에서는 버튼을 두지 않는다. */}
          {import.meta.env.DEV && <><input ref={picker} type="file" accept=".net,.txt" multiple hidden onChange={event => { chat.setFiles([...chat.files, ...Array.from(event.target.files ?? [])]); event.target.value = '' }} />
            <button type="button" className="btn btn-icon" disabled={running} onClick={() => picker.current?.click()} aria-label="파일 첨부 (.net, .txt)" title="파일 첨부 (.net, .txt)"><Paperclip aria-hidden="true" /></button></>}
          {running ? <button type="button" className="btn btn-icon" onClick={chat.stream.cancel} aria-label="응답 받기 중단"><Square aria-hidden="true" /></button>
            : <button className="btn btn-icon" disabled={waiting || !chat.text.trim()} aria-label="질문 보내기"><ArrowUp aria-hidden="true" /></button>}
        </form>
        {chat.files.length > 0 && <ul className="chips" aria-label="첨부한 파일">{chat.files.map((file, index) => <li key={`${file.name}-${index}`}><FileText aria-hidden="true" /><span>{file.name}</span>
          <button type="button" className="icon-btn" aria-label={`${file.name} 첨부 취소`} onClick={() => chat.setFiles(chat.files.filter((_, at) => at !== index))}><X aria-hidden="true" /></button></li>)}</ul>}
        <p id="composer-hint" className="composer-hint meta-fields"><span>Enter로 보내기</span><span>Shift + Enter로 줄바꿈</span></p>
      </section>
    </article>

    {/* 끌어서 속성 칸 너비를 바꾼다. 두 번 누르면 기본 너비로 돌아간다. */}
    <div className="props-resize" role="separator" aria-orientation="vertical" aria-label="속성 칸 너비 조절" title="끌어서 너비 조절, 두 번 눌러 기본값" tabIndex={0}
      aria-valuenow={propsWidth} aria-valuemin={PROPS_MIN} aria-valuemax={PROPS_MAX}
      onPointerDown={event => event.currentTarget.setPointerCapture(event.pointerId)}
      onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId) && root.current) resizeProps(root.current.getBoundingClientRect().right - event.clientX) }}
      onDoubleClick={() => resizeProps(PROPS_DEFAULT)}
      onKeyDown={event => { if (event.key === 'ArrowLeft') { event.preventDefault(); resizeProps(propsWidth + 16) } else if (event.key === 'ArrowRight') { event.preventDefault(); resizeProps(propsWidth - 16) } }} />
    <aside className="props" aria-label="속성">
      <section className="property-group" aria-labelledby="approval-heading"><h2 id="approval-heading">승인</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">승인할 결과를 기다리는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : candidate ? <Approval key={`${runId}-${candidate.part}`} candidate={candidate} messageId={run.data?.message_id ?? null} reviewer={reviewer} /> : <p className="property-note">판정 후 승인할 수 있습니다. 질문에 후보와 사용 조건을 입력해 주세요.</p>}
      </section>
      <section className="property-group" aria-labelledby="verdict-heading"><h2 id="verdict-heading">판정</h2><dl>
        <div><dt>결과</dt><dd>{candidate ? <span className={`dot tone-${VERDICT_TONE[candidate.verdict]}`}>{VERDICT_LABELS[candidate.verdict]}</span> : running ? '검토 중' : result ? '판정 없음' : '결과 대기'}</dd></div>
        {candidate && <div><dt>기판 수정</dt><dd>{candidate.board_change === true ? '필요' : candidate.board_change === false ? '필요 없음' : '확인 안 됨'}</dd></div>}
        {(judgement?.input_conditions ?? []).map(item => <div key={item.code}><dt>{INPUT_LABELS[item.code] ?? '추가 조건'}</dt><dd>{item.value}</dd></div>)}
      </dl></section>
      <section className="property-group" aria-labelledby="circuit-heading"><h2 id="circuit-heading">회로</h2><dl>
        {roles.isFetching && !roles.data && <div><dt>역할</dt><dd role="status"><span className="sr-only">역할 이름을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></dd></div>}
        {roleName && <div><dt>역할</dt><dd>{roleName}</dd></div>}
        <div><dt>현재 부품</dt><dd>{target.value}</dd></div>
        <div><dt>풋프린트</dt><dd>{target.footprint.replace(/^import_input:/, '') || '넷리스트에 없음'}</dd></div>
        {nets.map(net => <div key={net.name}><dt>핀 {net.pin}</dt><dd>{net.name}</dd></div>)}
        <div><dt>부품 수</dt><dd>{counts.parts}개</dd></div><div><dt>넷 수</dt><dd>{counts.nets}개</dd></div>
      </dl>{roles.error && <div className="notice" role="alert"><p>역할 이름을 불러오지 못했습니다.</p><button className="btn" onClick={() => void roles.refetch()}>역할 다시 불러오기</button></div>}</section>
      {(result?.price_parts ?? []).length > 0 && <section className="property-group" aria-labelledby="price-heading"><h2 id="price-heading">가격·재고</h2>
        <PriceLookup key={result!.price_parts.join(',')} parts={result!.price_parts} /></section>}
      <section className="property-group" aria-labelledby="evidence-heading"><h2 id="evidence-heading">근거</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">근거를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : documents.length ? <ul className="document-list">{documents.map(item => <li key={item.document}><FileText aria-hidden="true" />
          {item.source_url && /^https?:\/\//.test(item.source_url) ? <a href={item.source_url} target="_blank" rel="noreferrer">{item.document}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span>{item.document}</span>}</li>)}</ul> : <p className="property-note">{result ? '인용 문서가 없습니다. 질문에 후보 품번을 보완해 주세요.' : '검토 후 문서가 표시됩니다. 질문에 후보와 사용 조건을 입력해 주세요.'}</p>}
      </section>
    </aside>
  </div>
}
