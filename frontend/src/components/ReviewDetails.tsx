import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, CircleDashed, ExternalLink, FileText, ShieldCheck, X } from 'lucide-react'
import { getRun, listJudgeRoles } from '../api/conversations'
import type { CandidateDto, CheckDto, CitationDto, ResultDto } from '../api/conversations'
import type { CircuitPart } from '../api/projects'
import { approveMessage, createQuote, listMessageApprovals } from '../api/quotes'
import type { QuoteDto } from '../api/quotes'
import type { ApiError } from '../api/client'
import { errorMessage, requestIdProps } from '../api/client'
import type { ContextNet } from '../lib/circuit'
import { CHECK_LABELS, VERDICT_LABELS, VERDICT_TONE, candidatesOf, citationHref, citationText, documentEvidenceOf, formatValue, judgementOf } from '../lib/judgement'
import { INPUT_LABELS } from '../lib/inputLabels'
import PriceLookup from './PriceLookup'

export type DetailTab = { key: string; runId: string; part: string | null; label: string }
type Context = { target: CircuitPart; nets: ContextNet[]; counts: { parts: number; nets: number }; reviewer: string }

function CheckCitation({ citation, showDocument }: { citation?: CitationDto | null; showDocument: boolean }) {
  const href = citationHref(citation)
  const where = citation && ((showDocument && citation.document) || (citation.page != null && citation.page !== '') || citation.table || citation.row) ? <>
    {showDocument && citation.document && <span className="citation-document">{citation.document}</span>}
    {citation.page != null && citation.page !== '' && <span>{citation.page}쪽</span>}
    {citation.table && <span><span className="sr-only">표: </span>{citation.table}</span>}
    {citation.row && <span><span className="sr-only">행: </span>{citation.row}</span>}
  </> : <span>출처 위치 없음</span>
  return href ? <a className="citation-fields" href={href} target="_blank" rel="noreferrer">{where}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span className="citation-fields">{where}</span>
}

function requiredValue(check: CheckDto) {
  const op = check.threshold != null && check.op ? `${check.op === '>=' ? '≥' : check.op === '<=' ? '≤' : check.op} ` : ''
  return op + (formatValue(check.threshold, check.unit) || '값 없음')
}

function CheckResult({ state }: { state: string }) {
  return <span className={`result tone-${state === 'pass' ? 'identical' : state === 'fail' ? 'insufficient' : 'unverified'}`}>{CHECK_LABELS[state] ?? '확인 안 됨'}</span>
}

export function Checks({ candidate, resolved, showDocument = false }: { candidate: CandidateDto | undefined; resolved: boolean; showDocument?: boolean }) {
  const rows = candidate?.checks ?? []
  const empty = resolved ? '이 결과에는 조건별 대조 값이 없습니다. 아래 질문에 후보와 사용 조건을 보완해 주세요.' : '검토 후 대조 값이 표시됩니다. 아래에 후보와 사용 조건을 입력해 주세요.'
  if (showDocument) return rows.length ? <ul className="condition-checks" aria-label={`후보 ${candidate?.part ?? '부품'}의 조건 대조`}>{rows.map((check, index) => {
    const state = check.result ?? 'unverified'
    return <li key={`${check.code}-${index}`}>
      <details className="condition-check">
        <summary>
          <span className="check-title"><strong>{check.code}</strong><CheckResult state={state} /><ChevronDown aria-hidden="true" /><span className="sr-only">기준·근거</span></span>
          <span className="check-values"><span><span className="check-label">요구</span><strong>{requiredValue(check)}</strong></span><span><span className="check-label">후보 값</span><strong>{formatValue(check.value, check.unit) || '값 없음'}</strong></span></span>
        </summary>
        <div className="check-evidence"><dl>
          <div><dt>기준</dt><dd>{check.basis || '기준 정보 없음'}</dd></div>
          <div><dt>시험 조건</dt><dd>{check.condition || '표 기본 조건'}</dd></div>
          <div><dt>근거</dt><dd><CheckCitation citation={check.citation} showDocument /></dd></div>
        </dl>{state === 'pass' && check.why && <p className="property-note">{check.why}</p>}</div>
      </details>
      {state !== 'pass' && check.why && <p className="check-reason">{check.why}</p>}
    </li>
  })}</ul> : <p className="property-note">{empty}</p>
  return <div className="table-scroll"><table className="checks">
    <caption className="sr-only">후보 {candidate?.part ?? '부품'}의 조건별 요구 값과 데이터시트 근거</caption>
    <thead><tr><th scope="col">항목</th><th scope="col">기준</th><th scope="col" className="num">요구</th><th scope="col" className="num">후보 값</th><th scope="col">결과</th><th scope="col">근거 위치</th></tr></thead>
    <tbody>{rows.length === 0 ? <tr className="checks-empty"><td colSpan={6}>{empty}</td></tr>
      : rows.map((check, index) => {
        const state = check.result ?? 'unverified'
        return <tr key={`${check.code}-${index}`}>
          <th scope="row">{check.code}</th>
          <td className="basis" data-label="기준">{check.basis}</td>
          <td className="num" data-label="요구">{requiredValue(check)}</td>
          <td className="num strong" data-label="후보 값" title={check.condition ?? undefined}>{formatValue(check.value, check.unit) || '값 없음'}</td>
          <td data-label="결과"><CheckResult state={state} /></td>
          <td data-label="근거" title={check.citation?.document ?? undefined}><CheckCitation citation={check.citation} showDocument={false} /></td>
        </tr>
      })}</tbody>
  </table></div>
}

function Approval({ candidate, messageId, reviewer }: { candidate: CandidateDto; messageId: number | null; reviewer: string }) {
  const quantityId = useId()
  const client = useQueryClient()
  const saved = useQuery({ queryKey: ['message-approvals', messageId], queryFn: ({ signal }) => listMessageApprovals(messageId!, signal), enabled: messageId !== null, retry: false, refetchOnMount: 'always' })
  const approval = saved.data?.find(item => item.message_id === messageId && item.candidate_part === candidate.part && item.verdict === candidate.verdict)
  const other = !approval && saved.data?.[0]
  const checking = messageId !== null && (saved.isPending || saved.isFetching)
  const [quote, setQuote] = useState<QuoteDto | null>(null)
  const currentQuote = quote?.approval_id === approval?.id ? quote : null
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const approvable = candidate.verdict !== 'NOT_VERIFIED' && candidate.verdict !== 'NOT_SUFFICIENT'
  async function act(job: () => Promise<void>) { if (busy) return; setBusy(true); setError(null); try { await job() } catch (reason) { setError(reason) } finally { setBusy(false) } }
  async function approve() {
    try {
      const record = await approveMessage(messageId!, candidate.part, candidate.verdict)
      client.setQueryData(['message-approvals', messageId], [record])
      void client.invalidateQueries({ queryKey: ['approved-cases'] })
    } catch (reason) {
      if ((reason as ApiError)?.code === 'ALREADY_APPROVED') {
        const current = await saved.refetch()
        if (current.data?.length) return
      }
      throw reason
    }
  }
  function openQuote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const quantity = Math.max(1, Math.floor(Number(new FormData(event.currentTarget).get('quantity'))) || 1)
    void act(async () => setQuote(await createQuote(approval!.id, quantity)))
  }
  return <div className="approval">
    <p className="approval-state">{approval ? <ShieldCheck aria-hidden="true" /> : <CircleDashed aria-hidden="true" />}{approval ? '승인됨' : checking ? '승인 상태 확인 중' : saved.error ? '승인 상태 확인 안 됨' : other ? '다른 후보가 승인됨' : '승인 전'}</p>
    {approval && <p className="property-note">{reviewer}</p>}
    {other && <p className="property-note">이 질문에서 승인한 후보: {other.candidate_part}</p>}
    {currentQuote && <p className="property-note">견적 {currentQuote.part_number} × {currentQuote.quantity}</p>}
    {!approval && !other && <button className="btn btn-primary" disabled={busy || checking || Boolean(saved.error) || messageId === null || !approvable} onClick={() => void act(approve)}>{busy ? '저장 중' : '검토하고 승인'}</button>}
    {!approvable && <p className="property-note">이 판정은 승인 대상이 아닙니다.</p>}
    {saved.error && <div className="notice" role="alert" {...requestIdProps(saved.error)}><p>승인 상태를 불러오지 못했습니다. {errorMessage(saved.error)}</p><button className="btn" onClick={() => void saved.refetch()}>승인 상태 다시 확인</button></div>}
    {approval && !currentQuote && <form className="quote" onSubmit={openQuote}><label className="sr-only" htmlFor={quantityId}>수량</label><input id={quantityId} name="quantity" className="input" type="number" min={1} defaultValue={1} inputMode="numeric" /><button className="btn btn-primary" disabled={busy}>견적 열기</button></form>}
    {error ? <p className="notice" role="alert" {...requestIdProps(error)}>{approval ? '견적을 저장하지 못했습니다. 견적 열기로 다시 시도해 주세요.' : '승인을 저장하지 못했습니다. 검토하고 승인으로 다시 시도해 주세요.'} {errorMessage(error)}</p> : null}
  </div>
}


function DetailsPanel({ tab, active, panelId, focus, onFocused, fallback, target, nets, counts, reviewer }: Context & {
  tab: DetailTab; active: boolean; panelId: string; focus: boolean; onFocused: () => void; fallback?: ResultDto
}) {
  const panel = useRef<HTMLDivElement>(null)
  const details = useRef<HTMLHeadingElement>(null)
  const evidenceHeading = useRef<HTMLHeadingElement>(null)
  const runId = tab.runId
  const run = useQuery({ queryKey: ['run', runId], queryFn: ({ signal }) => getRun(runId, signal), enabled: Boolean(runId), retry: false, staleTime: Infinity })
  const roles = useQuery({ queryKey: ['judge-roles'], queryFn: ({ signal }) => listJudgeRoles(signal), retry: false, staleTime: Infinity })
  const result = fallback ?? run.data?.result
  const candidates = candidatesOf(result)
  const candidate = candidates.find(item => item.part === tab.part)
  const judgement = judgementOf(result)
  const role = candidate?.role ?? judgement?.roles?.[0] ?? ''
  const roleName = (Array.isArray(roles.data) ? roles.data.find(item => item.code === role)?.name : '') || role
  const documents = documentEvidenceOf(result)
  const resultLoading = run.isFetching && !result
  useEffect(() => {
    if (!active || !focus || !result) return
    const heading = candidate ? details.current : evidenceHeading.current
    heading?.focus({ preventScroll: true })
    if (panel.current) panel.current.scrollTop = 0
    onFocused()
  }, [active, focus, result, candidate, onFocused])
  return <div ref={panel} className="props-content" role="tabpanel" id={panelId} aria-label={tab.label} hidden={!active}>
      <section className="property-group">
        {candidate ? <><h2 ref={details} className="candidate-heading" tabIndex={-1}>{candidate.part}</h2><p className="property-note">선택한 질문의 검토 결과</p></>
          : <><h2>부품 상세</h2><p className="property-note">채팅에서 부품의 상세 보기를 선택해 주세요.</p></>}
      </section>
      {candidate && <>
      <section className="property-group" aria-labelledby={`approval-heading-${panelId}`}><h2 id={`approval-heading-${panelId}`}>승인</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">승인할 결과를 기다리는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : candidate ? <Approval key={`${runId}-${candidate.part}`} candidate={candidate} messageId={run.data?.message_id ?? null} reviewer={reviewer} /> : <p className="property-note">판정 후 승인할 수 있습니다. 질문에 후보와 사용 조건을 입력해 주세요.</p>}
      </section>
      <section className="property-group" aria-labelledby={`verdict-heading-${panelId}`}><h2 id={`verdict-heading-${panelId}`}>판정</h2><dl>
        <div><dt>결과</dt><dd>{candidate ? <span className={`dot tone-${VERDICT_TONE[candidate.verdict]}`}>{VERDICT_LABELS[candidate.verdict]}</span> : result ? '판정 없음' : '결과 대기'}</dd></div>
        {candidate && <div><dt>기판 수정</dt><dd>{candidate.board_change === true ? '필요' : candidate.board_change === false ? '필요 없음' : '확인 안 됨'}</dd></div>}
        {(judgement?.input_conditions ?? []).map(item => <div key={item.code}><dt>{INPUT_LABELS[item.code] ?? '추가 조건'}</dt><dd>{item.value}</dd></div>)}
      </dl>
        {candidate.package_citation && <p className="property-note">패키지 근거: {citationHref(candidate.package_citation) ? <a href={citationHref(candidate.package_citation)} target="_blank" rel="noreferrer">{candidate.package_citation.document} {citationText(candidate.package_citation)}<span className="sr-only"> (새 탭)</span></a> : <span>{candidate.package_citation.document} {citationText(candidate.package_citation)}</span>}</p>}
      </section>
      <section className="property-group" aria-labelledby={`checks-title-${panelId}`}><h2 id={`checks-title-${panelId}`}>조건 대조</h2>
        <Checks candidate={candidate} resolved showDocument />
        {[...(candidate.cautions ?? []), ...(candidate.missing ?? []).map(item => `문서에 없는 값: ${item}`), ...(candidate.uncertain ?? []).map(item => `확실하지 않은 값: ${item}`)].map(note => <p className="caution" key={note}>{note}</p>)}
      </section>
      </>}
      <section className="property-group" aria-labelledby={`circuit-heading-${panelId}`}><h2 id={`circuit-heading-${panelId}`}>회로</h2><dl>
        {roles.isFetching && !roles.data && <div><dt>역할</dt><dd role="status"><span className="sr-only">역할 이름을 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></dd></div>}
        {roleName && <div><dt>역할</dt><dd>{roleName}</dd></div>}
        <div><dt>현재 부품</dt><dd>{target.value}</dd></div>
        <div><dt>풋프린트</dt><dd>{target.footprint.replace(/^import_input:/, '') || '넷리스트에 없음'}</dd></div>
        {nets.map(net => <div key={net.name}><dt>핀 {net.pin}</dt><dd>{net.name}</dd></div>)}
        <div><dt>부품 수</dt><dd>{counts.parts}개</dd></div><div><dt>넷 수</dt><dd>{counts.nets}개</dd></div>
      </dl>{candidate && (judgement?.role_evidence ?? []).map(note => <p className="property-note" key={note}>역할 근거: {note}</p>)}{roles.error && <div className="notice" role="alert"><p>역할 이름을 불러오지 못했습니다.</p><button className="btn" onClick={() => void roles.refetch()}>역할 다시 불러오기</button></div>}</section>
      {(result?.price_parts ?? []).length > 0 && <section className="property-group" aria-labelledby={`price-heading-${panelId}`}><h2 id={`price-heading-${panelId}`}>가격·재고</h2>
        <PriceLookup key={result!.price_parts.join(',')} parts={result!.price_parts} /></section>}
      {(!candidates.length || documents.length > 0) && <section className="property-group" aria-labelledby={`evidence-heading-${panelId}`}><h2 ref={evidenceHeading} id={`evidence-heading-${panelId}`} tabIndex={-1}>{candidates.length ? '추가 문서 근거' : '근거'}</h2>
        {resultLoading ? <div className="skeleton" role="status"><span className="sr-only">근거를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /></div> : documents.length ? <ul className="document-list">{documents.map((item, index) => <li key={index}><FileText aria-hidden="true" /><div className="document-entry">
          {citationHref(item) ? <a href={citationHref(item)} target="_blank" rel="noreferrer">{item.document}<ExternalLink aria-hidden="true" /><span className="sr-only"> (새 탭)</span></a> : <span>{item.document}</span>}
          <span className="property-note">{[citationText(item), item.section].filter(Boolean).join(' · ') || '출처 위치 없음'}</span></div></li>)}</ul> : <p className="property-note">{result ? '인용 문서가 없습니다. 질문에 후보 품번을 보완해 주세요.' : '검토 후 문서가 표시됩니다. 질문에 후보와 사용 조건을 입력해 주세요.'}</p>}
      </section>}

    {run.error && <div className="notice" role="alert"><p>상세 결과를 불러오지 못했습니다.</p><button className="btn" onClick={() => void run.refetch()}>상세 다시 불러오기</button></div>}
  </div>
}

export default function ReviewDetails({ tabs, selected, open, onSelect, onClose, onDismiss, focus, onFocused, runId, result, ...context }: Context & {
  tabs: DetailTab[]; selected: DetailTab | null; onSelect: (tab: DetailTab | null) => void; onClose: (tab: DetailTab) => void; onDismiss: () => void;
  open: boolean; focus: boolean; onFocused: () => void; runId: string; result?: ResultDto
}) {
  const list = useRef<HTMLDivElement>(null)
  const refocus = useRef(false)
  useEffect(() => {
    if (!refocus.current) return
    list.current?.querySelector<HTMLButtonElement>('[aria-selected="true"]')?.focus({ preventScroll: true })
    refocus.current = false
  }, [tabs, selected])
  function close(tab: DetailTab) { refocus.current = true; onClose(tab) }
  function key(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key === 'Delete' && index > 0) { event.preventDefault(); close(tabs[index - 1]); return }
    const next = event.key === 'ArrowRight' ? (index + 1) % (tabs.length + 1) : event.key === 'ArrowLeft' ? (index + tabs.length) % (tabs.length + 1) : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length : -1
    if (next < 0) return
    event.preventDefault()
    onSelect(next === 0 ? null : tabs[next - 1])
    list.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
  }
  const base: DetailTab = { key: 'context', runId, part: null, label: '회로 정보' }
  return <aside id="candidate-details" className={`props${open ? ' props-open' : ''}`} aria-label="부품 상세" onKeyDown={event => { if (event.key === 'Escape') onDismiss() }}>
    <div ref={list} className="props-tabs" role="tablist" aria-label="열린 상세 정보">
      <button type="button" role="tab" aria-selected={!selected} aria-controls="detail-context" tabIndex={selected ? -1 : 0} onClick={() => onSelect(null)} onKeyDown={event => key(event, 0)}>회로 정보</button>
      {tabs.map((tab, index) => <div className="props-tab" key={tab.key}>
        <button type="button" role="tab" aria-selected={selected?.key === tab.key} aria-controls={`detail-${index}`} tabIndex={selected?.key === tab.key ? 0 : -1} onClick={() => onSelect(tab)} onKeyDown={event => key(event, index + 1)}>{tab.label}</button>
        <button type="button" className="icon-btn" tabIndex={selected?.key === tab.key ? 0 : -1} aria-label={`${tab.label} 닫기`} onClick={() => close(tab)}><X aria-hidden="true" /></button>
      </div>)}
    </div>
    <button type="button" className="btn props-dismiss" onClick={onDismiss}>상세 패널 접기</button>
    <DetailsPanel {...context} tab={base} panelId="detail-context" active={!selected} focus={false} onFocused={onFocused} fallback={result} />
    {tabs.map((tab, index) => <DetailsPanel key={tab.key} {...context} tab={tab} panelId={`detail-${index}`} active={selected?.key === tab.key} focus={selected?.key === tab.key && focus} onFocused={onFocused} fallback={tab.runId === runId ? result : undefined} />)}
  </aside>
}
