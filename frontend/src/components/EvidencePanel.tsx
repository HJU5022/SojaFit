import { useState } from 'react'
import type { CandidateDto, CitationDto, EvidenceDto } from '../api/conversations'
import AccessibleDialog from './AccessibleDialog'

function candidateCitations(candidate?: CandidateDto) {
  if (!candidate) return []
  const values = [candidate.package_citation, ...(candidate.checks?.map(check => check.citation) ?? [])]
    .filter((item): item is CitationDto => Boolean(item))
  return values.filter((item, index) => values.findIndex(other => JSON.stringify(other) === JSON.stringify(item)) === index)
}

export default function EvidencePanel({ evidence, candidate }: { evidence: EvidenceDto[]; candidate?: CandidateDto }) {
  const citations = candidateCitations(candidate)
  const [detail, setDetail] = useState<{ document?: string; page?: number | string | null; table?: string; row?: string; section?: string; field?: string } | null>(null)
  return <section className="panel result-section" aria-labelledby="evidence-heading"><h2 id="evidence-heading">근거</h2>
    {evidence.length === 0 ? <p>표시할 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{evidence.map((item, index) => <li key={`${item.document}-${item.citation_number}-${index}`}><button className="evidence-card" onClick={() => setDetail(item)}>
      <strong>{item.document || '문서명 없음'}</strong>
      <span>{[item.page !== null && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row, item.section].filter(Boolean).join(' · ')}</span>
      {item.citation_number && <span>인용 {item.citation_number}</span>}
    </button></li>)}</ol>}
    {candidate && <div className="candidate-evidence"><h3>{candidate.part} 데이터시트 근거</h3>
      {citations.length === 0 ? <p>선택 후보의 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{citations.map((item, index) => <li key={`${item.document}-${item.chunk_id}-${index}`}><button className="evidence-card" onClick={() => setDetail(item)}>
        <strong>{item.document || '문서명 없음'}</strong>
        <span>{[item.page !== null && item.page !== undefined && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row].filter(Boolean).join(' · ')}</span>
      </button></li>)}</ol>}
    </div>}
    {detail && <AccessibleDialog title="데이터시트 근거 상세" onClose={() => setDetail(null)}><dl className="detail-list"><div><dt>문서명</dt><dd>{detail.document || '확인 안 됨'}</dd></div><div><dt>페이지</dt><dd>{detail.page ?? '확인 안 됨'}</dd></div><div><dt>표</dt><dd>{detail.table || '확인 안 됨'}</dd></div><div><dt>행</dt><dd>{detail.row || '확인 안 됨'}</dd></div><div><dt>적용 사양</dt><dd>{detail.field || detail.section || '확인 안 됨'}</dd></div></dl><p>저장소에 원문이 제공되지 않은 경우 PDF 내용을 대신 표시하지 않습니다.</p></AccessibleDialog>}
  </section>
}
