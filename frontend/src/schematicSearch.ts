/**
 * 원본 회로도 웹 검색을 "프로젝트 번호:회로 버전"마다 한 번만 보내는 탭 메모리. 검색 함수는 받아서 부른다(네트워크·DOM 없음).
 * 하지 않는 일: 브라우저 저장소(sessionStorage 등)에 쓰기, 결과 판단. 새로고침하면 비워진다.
 * [왜] 검색 한 번이 유료 외부 검색과 3~20초 렌더를 거친다. 대화를 옮기면 작업대가 다시 그려지는데, 그때 같은 검색을 다시
 * 보내지 않고 진행 중인 검색도 이어받는다. 출처: SPEC 4절(external-circuits).
 */

// [주의] 서버가 서명한 이미지 주소는 15분 뒤 만료되므로 찾은 결과는 14분까지만 쓴다.
export const REUSE_MS = 14 * 60 * 1000;
type Entry = { at: number; p: Promise<unknown>; ok: boolean; failed: boolean };
const searches = new Map<string, Entry>();

/**
 * 같은 키의 검색이 진행 중이거나 쓸 수 있으면 그 약속을, 아니면 새로 부른 약속을 돌려준다.
 * fresh는 사용자가 직접 누른 검색(다시 시도·다른 이름으로 찾기·다른 후보)이다. 자동으로 여는 쪽은 fresh를 넘기지 않는다.
 */
export function searchOnce<T>(
  key: string,
  run: () => Promise<T>,
  fresh = false,
  now = Date.now(),
): Promise<T> {
  const hit = searches.get(key);
  // [왜] 실패(못 찾음·409·502·503·네트워크)는 사용자가 다시 찾을 때까지 남겨 둔다. 지우면 대화를 옮길 때마다 유료 검색이 다시 나간다.
  if (!fresh && hit && (hit.failed || now - hit.at < REUSE_MS)) return hit.p as Promise<T>;
  const entry: Entry = { at: now, p: run(), ok: false, failed: false };
  searches.set(key, entry);
  entry.p.then(
    () => {
      entry.ok = true;
    },
    () => {
      entry.failed = true;
      // [왜] 직접 찾은 이름·후보가 실패해도 앞서 찾은 도면은 지우지 않고 다음에 열 때 그대로 보인다.
      if (hit?.ok && searches.get(key) === entry) searches.set(key, hit);
    },
  );
  return entry.p as Promise<T>;
}
