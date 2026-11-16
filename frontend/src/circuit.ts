/** 공개 회로 값을 화면에 투영한다. 회로 역할을 추론하지 않는다. 출처: backend/projects의 공개 Project. */
import type { Project } from './types.ts';
export function partsOf(project: Project | null) {
  return (project?.connections?.components ?? project?.connections?.parts ?? []) as {
    ref: string;
    value: string;
    footprint?: string;
    [key: string]: any;
  }[];
}
export function pinsOf(project: Project | null, ref: string) {
  return ((project?.connections?.nets ?? []) as any[]).flatMap((n) =>
    (n.nodes ?? [])
      .filter((p: any) => p.ref === ref)
      .map((p: any) => ({
        pin: String(p.pin),
        net: n.name ?? n.code ?? '',
        name: p.pinfunction ?? p.name ?? '',
      })),
  );
}
/** ref에 은/는을 붙인다. 끝 글자를 한국어로 읽은 받침으로 고른다(숫자는 영·일·이·삼…, 영문은 엘·엠·엔·알만 받침). 서버 _topic과 같은 규칙. */
function topic(ref: string) {
  const last = ref.slice(-1).toUpperCase(),
    code = last.charCodeAt(0);
  const final =
    code >= 0xac00 && code <= 0xd7a3 ? (code - 0xac00) % 28 > 0 : '013678LMNR'.includes(last);
  return ref + (final ? '은' : '는');
}
/**
 * 판정 대상으로 고를 수 없는 부품의 이유(고를 수 있으면 빈 문자열). LED·표시기(7세그)·다이오드가 아닌 부품이다.
 * 서버(backend/conversations/memory_service.py의 _require_supported_target)와 같은 규칙·같은 문구라
 * 화면이 미리 막은 부품도 서버가 같은 이유로 422를 준다. 서버가 최종 판단이고 이 함수는 안내용이다.
 */
export function unsupportedPartReason(part: {
  ref: string;
  value?: string;
  footprint?: string;
  description?: string;
}): string {
  const identifiers = `${part.value ?? ''} ${part.footprint ?? ''}`;
  const description = (part.description ?? '').trim();
  const ledDescription =
    /light[\s-]*emitting[\s-]*diode|발광\s*다이오드|^(?:(?:red|green|blue|white|yellow|amber|orange|rgb)\s+)?leds?$/i.test(
      description,
    );
  if (
    /(^|[^a-z0-9])leds?(?=$|[^a-z])/i.test(identifiers) ||
    ledDescription ||
    /^LED\d/i.test(part.ref)
  )
    return `${topic(part.ref)} LED라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.`;
  if (/(^|[^a-z0-9])(?:7|seven)[\s_-]*seg(?:ment)?/i.test(identifiers))
    return `${topic(part.ref)} 표시기라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.`;
  if (!/^D\d/i.test(part.ref))
    return `${topic(part.ref)} 다이오드가 아니라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.`;
  return '';
}
/** 회로 없는 대화에서 회로가 필요한 질문의 서버 답(SPEC 8.9). 이 답이면 화면이 넷리스트 첨부 · 기존 회로 고르기 카드를 붙인다. backend/multi_agent/messages.py NEED_NETLIST와 같은 글자다. */
export const NEEDS_CIRCUIT = '이 질문은 회로가 있어야 검토할 수 있어요. 넷리스트를 첨부해 주세요.';
/** 회로 없이 보낸 첫 질문으로 만드는 프로젝트 이름: 겹친 공백을 한 칸으로 줄인 앞 30자. 비면 "새 대화". */
export function projectNameFromQuestion(question: string) {
  return question.replace(/\s+/g, ' ').trim().slice(0, 30).trim() || '새 대화';
}
