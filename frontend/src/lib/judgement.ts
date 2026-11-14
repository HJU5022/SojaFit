import type { CandidateDto, CitationDto, EvidenceDto, JudgementDto, ResultDto } from '../api/conversations'

// 판정 표기는 SPEC 3절의 화면 표기를 그대로 쓴다.
export const VERDICT_LABELS: Record<CandidateDto['verdict'], string> = {
  IDENTICAL: '동일품', SPEC_EQUIVALENT: '사양 동등', ROLE_SUFFICIENT: '역할상 충분', NOT_SUFFICIENT: '불충족', NOT_VERIFIED: '문서로 확인 안 됨',
}
export const VERDICT_TONE: Record<CandidateDto['verdict'], string> = {
  IDENTICAL: 'identical', SPEC_EQUIVALENT: 'equivalent', ROLE_SUFFICIENT: 'sufficient', NOT_SUFFICIENT: 'insufficient', NOT_VERIFIED: 'unverified',
}
export const CHECK_LABELS: Record<string, string> = { pass: '통과', fail: '불충족', unverified: '확인 안 됨' }

export function candidatesOf(result: ResultDto | undefined): CandidateDto[] {
  const judgement = result?.judgement as Partial<JudgementDto> | undefined
  if (!judgement || !('kind' in judgement)) return []
  return judgement.results?.length ? judgement.results : [...(judgement.shown ?? []), ...(judgement.unverified ?? [])]
}

export function judgementOf(result: ResultDto | undefined): JudgementDto | null {
  const judgement = result?.judgement as Partial<JudgementDto> | undefined
  return judgement && 'kind' in judgement ? judgement as JudgementDto : null
}

// 원본 답변은 보존하고, 이 답변의 근거에 등록된 숫자 인용만 화면에서 숨긴다.
export function withoutCorpusCitations(text: string, evidence: EvidenceDto[] = []) {
  const numbers = new Set(evidence.map(item => item.citation_number).filter(id => /^\d+$/.test(id)))
  return text.replace(/[ \t]*\[([^\[\]\n]+)\](?!\()/g, (match, group: string) => {
    const ids = group.split(',').map(id => id.trim())
    const remaining = ids.filter(id => !numbers.has(id))
    return remaining.length === ids.length ? match : remaining.length ? `${match.match(/^[ \t]*/)?.[0] ?? ''}[${remaining.join(', ')}]` : ''
  })
}

export function documentEvidenceOf(result: ResultDto | undefined) {
  const location = (item: CitationDto) => JSON.stringify([item.document, item.page, item.table || '', item.row || '', citationHref(item)])
  const covered = new Set(candidatesOf(result).flatMap(item => [item.package_citation, ...(item.checks ?? []).map(check => check.citation)]).filter(item => item != null).map(location))
  const entries = (result?.evidence ?? []).filter(item => !covered.has(location(item)))
  return [...new Map(entries.map(item => [JSON.stringify([item.document, item.page, item.table, item.row, item.section, citationHref(item)]), item])).values()]
}

export function formatValue(value: number | number[] | null | undefined, unit?: string | null) {
  if (value === null || value === undefined) return ''
  const text = Array.isArray(value) ? value.join(' ~ ') : String(value)
  return unit ? `${text} ${unit}` : text
}

export function citationText(citation: CitationDto | null | undefined) {
  if (!citation) return ''
  return [citation.page != null && citation.page !== '' ? `${citation.page}쪽` : '', citation.table, citation.row].filter(Boolean).join(' · ')
}

// 서버가 준 출처 주소만 쓴다. http(s)가 아니면 링크를 만들지 않는다.
export function citationHref(citation: CitationDto | null | undefined) {
  if (!citation?.source_url || !/^https?:\/\//.test(citation.source_url)) return ''
  const page = citation.outline_page ?? citation.page
  return typeof page === 'number' ? `${citation.source_url.split('#')[0]}#page=${page}` : citation.source_url
}
