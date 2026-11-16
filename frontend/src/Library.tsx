/** 데이터시트 서재(`/library`, #67): 판정 근거로 쓰는 코퍼스 데이터시트를 품번·제목·제조사와 분류로 찾고 원문 PDF로 잇는다. 읽기만 한다. 출처: SPEC 4절. */
import { useEffect, useState } from 'react';
import { ExternalLink, Search } from 'lucide-react';
import { safeLink } from './display';
import {
  libraryQueryString,
  matchedParts,
  readLibraryQuery,
  type LibraryQuery,
} from './libraryQuery';
import { Empty, ErrorBox, Loading, navigate, useResource } from './ui';
import type { DatasheetPage } from './types';
export function Library({ search }: { search: string }) {
  const query = readLibraryQuery(search),
    data = useResource<DatasheetPage>('/datasheets' + libraryQueryString(query)),
    d = data.data,
    [text, setText] = useState(query.q),
    [categories, setCategories] = useState<DatasheetPage['categories']>([]);
  useEffect(() => setText(query.q), [query.q]); // 뒤로 가기·깊은 링크로 주소가 바뀌면 입력칸도 따라간다
  // [왜] 쪽·조건을 바꾸는 동안 응답이 비어도 분류 목록이 사라지지 않게 마지막 목록을 둔다
  useEffect(() => {
    if (d) setCategories(d.categories);
  }, [d]);
  const go = (next: Partial<LibraryQuery>) =>
    navigate('/library' + libraryQueryString({ ...query, page: 1, ...next }));
  const pages = d ? Math.max(1, Math.ceil(d.total / d.page_size)) : 1;
  return (
    <div className="page-content">
      <h1>데이터시트 서재</h1>
      {/* [왜] 서재에 없는 값은 제조사 공식 PDF의 검증한 표 행(2등급)도 판정 근거가 된다(SPEC 3절 근거 등급). "서재만"이라고 쓰지 않는다 */}
      <p className="page-intro">
        판정 근거는 이 서재의 데이터시트를 먼저 씁니다. 서재에 없는 값은 제조사 공식 PDF에서 검증한
        표 행으로 보충할 수 있고, 그 밖의 웹 자료는 판정에 쓰지 않고 미검증 참고로만 보입니다.
      </p>
      <form
        className="library-search"
        role="search"
        onSubmit={(e) => {
          e.preventDefault();
          go({ q: text.trim() });
        }}
      >
        <input
          type="search"
          value={text}
          maxLength={100}
          onChange={(e) => setText(e.target.value)}
          placeholder="품번·시리즈·제조사 (예: SS34)"
          aria-label="품번·시리즈·제조사 검색"
        />
        <select
          value={query.category}
          onChange={(e) => go({ q: text.trim(), category: e.target.value })}
          aria-label="분류"
        >
          <option value="">모든 분류</option>
          {categories.map((c) => (
            <option key={c.category} value={c.category}>
              {c.category} ({c.count})
            </option>
          ))}
        </select>
        <button className="primary" type="submit">
          <Search size={16} />
          검색
        </button>
      </form>
      {data.loading ? (
        <Loading />
      ) : data.error ? (
        <ErrorBox error={data.error} retry={data.reload} />
      ) : !d ? null : d.items.length ? (
        <>
          <p className="muted library-count">
            {query.q || query.category ? '검색 결과' : '전체'} {d.total.toLocaleString('ko-KR')}건 ·{' '}
            {d.page}/{pages}쪽
          </p>
          <div className="audit-scroll" role="region" aria-label="데이터시트 목록" tabIndex={0}>
            <table className="audit-table library-table">
              <thead>
                <tr>
                  <th>품번 시리즈</th>
                  <th>제조사</th>
                  <th>분류</th>
                  <th>판본</th>
                  <th>수집일</th>
                  <th>원문 PDF</th>
                </tr>
              </thead>
              <tbody>
                {d.items.map((item) => {
                  const hits = matchedParts(item.parts, query.q),
                    href = safeLink(item.source_url);
                  return (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.title}</strong>
                        {hits.length > 0 && (
                          <small className="library-hits">
                            {hits.slice(0, 5).join(', ')}
                            {hits.length > 5 && ` 외 ${hits.length - 5}개`} 포함
                          </small>
                        )}
                      </td>
                      <td>{item.publisher}</td>
                      <td>{item.category ?? '-'}</td>
                      <td>{item.revision ?? '-'}</td>
                      <td>{new Date(item.collected_at).toLocaleDateString('ko-KR')}</td>
                      <td>
                        {href ? (
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            aria-label={`${item.title} 원문 PDF (새 탭)`}
                          >
                            <ExternalLink size={14} /> PDF
                          </a>
                        ) : (
                          '-'
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <nav className="library-pager" aria-label="쪽 이동">
              <button
                disabled={d.page <= 1}
                onClick={() => {
                  go({ page: d.page - 1 });
                  scrollTo(0, 0);
                }}
              >
                이전
              </button>
              <span>
                {d.page} / {pages}
              </span>
              <button
                disabled={d.page >= pages}
                onClick={() => {
                  go({ page: d.page + 1 });
                  scrollTo(0, 0);
                }}
              >
                다음
              </button>
            </nav>
          )}
        </>
      ) : d.total ? (
        <Empty title="이 쪽에는 데이터시트가 없습니다.">
          <button className="primary" onClick={() => go({})}>
            첫 쪽으로
          </button>
        </Empty>
      ) : (
        <Empty
          title={
            query.q || query.category
              ? '조건에 맞는 데이터시트가 없습니다.'
              : '서재에 데이터시트가 없습니다.'
          }
        >
          {query.q && <p>품번 전체나 앞부분(예: SS34)이나 시리즈 이름으로 찾아 보세요.</p>}
        </Empty>
      )}
    </div>
  );
}
