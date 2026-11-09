import type { CandidateDto, CitationDto, EvidenceDto } from '../api/conversations'

function candidateCitations(candidate?: CandidateDto) {
  if (!candidate) return []
  const values = [candidate.package_citation, ...(candidate.checks?.map(check => check.citation) ?? [])]
    .filter((item): item is CitationDto => Boolean(item))
  return values.filter((item, index) => values.findIndex(other => JSON.stringify(other) === JSON.stringify(item)) === index)
}

export default function EvidencePanel({ evidence, candidate }: { evidence: EvidenceDto[]; candidate?: CandidateDto }) {
  const citations = candidateCitations(candidate)
  return <section className="panel result-section" aria-labelledby="evidence-heading"><h2 id="evidence-heading">근거</h2>
    {evidence.length === 0 ? <p>표시할 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{evidence.map((item, index) => <li key={`${item.document}-${item.citation_number}-${index}`}>
      <strong>{item.document || '문서명 없음'}</strong>
      <span>{[item.page !== null && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row, item.section].filter(Boolean).join(' · ')}</span>
      {item.citation_number && <span>인용 {item.citation_number}</span>}
    </li>)}</ol>}
    {candidate && <div className="candidate-evidence"><h3>{candidate.part} 데이터시트 근거</h3>
      {citations.length === 0 ? <p>선택 후보의 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{citations.map((item, index) => <li key={`${item.document}-${item.chunk_id}-${index}`}>
        <strong>{item.document || '문서명 없음'}</strong>
        <span>{[item.page !== null && item.page !== undefined && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row].filter(Boolean).join(' · ')}</span>
      </li>)}</ol>}
    </div>}
  </section>
}
