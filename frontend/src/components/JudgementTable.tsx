import type { CandidateDto, JudgementDto } from '../api/conversations'

const LABELS: Record<CandidateDto['verdict'], string> = {
  IDENTICAL: '동일품', SPEC_EQUIVALENT: '사양 동등', ROLE_SUFFICIENT: '역할상 충분', NOT_SUFFICIENT: '불충족', NOT_VERIFIED: '문서로 확인 안 됨',
}

export default function JudgementTable({ judgement }: { judgement?: JudgementDto | Record<string, never> }) {
  if (!judgement || !('kind' in judgement)) return <section className="panel result-section"><h2>판정</h2><p>아직 판정 결과가 없습니다.</p></section>
  const candidates = judgement.kind === 'find' ? [...judgement.shown, ...judgement.unverified] : judgement.results
  return <section className="panel result-section" aria-labelledby="judgement-heading"><h2 id="judgement-heading">후보 판정</h2>
    <p className="disclaimer">같은 동작은 보장하지 않습니다.</p>
    {candidates.length === 0 ? <p>판정 가능한 후보가 없습니다.</p> : <div className="table-scroll"><table><thead><tr><th>후보</th><th>판정</th><th>기판 수정</th><th>확인 사항</th></tr></thead>
      <tbody>{candidates.map((candidate, index) => <tr key={`${candidate.part}-${index}`}><td>{candidate.part}</td><td>{LABELS[candidate.verdict]}</td>
        <td>{candidate.board_change === true ? '필요' : candidate.board_change === false ? '불필요' : '확인 안 됨'}</td>
        <td>{[...(candidate.missing ?? []), ...(candidate.uncertain ?? []), ...(candidate.cautions ?? [])].join(', ') || '—'}</td></tr>)}</tbody></table></div>}
  </section>
}
