import { useState } from 'react'
import type { CandidateDto, CitationDto, EvidenceDto } from '../api/conversations'
import AccessibleDialog from './AccessibleDialog'

function pdfPage(url: string, page?: number | string | null) {
  if (!url.startsWith('https://')) return ''
  return typeof page === 'number' && page > 0 ? `${url.split('#')[0]}#page=${page}` : url
}

function candidateCitations(candidate?: CandidateDto) {
  if (!candidate) return []
  const values = [candidate.package_citation, ...(candidate.checks?.map(check => check.citation) ?? [])]
    .filter((item): item is CitationDto => Boolean(item))
  return values.filter((item, index) => values.findIndex(other => JSON.stringify(other) === JSON.stringify(item)) === index)
}

export default function EvidencePanel({ evidence, candidate }: { evidence: EvidenceDto[]; candidate?: CandidateDto }) {
  const citations = candidateCitations(candidate)
  const documents = [...(candidate?.checks?.map(check => check.citation) ?? []), candidate?.package_citation]
    .filter((item): item is CitationDto => Boolean(item?.source_url && pdfPage(item.source_url)))
  const uniqueDocuments = documents.filter((item, index) => documents.findIndex(other => other.source_url === item.source_url) === index)
  const [detail, setDetail] = useState<{ document?: string; page?: number | string | null; table?: string; row?: string; section?: string; field?: string } | null>(null)
  return <section className="panel result-section" aria-labelledby="evidence-heading"><h2 id="evidence-heading">근거</h2>
    {evidence.length === 0 ? <p>표시할 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{evidence.map((item, index) => <li key={`${item.document}-${item.citation_number}-${index}`}><button className="evidence-card" onClick={() => setDetail(item)}>
      <strong>{item.document || '문서명 없음'}</strong>
      <span>{[item.page !== null && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row, item.section].filter(Boolean).join(' · ')}</span>
      {item.citation_number && <span>인용 {item.citation_number}</span>}
    </button></li>)}</ol>}
    {candidate && <div className="candidate-evidence"><h3>{candidate.part} 데이터시트 근거</h3>
      <div className="package-boundary"><strong>{candidate.board_change === false ? '동일 패키지 가능성' : candidate.board_change === true ? '기판 변경 가능성 있음' : '패키지 변경 여부 확인 필요'}</strong>
        <p>{candidate.board_change === false ? '데이터시트 패키지 기준이며 직접 교체 보증이 아닙니다.' : candidate.board_change === true ? '패키지가 달라질 수 있다는 뜻이며 납땜·재배선 방법을 뜻하지 않습니다.' : '패키지 또는 기존 footprint 정보가 부족합니다.'}</p>
      </div>
      {uniqueDocuments.map(item => {
        const outline = documents.find(other => other.source_url === item.source_url && typeof other.outline_page === 'number' && other.outline_page > 0)?.outline_page
        return <div className="evidence-links" key={item.source_url}>
          <a href={pdfPage(item.source_url!, item.page)} target="_blank" rel="noreferrer noopener">{candidate.part} 공식 데이터시트 열기</a>
          {typeof outline === 'number' && <a href={pdfPage(item.source_url!, outline)} target="_blank" rel="noreferrer noopener">패키지 외형 {outline}쪽 열기</a>}
        </div>
      })}
      {citations.length === 0 ? <p>선택 후보의 구조화 근거가 없습니다.</p> : <ol className="evidence-list">{citations.map((item, index) => <li key={`${item.document}-${item.chunk_id}-${index}`}><button className="evidence-card" onClick={() => setDetail(item)}>
        <strong>{item.document || '문서명 없음'}</strong>
        <span>{[item.page !== null && item.page !== undefined && item.page !== '' ? `${item.page}쪽` : '', item.table, item.row].filter(Boolean).join(' · ')}</span>
      </button></li>)}</ol>}
    </div>}
    {detail && <AccessibleDialog title="데이터시트 근거 상세" onClose={() => setDetail(null)}><dl className="detail-list"><div><dt>문서명</dt><dd>{detail.document || '확인 안 됨'}</dd></div><div><dt>페이지</dt><dd>{detail.page ?? '확인 안 됨'}</dd></div><div><dt>표</dt><dd>{detail.table || '확인 안 됨'}</dd></div><div><dt>행</dt><dd>{detail.row || '확인 안 됨'}</dd></div><div><dt>적용 사양</dt><dd>{detail.field || detail.section || '확인 안 됨'}</dd></div></dl><p>저장소에 원문이 제공되지 않은 경우 PDF 내용을 대신 표시하지 않습니다.</p></AccessibleDialog>}
  </section>
}
