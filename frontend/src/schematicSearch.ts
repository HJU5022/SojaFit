/**
 * 원본 회로도 웹 검색을 "프로젝트 번호:회로 버전"마다 한 번만 보내는 탭 메모리. 검색 함수는 받아서 부른다(네트워크·DOM 없음).
 * 하지 않는 일: 브라우저 저장소(sessionStorage 등)에 쓰기, 결과 판단. 새로고침하면 비워진다.
 * [왜] 검색 한 번이 유료 외부 검색과 3~20초 렌더를 거친다. 대화를 옮기면 작업대가 다시 그려지는데, 그때 같은 검색을 다시
 * 보내지 않고 진행 중인 검색도 이어받는다. 출처: SPEC 4절(external-circuits).
 */

// [주의] 서버가 서명한 이미지 주소는 15분 뒤 만료되므로 찾은 결과는 14분까지만 쓴다.
export const REUSE_MS = 14 * 60 * 1000;
const searches = new Map<string, { at: number; p: Promise<unknown>; missing: boolean }>();

/** 같은 키의 검색이 진행 중이거나 쓸 수 있으면 그 약속을, 아니면(또는 fresh면) 새로 부른 약속을 돌려준다. */
export function searchOnce<T>(
  key: string,
  run: () => Promise<T>,
  fresh = false,
  now = Date.now(),
): Promise<T> {
  const hit = searches.get(key);
  if (!fresh && hit && (hit.missing || now - hit.at < REUSE_MS)) return hit.p as Promise<T>;
  const entry = { at: now, p: run(), missing: false };
  searches.set(key, entry);
  entry.p.catch((e) => {
    // [왜] 못 찾음(404 SCHEMATIC_NOT_FOUND)은 이미지 주소가 없어 탭이 열려 있는 동안 쓴다.
    // 다른 오류(409·502·503·네트워크)는 바로 다시 시도할 수 있게 버린다.
    if ((e as { code?: string } | null)?.code === 'SCHEMATIC_NOT_FOUND') entry.missing = true;
    else if (searches.get(key) === entry) searches.delete(key);
  });
  return entry.p;
}
