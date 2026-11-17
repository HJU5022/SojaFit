/**
 * 공개 회로 값을 화면에 투영한다. 회로 역할을 추론하지 않는다. 출처: backend/projects의 공개 Project.
 * 넷리스트 연결 그림의 배치(`layoutCircuit`)는 dagre(MIT, 그래프 자동 배치)가 정한다. 부품 위치 · 배선이 없는 넷리스트에서
 * 부품은 상자, 넷은 이름표, 선은 "이 부품의 핀이 이 넷에 붙어 있다"만 뜻한다(실제 회로도 배치 · 기호가 아니다).
 */
import dagre from '@dagrejs/dagre';
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
/** 끝 글자를 한국어로 읽은 받침이 있나(숫자는 영·일·이·삼…, 영문은 엘·엠·엔·알만 받침). 서버 _topic과 같은 규칙. */
function hasFinal(ref: string) {
  const last = ref.slice(-1).toUpperCase(),
    code = last.charCodeAt(0);
  return code >= 0xac00 && code <= 0xd7a3 ? (code - 0xac00) % 28 > 0 : '013678LMNR'.includes(last);
}
/** ref에 은/는을 붙인다. */
function topic(ref: string) {
  return ref + (hasFinal(ref) ? '은' : '는');
}
type PartLike = { ref: string; value?: string; footprint?: string; description?: string };
/** 판정 대상으로 고를 수 없는 부품의 종류('LED' · '표시기' · '다이오드가 아닌 부품'). 고를 수 있으면 빈 문자열. */
function unsupportedKind(part: PartLike): string {
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
    return 'LED';
  if (/(^|[^a-z0-9])(?:7|seven)[\s_-]*seg(?:ment)?/i.test(identifiers)) return '표시기';
  if (!/^D\d/i.test(part.ref)) return '다이오드가 아닌 부품';
  return '';
}
/**
 * 판정 대상으로 고를 수 없는 부품의 이유(고를 수 있으면 빈 문자열). LED·표시기(7세그)·다이오드가 아닌 부품이다.
 * 서버(backend/conversations/memory_service.py의 _require_supported_target)와 같은 규칙·같은 문구라
 * 화면이 미리 막은 부품도 서버가 같은 이유로 422를 준다. 서버가 최종 판단이고 이 함수는 안내용이다.
 */
export function unsupportedPartReason(part: PartLike): string {
  const kind = unsupportedKind(part);
  if (!kind) return '';
  const why = kind === '다이오드가 아닌 부품' ? '다이오드가 아니라서' : kind + '라서';
  return `${topic(part.ref)} ${why} 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.`;
}
/** 회로 패널에 보일 사실 한 줄(#50). 고르는 칸이 없으므로 고르라는 말은 넣지 않는다. 지원하면 빈 문자열. */
export function unsupportedPartNote(part: PartLike): string {
  const kind = unsupportedKind(part);
  // [왜] 은/는은 괄호 앞 ref를 따른다(D2(LED)는)
  return kind
    ? `이 회로의 ${part.ref}(${kind})${topic(part.ref).slice(part.ref.length)} 아직 교체 검토를 지원하지 않아요.`
    : '';
}
/** 회로 없는 대화에서 회로가 필요한 질문의 서버 답(SPEC 8.9). 이 답이면 화면이 넷리스트 첨부 · 기존 회로 고르기 카드를 붙인다. backend/multi_agent/messages.py NEED_NETLIST와 같은 글자다. */
export const NEEDS_CIRCUIT = '이 질문은 회로가 있어야 검토할 수 있어요. 넷리스트를 첨부해 주세요.';
/** 회로 없이 보낸 첫 질문으로 만드는 프로젝트 이름: 겹친 공백을 한 칸으로 줄인 앞 30자. 비면 "새 대화". */
export function projectNameFromQuestion(question: string) {
  return question.replace(/\s+/g, ' ').trim().slice(0, 30).trim() || '새 대화';
}
/** 고른 파일 이름이 받는 확장자(accept, 쉼표로 나눈 `.net,.kicad_sch` 꼴) 중 하나로 끝나는지. 대소문자 · 앞뒤 공백은 무시한다. 서버도 다시 검사한다. */
export function acceptsFile(name: string, accept: string) {
  const lower = name.trim().toLowerCase();
  return accept.split(',').some((ext) => lower.endsWith(ext));
}
/** KiCad 회로도(`.kicad_sch`)인지(#52). 아니면 넷리스트로 본다. 서버는 회로도를 렌더러로 넷리스트와 그림으로 바꾼다. */
export function isSchematicFile(name: string) {
  return acceptsFile(name, '.kicad_sch');
}
/** 넷리스트 업로드 409의 중복 후보(SPEC 4절 `details.duplicates`, 서버가 최근 순)로 할 일을 정한다(#48). 같은 넷리스트가 있으면 그 프로젝트로 이어 가고, 이름만 겹치면 새로 만든다. */
export function duplicateAction(
  duplicates: { id: number; name: string; matches: string[] }[],
): { action: 'continue'; projectId: number; name: string } | { action: 'create' } {
  const same = duplicates.find((d) => d.matches.includes('netlist'));
  return same ? { action: 'continue', projectId: same.id, name: same.name } : { action: 'create' };
}
/** 부품 점검표의 "이 부품 검토"가 입력창에 미리 써 두는 질문(#68). 보내기는 사용자가 누른다. */
export function reviewQuestion(ref: string) {
  return `${ref}${hasFinal(ref) ? '을' : '를'} 다른 부품으로 바꿔도 될까?`;
}
/** 부품 점검표에 보일 줄: 종류(빈 문자열이면 전체)와 "판정 지원 부품만"으로 거른다(#68). 분류 · 지원 여부는 서버 값이다. */
export function filterParts<T extends { kind: string; judge_supported: boolean }>(
  parts: T[],
  kind: string,
  supportedOnly: boolean,
) {
  return parts.filter((p) => (!kind || p.kind === kind) && (!supportedOnly || p.judge_supported));
}

/** 넷리스트 연결 그림의 배치 결과. 좌표는 SVG 단위(px)다. */
export type CircuitLayout = {
  width: number;
  height: number;
  parts: {
    ref: string;
    value: string;
    x: number;
    y: number;
    w: number;
    h: number;
    focus: boolean;
  }[];
  nets: { name: string; more: number; x: number; y: number; w: number; h: number }[];
  wires: { x: number; y: number }[][];
};
// [왜] 글자 폭을 재지 않고 글자 수로 상자 폭을 정한다(배치는 화면 밖 계산이라 DOM이 없다). 한글 · 영문 평균 폭으로 넉넉히 잡는다
const boxWidth = (texts: string[], px: number) => Math.max(...texts.map((t) => t.length)) * px + 18;
/**
 * 대상 부품의 넷리스트 연결을 dagre로 위 → 아래로 배치한다: 대상 부품, 그 부품의 핀이 붙은 넷, 그 넷에 붙은 이웃 부품.
 * 핀 번호가 가장 작은 핀의 넷은 위, 나머지 넷은 아래에 놓는다. 넷마다 이웃은 perNet개(기본 3)까지 그리고 나머지 수는
 * 넷 이름표에 "+N"으로 적는다(GND처럼 큰 넷이 그림을 덮지 않게). 대상 부품이나 그 넷이 없으면 null.
 */
export function layoutCircuit(
  project: Project | null,
  focus: string,
  perNet = 3,
): CircuitLayout | null {
  const parts = partsOf(project);
  const chosen = ((project?.connections?.nets ?? []) as any[])
    .map((n) => ({
      name: String(n.name ?? n.code ?? ''),
      refs: [...new Set(((n.nodes ?? []) as any[]).map((x) => String(x.ref)))],
    }))
    .filter((n) => n.refs.includes(focus));
  if (!parts.length || !chosen.length) return null;
  const byRef = new Map(parts.map((p) => [p.ref, p]));
  const g = new dagre.graphlib.Graph();
  // [왜] 좁은 회로 패널에 맞게 위 → 아래로 놓는다(층마다 부품이 적어 폭이 좁다)
  g.setGraph({ rankdir: 'TB', nodesep: 10, ranksep: 24, edgesep: 6, marginx: 6, marginy: 6 });
  g.setDefaultEdgeLabel(() => ({}));
  const addPart = (ref: string) => {
    if (g.hasNode('p:' + ref)) return;
    const value = String(byRef.get(ref)?.value ?? '').slice(0, 12);
    g.setNode('p:' + ref, { width: boxWidth([ref, value], 7), height: value ? 38 : 26 });
  };
  addPart(focus);
  // 핀 번호가 가장 작은 핀의 넷을 위에 둔다(넷 목록 순서는 넷리스트마다 달라 번호로 정한다)
  const top = [...pinsOf(project, focus)].sort((a, b) =>
    a.pin.localeCompare(b.pin, undefined, { numeric: true }),
  )[0]?.net;
  const more = new Map<string, number>();
  chosen.forEach((n, i) => {
    const id = 'n:' + i;
    const others = n.refs.filter((r) => r !== focus);
    const keep = others.slice(0, perNet);
    more.set(id, others.length - keep.length);
    const label = n.name + (others.length > keep.length ? ` +${others.length - keep.length}` : '');
    g.setNode(id, { width: boxWidth([label], 6.6), height: 20, name: n.name });
    // [왜] 선의 방향이 층을 정한다. 위 넷은 이웃 → 넷 → 대상, 나머지는 대상 → 넷 → 이웃으로 이어 대상이 가운데 놓인다
    const above = n.name === top;
    if (above) g.setEdge(id, 'p:' + focus);
    else g.setEdge('p:' + focus, id);
    for (const r of keep) {
      addPart(r);
      if (above) g.setEdge('p:' + r, id);
      else g.setEdge(id, 'p:' + r);
    }
  });
  dagre.layout(g);
  const graph = g.graph() as { width?: number; height?: number };
  const out: CircuitLayout = {
    width: graph.width ?? 0,
    height: graph.height ?? 0,
    parts: [],
    nets: [],
    wires: [],
  };
  for (const id of g.nodes()) {
    const node = g.node(id) as any;
    const box = {
      x: node.x - node.width / 2,
      y: node.y - node.height / 2,
      w: node.width,
      h: node.height,
    };
    if (id.startsWith('p:')) {
      const ref = id.slice(2);
      out.parts.push({
        ref,
        value: String(byRef.get(ref)?.value ?? '').slice(0, 12),
        focus: ref === focus,
        ...box,
      });
    } else out.nets.push({ name: node.name, more: more.get(id) ?? 0, ...box });
  }
  for (const e of g.edges())
    out.wires.push(((g.edge(e) as any).points ?? []).map((p: any) => ({ x: p.x, y: p.y })));
  return out;
}
