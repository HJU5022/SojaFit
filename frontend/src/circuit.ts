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
    return `${part.ref}은(는) LED로 식별됩니다. 현재 LED 대체 판정은 지원하지 않습니다. 일반 다이오드를 선택해 주세요.`;
  if (/(^|[^a-z0-9])(?:7|seven)[\s_-]*seg(?:ment)?/i.test(identifiers))
    return `${part.ref}은(는) 표시기로 식별됩니다. 현재 표시기 대체 판정은 지원하지 않습니다. 일반 다이오드를 선택해 주세요.`;
  if (!/^D\d/i.test(part.ref))
    return `${part.ref}은(는) 현재 판정 범위 밖입니다. 지금은 다이오드만 판정합니다.`;
  return '';
}
