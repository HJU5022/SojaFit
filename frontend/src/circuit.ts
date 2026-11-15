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
