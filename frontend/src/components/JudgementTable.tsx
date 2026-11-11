import { useState } from 'react'
import type { CandidateDto, JudgementDto } from '../api/conversations'
import { candidatesOf } from './circuitContext'
import AccessibleDialog from './AccessibleDialog'

const LABELS: Record<CandidateDto['verdict'], string> = {
  IDENTICAL: '동일품', SPEC_EQUIVALENT: '사양 동등', ROLE_SUFFICIENT: '역할상 충분', NOT_SUFFICIENT: '불충족', NOT_VERIFIED: '문서로 확인 안 됨',
}
const RESULT_LABELS: Record<string, string> = { pass: '통과', fail: '불충족', unverified: '확인 안 됨' }

function displayValue(value: number | number[] | null | undefined, unit?: string | null) {
  if (value == null) return 'MISSING'
  return `${Array.isArray(value) ? value.join('–') : value}${unit ? ` ${unit}` : ''}`
}

function sourceLink(sourceUrl?: string, page?: number | string | null) {
  if (!sourceUrl) return null
  try {
    const url = new URL(sourceUrl)
    if (url.protocol !== 'https:') return null
    if (page != null && `${page}` !== '') return `${sourceUrl.split('#')[0]}#page=${page}`
    return sourceUrl
  } catch { return null }
}

function ConditionTable({ candidate }: { candidate: CandidateDto }) {
  if (!candidate.checks?.length) return <p>확인된 사양 비교가 없습니다.</p>
  return <div className="table-scroll"><table className="condition-table" aria-label={`${candidate.part} 판정 조건표`}>
    <thead><tr><th>조건</th><th>기준과 계산</th><th>후보 값</th><th>시험 조건</th><th>결과</th><th>근거</th></tr></thead>
    <tbody>{candidate.checks.map((check, index) => {
      const op = check.op === '>=' ? '≥' : check.op === '<=' ? '≤' : check.op || ''
      const href = sourceLink(check.citation?.source_url, check.citation?.page)
      const coordinate = [check.citation?.document, check.citation?.page != null ? `${check.citation.page}쪽` : '', check.citation?.table, check.citation?.row].filter(Boolean).join(' · ')
      return <tr key={`${check.code}-${index}`}><th scope="row">{check.code}</th>
        <td><span>{check.basis || '계산 근거 없음'}</span>{check.threshold != null && <strong>{`${op ? `${op} ` : ''}${displayValue(check.threshold, check.unit)}`}</strong>}</td>
        <td>{displayValue(check.value, check.unit)}</td><td>{check.condition || '확인 안 됨'}</td>
        <td><strong>{RESULT_LABELS[check.result || ''] || check.result || '확인 안 됨'}</strong>{check.why && <small>{check.why}</small>}</td>
        <td>{coordinate || '출처 좌표 없음'}{href && <a href={href} target="_blank" rel="noreferrer" aria-label={`${check.code} 근거 열기`}>원문 열기</a>}</td></tr>
    })}</tbody>
  </table></div>
}

export default function JudgementTable({ judgement, selectedIndex, onSelectCandidate }: {
  judgement?: JudgementDto | Record<string, never>
  selectedIndex?: number | null
  onSelectCandidate?: (candidate: CandidateDto, index: number) => void
}) {
  const [detail, setDetail] = useState<CandidateDto | null>(null)
  if (!judgement || !('kind' in judgement)) return <section className="panel result-section"><h2>판정</h2><p>아직 판정 결과가 없습니다.</p></section>
  const candidates = candidatesOf(judgement)
  return <section className="panel result-section" aria-labelledby="judgement-heading"><h2 id="judgement-heading">후보 판정</h2>
    <p className="disclaimer">같은 동작은 보장하지 않습니다.</p>
    {candidates.length === 0 ? <p>판정 가능한 후보가 없습니다.</p> : <div className="table-scroll"><table><thead><tr><th>후보</th><th>판정</th><th>기판 수정</th><th>확인 사항</th><th>상세</th></tr></thead>
      <tbody>{candidates.map((candidate, index) => <tr key={`${candidate.part}-${index}`} className={selectedIndex === index ? 'candidate-selected' : ''}>
        <td>{onSelectCandidate ? <button className="candidate-select" aria-label={`${candidate.part} 후보 선택`} aria-pressed={selectedIndex === index}
          onClick={() => onSelectCandidate(candidate, index)}>{candidate.part}</button> : candidate.part}</td><td>{LABELS[candidate.verdict]}</td>
        <td>{candidate.board_change === true ? '필요' : candidate.board_change === false ? '불필요' : '확인 안 됨'}</td>
        <td>{[...(candidate.missing ?? []), ...(candidate.uncertain ?? []), ...(candidate.cautions ?? [])].join(', ') || '확인 안 됨'}</td><td><button className="secondary compact" onClick={() => setDetail(candidate)}>{candidate.part} 상세</button></td></tr>)}</tbody></table></div>}
    {detail && <AccessibleDialog title="후보 상세" onClose={() => setDetail(null)}><dl className="detail-list"><div><dt>후보 품번</dt><dd>{detail.part}</dd></div><div><dt>판정</dt><dd>{LABELS[detail.verdict]}</dd></div><div><dt>역할</dt><dd>{detail.role || '확인 안 됨'}</dd></div><div><dt>패키지 차이</dt><dd>{detail.board_change === true ? '기판 수정 필요' : detail.board_change === false ? '기판 수정 불필요' : 'MISSING'}</dd></div></dl>
      <h3>판정 조건</h3><ConditionTable candidate={detail} />
      {[...(detail.missing ?? []), ...(detail.uncertain ?? []), ...(detail.cautions ?? [])].length > 0 && <p>미확인 또는 주의: {[...(detail.missing ?? []), ...(detail.uncertain ?? []), ...(detail.cautions ?? [])].join(', ')}</p>}</AccessibleDialog>}
  </section>
}
