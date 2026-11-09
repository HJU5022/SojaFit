import type { EvidenceDto } from '../api/conversations'

export default function EvidencePanel({ evidence }: { evidence: EvidenceDto[] }) {
  return <section className="panel result-section" aria-labelledby="evidence-heading"><h2 id="evidence-heading">근거</h2>
    {evidence.length === 0 ? <p>표시할 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{evidence.map((item, index) => <li key={`${item.document}-${item.citation_number}-${index}`}>
      <strong>{item.document || '문서명 없음'}</strong>
      <span>{[item.page !== null && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row, item.section].filter(Boolean).join(' · ')}</span>
      {item.citation_number && <span>인용 {item.citation_number}</span>}
    </li>)}</ol>}
  </section>
}
