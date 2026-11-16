/**
 * 데이터시트 서재(`/library`) 주소의 검색 조건을 읽고 쓰는 순수 함수. 출처: SPEC 4절 `GET /api/datasheets`(#67).
 * [왜] 주소가 화면 상태의 정본이라 깊은 링크(`/library?q=SS34`)와 뒤로 가기가 따로 코드 없이 된다.
 * 같은 쿼리 글을 화면 주소와 API 주소(`/datasheets?…`)에 함께 쓴다.
 */
export type LibraryQuery = { q: string; category: string; page: number };

export function readLibraryQuery(search: string): LibraryQuery {
  const params = new URLSearchParams(search),
    page = Number(params.get('page'));
  return {
    q: (params.get('q') ?? '').trim(),
    category: params.get('category') ?? '',
    page: Number.isInteger(page) && page > 1 ? page : 1,
  };
}

/** 빈 값과 1쪽은 빼서 주소를 짧게 둔다. 조건이 없으면 빈 글. */
export function libraryQueryString({ q, category, page }: LibraryQuery): string {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (category) params.set('category', category);
  if (page > 1) params.set('page', String(page));
  const text = params.toString();
  return text ? '?' + text : '';
}

/** 검색어가 든 표지 품번(서버와 같은 대소문자 무시 부분 일치). 품번으로 찾은 시리즈에 왜 나왔는지 보인다. */
export function matchedParts(parts: string[], q: string): string[] {
  const needle = q.trim().toUpperCase();
  return needle ? parts.filter((part) => part.toUpperCase().includes(needle)) : [];
}

// [왜] 코퍼스 분류는 영어 슬러그(backend/multi_agent/contracts.py Category)다. 화면에는 한국어 이름을 보이고 주소·검색 값은 슬러그 그대로 둔다
const CATEGORY_NAMES: Record<string, string> = {
  'standard-rectifier': '일반 정류 다이오드',
  'schottky-rectifier': '쇼트키 정류 다이오드',
  'schottky-diode': '쇼트키 다이오드',
  'sic-schottky-diode': 'SiC 쇼트키 다이오드',
  'fast-recovery-trr-100-500ns': '고속 회복 다이오드(trr 100~500ns)',
  'high-efficiency-trr-50-99ns': '고효율 다이오드(trr 50~99ns)',
  'super-fast-recovery': '슈퍼패스트 회복 다이오드',
  'ultra-fast-recovery': '울트라패스트 회복 다이오드',
  'switching-diode': '스위칭 다이오드',
  'zener-diode': '제너 다이오드',
  tvs: 'TVS 다이오드(과전압 보호)',
  'esd-protection': 'ESD 보호 다이오드',
  bridge: '브리지 정류기',
};
/** 분류 슬러그의 한국어 이름. 표에 없는 새 분류는 슬러그 그대로 보인다. */
export function categoryName(category: string | null | undefined): string {
  return category ? (CATEGORY_NAMES[category] ?? category) : '-';
}
