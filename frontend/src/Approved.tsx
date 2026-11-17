/** 승인 사례 목록과 사례 하나의 기록(원래 대화·판정·근거·견적)·인쇄용 보고서. 저장한 값을 보이기만 하고 다시 판정하지 않는다. 출처: SPEC 4절·8.4절. */
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Download, FileText, Printer, Trash2 } from 'lucide-react';
import { api, verdicts } from './api';
import { Amount } from './Candidate';
import { formatAmount, opLabel, pricesPath, safeLink } from './display';
import { ecoFields, quoteFields } from './report';
import {
  Badge,
  Disclaimer,
  Empty,
  ErrorBox,
  GradeHelp,
  Loading,
  Markdown,
  Modal,
  Source,
  useResource,
} from './ui';
import type { ApprovedCaseDetail, Prices, Role, Verdict } from './types';
const RESULTS: Record<string, string> = { pass: '통과', fail: '불충족' };
const reportLink = (id: number) => (
  <a className="button" href={`/approved/${id}/report`}>
    <FileText size={16} />
    보고서
  </a>
);
function CaseDetail({ id, close }: { id: number; close: () => void }) {
  const detail = useResource<ApprovedCaseDetail>(`/approved-cases/${id}`),
    d = detail.data;
  return (
    <Modal title="승인 사례 기록" close={close} wide>
      {detail.loading ? (
        <Loading />
      ) : detail.error ? (
        <ErrorBox error={detail.error} retry={detail.reload} />
      ) : (
        d && (
          <>
            <div className="candidate-heading">
              <h1>{d.candidate_part}</h1>
              <Badge verdict={d.verdict} />
              <p>{new Date(d.created_at).toLocaleString('ko-KR')} 승인</p>
              <Disclaimer />
              {reportLink(d.id)}
            </div>
            <section>
              <h2>원래 대화</h2>
              <dl className="facts">
                <div>
                  <dt>프로젝트</dt>
                  <dd>{d.project_name}</dd>
                </div>
                <div>
                  <dt>대화</dt>
                  <dd>
                    <a href={`/app?project=${d.project_id}&thread=${d.thread_id}`}>
                      {d.thread_title}
                    </a>
                  </dd>
                </div>
                <div>
                  <dt>바꿀 부품</dt>
                  <dd>
                    {d.target_ref
                      ? d.target_ref + (d.target_value ? ` (${d.target_value})` : '')
                      : '기록 없음'}
                  </dd>
                </div>
                <div>
                  <dt>질문</dt>
                  <dd>{d.question || '기록 없음'}</dd>
                </div>
              </dl>
              <p className="muted">
                질문과 따로 적은 사용 조건·조건 답변은 이 기록에 저장되지 않습니다. 원래 대화에서
                확인하세요.
              </p>
            </section>
            <section>
              <h2>조건별 판정</h2>
              {d.candidate?.checks.length ? (
                <>
                  <div className="checks-heading">
                    <span>조건</span>
                    <span>필요 값</span>
                    <span>후보 값</span>
                    <span>결과</span>
                  </div>
                  {d.candidate.checks.map((check, i) => (
                    <details className="check-row" key={i}>
                      <summary>
                        <strong>{check.code}</strong>
                        <span>
                          {check.op && <small>{opLabel(check.op)} </small>}
                          {formatAmount(check.threshold, check.unit)}
                        </span>
                        <span>{formatAmount(check.value, check.unit)}</span>
                        <span className={'check-status ' + check.result.toLowerCase()}>
                          {RESULTS[check.result.toLowerCase()] ?? '확인 안 됨'}
                        </span>
                      </summary>
                      <div className="check-evidence">
                        {check.citation ? (
                          <Source cite={check.citation} />
                        ) : (
                          <p className="muted">이 조건의 인용 위치가 저장되지 않았습니다.</p>
                        )}
                      </div>
                    </details>
                  ))}
                </>
              ) : (
                <p className="muted">저장된 조건별 판정이 없습니다.</p>
              )}
            </section>
            <section>
              <h2>근거 문서</h2>
              {d.evidence.length > 0 && <GradeHelp />}
              {d.evidence.length ? (
                d.evidence.map((cite, i) => <Source key={i} cite={cite} />)
              ) : (
                <p className="muted">저장된 근거 위치가 없습니다.</p>
              )}
            </section>
            {d.answer && (
              <section>
                <h2>승인 때의 답</h2>
                <Markdown>{d.answer}</Markdown>
              </section>
            )}
            <section>
              <h2>견적</h2>
              {d.quotes.length ? (
                <ul className="case-quotes">
                  {d.quotes.map((q) => (
                    <li key={q.id}>
                      {q.part_number} · {q.quantity}개 ·{' '}
                      {new Date(q.created_at).toLocaleString('ko-KR')} 저장 ·{' '}
                      <a href={`/approved/${id}/quote/${q.id}`} target="_blank" rel="noreferrer">
                        견적서 보기
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">이 승인으로 저장한 견적이 없습니다.</p>
              )}
            </section>
          </>
        )
      )}
    </Modal>
  );
}
export function ApprovedCases() {
  const data = useResource<any[]>('/approved-cases'),
    [error, setError] = useState<Error | null>(null),
    [remove, setRemove] = useState<number | null>(null),
    [open, setOpen] = useState<number | null>(null);
  return (
    <div className="page-content">
      <h1>승인 사례</h1>
      <p className="page-intro">
        사람이 확인하고 승인한 후보의 기록입니다. 눌러서 그때의 판정·근거·견적과 원래 대화를 볼 수
        있습니다. 새 검토의 판정 근거로 재사용하지 않습니다.
      </p>
      <ErrorBox error={error} />
      {data.loading ? (
        <Loading />
      ) : data.error ? (
        <ErrorBox error={data.error} retry={data.reload} />
      ) : data.data?.length ? (
        <div className="case-list">
          {data.data.map((c) => (
            <article key={c.id}>
              <div>
                <h2>{c.candidate_part}</h2>
                <Badge verdict={c.verdict} />
                <p>{new Date(c.created_at).toLocaleString('ko-KR')} 승인</p>
                <Disclaimer />
              </div>
              <div className="case-actions">
                <button className="primary" onClick={() => setOpen(c.id)}>
                  기록 보기
                </button>
                {reportLink(c.id)}
                <button
                  className="icon-button"
                  aria-label="사례 삭제"
                  title="사례 삭제"
                  onClick={() => setRemove(c.id)}
                >
                  <Trash2 size={17} />
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="아직 승인한 후보가 없습니다.">
          <p>검토 결과의 후보 상세에서 근거를 확인하고 승인하세요.</p>
          <a href="/app" className="button primary">
            새 대화로
          </a>
        </Empty>
      )}
      {open !== null && <CaseDetail id={open} close={() => setOpen(null)} />}
      {remove !== null && (
        <Modal title="승인 사례를 삭제할까요?" close={() => setRemove(null)}>
          <p>
            승인을 취소하고 사례를 삭제합니다. 기존 견적은 이력으로 남고, 같은 검토에서 후보를 다시
            승인할 수 있습니다.
          </p>
          <div className="dialog-actions">
            <button onClick={() => setRemove(null)}>취소</button>
            <button
              className="primary"
              onClick={async () => {
                try {
                  await api('/approved-cases/' + remove, 'DELETE');
                  setRemove(null);
                  data.reload();
                } catch (e) {
                  setError(e as Error);
                  setRemove(null);
                }
              }}
            >
              사례 삭제
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
// 승인할 수 있는 판정 3종의 뜻(SPEC 3절 표). 역할상 충분은 원래 부품 데이터시트가 없어도 나오므로 "못 미침"으로 단정하지 않는다
const MEANINGS: Partial<Record<Verdict, string>> = {
  IDENTICAL:
    '같은 품번이거나 주문 코드만 다른 품번, 또는 제조사가 같은 제품이라고 밝힌 품번입니다.',
  SPEC_EQUIVALENT: '품번은 다르지만 원래 부품의 주요 정격을 모두 같거나 넘습니다.',
  ROLE_SUFFICIENT:
    '회로 역할의 필수 조건은 모두 만족하지만, 원래 부품의 주요 정격을 모두 같거나 넘는다고는 확인하지 못했습니다.',
};
/** 승인 사례 하나의 인쇄용 부품 대체 검토 보고서(`/approved/{id}/report`, 사이드바 없이 A4 1~2쪽). 위는 ECO 양식(#56), 아래는 기술 검토 근거. 저장한 값만 옮긴다(#44). */
export function CaseReport({ id, email }: { id: number; email: string }) {
  const detail = useResource<ApprovedCaseDetail>(`/approved-cases/${id}`),
    roles = useResource<Role[]>('/judge/roles'),
    d = detail.data;
  useEffect(() => {
    // [왜] 브라우저의 "PDF로 저장"은 문서 제목을 기본 파일 이름으로 쓴다
    const before = document.title;
    document.title = `부품 대체 검토 보고서 SF-${id}`;
    return () => {
      document.title = before;
    };
  }, [id]);
  return (
    <div className="report-page">
      <div className="report-actions">
        <a className="button" href="/approved">
          <ArrowLeft size={16} />
          돌아가기
        </a>
        <button className="primary" onClick={() => window.print()} disabled={!d}>
          <Printer size={16} />
          인쇄 / PDF로 저장
        </button>
      </div>
      {detail.loading ? (
        <Loading />
      ) : detail.error ? (
        <ErrorBox error={detail.error} retry={detail.reload} />
      ) : (
        d && <ReportBody d={d} roles={roles.data} email={email} />
      )}
    </div>
  );
}
/** 저장한 견적 하나의 견적서 문서(A4 한 장)와 PDF 다운로드. 가격·재고는 열 때 한 번 조회해 보이기만 하고 저장하지 않는다(SPEC 8.4, ADR 0009). */
export function CaseQuote({
  caseId,
  quoteId,
  email,
}: {
  caseId: number;
  quoteId: number;
  email: string;
}) {
  const detail = useResource<ApprovedCaseDetail>(`/approved-cases/${caseId}`),
    d = detail.data,
    quote = d?.quotes.find((q) => q.id === quoteId),
    prices = useResource<Prices>(quote ? pricesPath(quote.part_number, quote.quantity) : null),
    sheet = useRef<HTMLElement>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const f = d && quote ? quoteFields(d, quote, prices.data) : null;
  async function download() {
    if (!sheet.current || !f) return;
    setBusy(true);
    setError(null);
    try {
      // [왜] PDF 라이브러리는 크기가 커서 단추를 누를 때만 불러온다
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import('html2canvas'),
        import('jspdf'),
      ]);
      const canvas = await html2canvas(sheet.current, { scale: 2, backgroundColor: '#ffffff' });
      const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: true });
      // [왜] A4(210×297mm)에 여백 10mm를 두고, 문서가 길어도 한 쪽에 들어오게 비율을 지켜 줄인다
      const k = Math.min(190 / canvas.width, 277 / canvas.height);
      // [왜] 압축 없이 넣으면 한 장이 6MB를 넘는다. FAST 압축으로 수백 kB로 줄인다
      pdf.addImage(
        canvas.toDataURL('image/png'),
        'PNG',
        10,
        10,
        canvas.width * k,
        canvas.height * k,
        undefined,
        'FAST',
      );
      pdf.save(f.file);
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  const checks = d?.candidate?.checks ?? [],
    passed = checks.filter((check) => check.result.toLowerCase() === 'pass').length,
    // [왜] 조회는 됐는데 못 쓴 이유(quoteFields)와 조회 요청 자체가 실패한 경우를 한 줄로 알린다
    reason = f?.unavailable ?? (prices.error ? '가격·재고를 조회하지 못했습니다.' : null),
    money = (value: string | undefined) =>
      f?.estimate && value
        ? `${value} ${f.estimate.currency}`
        : prices.loading
          ? '조회 중'
          : '조회 불가';
  return (
    <div className="report-page">
      <div className="report-actions">
        <a className="button" href="/approved">
          <ArrowLeft size={16} />
          돌아가기
        </a>
        <button className="primary" onClick={download} disabled={!f || prices.loading || busy}>
          <Download size={16} />
          {busy ? 'PDF 만드는 중…' : 'PDF 다운로드'}
        </button>
      </div>
      <ErrorBox error={error} />
      {detail.loading ? (
        <Loading />
      ) : detail.error ? (
        <ErrorBox error={detail.error} retry={detail.reload} />
      ) : !d || !quote || !f ? (
        <Empty title="견적을 찾지 못했습니다">
          <p>승인 사례에서 저장한 견적을 다시 확인해 주세요.</p>
        </Empty>
      ) : (
        <article className="report quote-sheet" ref={sheet}>
          <header>
            <h1>견적서</h1>
            <dl className="report-facts">
              {[
                ['견적 번호', f.number],
                ['작성일', new Date(quote.created_at).toLocaleDateString('ko-KR')],
                ['프로젝트(회로)', d.project_name],
                ['요청자', email],
                ['서비스', 'SojaFit'],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          </header>
          <section>
            <h2>품목</h2>
            <div className="report-table">
              <table className="quote-items">
                <thead>
                  <tr>
                    <th>기호</th>
                    <th>원래 품번</th>
                    <th>대체 품번</th>
                    <th>제조사</th>
                    <th>수량</th>
                    <th>적용 구간</th>
                    <th>단가</th>
                    <th>금액</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{f.ref ?? '—'}</td>
                    <td>{f.original ?? '—'}</td>
                    <td>
                      <strong>{f.part}</strong>
                    </td>
                    <td>{f.manufacturer ?? '—'}</td>
                    <td>{f.quantity.toLocaleString()}개</td>
                    <td>
                      {f.estimate ? `${f.estimate.break_quantity.toLocaleString()}개부터` : '—'}
                    </td>
                    <td>{money(f.estimate?.unit_price)}</td>
                    <td>{money(f.estimate?.total)}</td>
                  </tr>
                </tbody>
                <tfoot>
                  <tr>
                    <th colSpan={7}>합계</th>
                    <td>{money(f.estimate?.total)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            {reason && <p role="status">가격 조회 불가: {reason}</p>}
          </section>
          <section>
            <h2>가격·재고 출처</h2>
            {f.source && f.fetchedAt ? (
              <>
                <p>
                  {f.source} 실시간 조회 · {new Date(f.fetchedAt).toLocaleString('ko-KR')}
                </p>
                <p>재고: {f.availability ?? '미제공'}</p>
                {safeLink(f.url) && <p className="quote-url">판매처: {safeLink(f.url)}</p>}
              </>
            ) : (
              <p>
                {prices.loading ? '가격·재고를 조회하는 중입니다.' : '조회한 가격·재고가 없습니다.'}
              </p>
            )}
            <p>
              세금·배송비·환율은 들어 있지 않습니다. 가격·재고는 조회한 시점의 값이며 SojaFit은
              저장하지 않습니다. 주문 전에 판매처에서 다시 확인해 주세요.
            </p>
          </section>
          <section>
            <h2>검토 근거</h2>
            <p>
              <Badge verdict={d.verdict} />{' '}
              {checks.length ? `조건 ${checks.length}개 중 ${passed}개 통과` : null}
            </p>
            {/* [왜] 같은 표를 조건마다 인용하면 같은 줄이 겹친다. 문서 · 쪽 · 표가 같은 근거는 한 번만 적는다 */}
            {[
              ...new Set(
                d.evidence.map(
                  (e) =>
                    e.document +
                    (e.page != null ? ` ${e.page}쪽` : '') +
                    (e.table ? `, ${e.table}` : ''),
                ),
              ),
            ]
              .slice(0, 3)
              .map((line) => (
                <p key={line}>근거 문서: {line}</p>
              ))}
            <p>조건별 비교는 부품 대체 검토 보고서 SF-{d.id}에 있습니다.</p>
          </section>
          <section>
            <h2>승인</h2>
            <dl className="report-facts">
              <div>
                <dt>승인 시각</dt>
                <dd>{new Date(d.created_at).toLocaleString('ko-KR')}</dd>
              </div>
              <div>
                <dt>승인자</dt>
                <dd>{email}</dd>
              </div>
            </dl>
          </section>
          <Disclaimer />
        </article>
      )}
    </div>
  );
}
/** 보고서 본문: 불러온 사례 값만 그린다. ECO 칸 값은 `report.ts` `ecoFields`가 만든다. */
export function ReportBody({
  d,
  roles,
  email,
}: {
  d: ApprovedCaseDetail;
  roles: Role[] | null;
  email: string;
}) {
  const c = d.candidate,
    role = c?.role ? `${c.role} ${roles?.find((r) => r.code === c.role)?.name ?? ''}`.trim() : null,
    eco = ecoFields(d, role, verdicts[d.verdict]);
  // [왜] 값이 null이면 손으로 적는 빈칸(.report-blank)으로 둔다. 없는 값을 지어 넣지 않는다(#56)
  const facts = (rows: [string, React.ReactNode][]) => (
    <dl className="report-facts">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd className={v == null ? 'report-blank' : undefined}>{v}</dd>
        </div>
      ))}
    </dl>
  );
  return (
    <article className="report">
      {/* [왜] 위 ECO 양식은 Arena Solutions 공개 ECO 서식 1쪽 칸을 본뜬다(https://www.arenasolutions.com/wp-content/uploads/arena-eco-template.pdf). 저장 값이 없는 칸은 빈칸(#56) */}
      <header>
        <h1>부품 대체 검토 보고서</h1>
        {facts([
          ['ECO 번호', `SF-${d.id}`],
          ['변경 요청(ECR) 번호', null],
          ['제품(회로)', d.project_name],
          ['우선순위', null],
          ['요청자', null],
          ['제출일', new Date().toLocaleDateString('ko-KR')],
          ['서비스', 'SojaFit'],
        ])}
      </header>
      <section>
        <h2>변경 내용</h2>
        {eco.change ? <p>{eco.change}</p> : <div className="report-blank" />}
      </section>
      <section>
        <h2>변경 사유</h2>
        <div className="report-blank" />
      </section>
      <section>
        <h2>변경 영향</h2>
        <p>{eco.impact}</p>
        <div className="report-blank" />
      </section>
      <section>
        <h2>영향받는 품목</h2>
        {/* [왜] Arena의 수명 주기 단계(이전·새) 열은 저장 값이 없고 A4 세로 폭을 넘겨 뺀다 */}
        <div className="report-table">
          <table className="report-items">
            <thead>
              <tr>
                <th scope="col">기호</th>
                <th scope="col">설명</th>
                <th scope="col">이전 품번</th>
                <th scope="col">새 품번</th>
                <th scope="col">회로 판(이전 → 새)</th>
                <th scope="col">적용 날짜</th>
                <th scope="col">재고 상태</th>
                <th scope="col">재고 처리</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                {eco.row.map((v, i) => (
                  <td key={i}>{v}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
        {/* [왜] 체크 칸 입력(input)은 전역 입력 스타일로 크게 그려지고 열 폭을 넘겨, 인쇄에서 작은 상자로 나오는 글자 ☐로 쓴다 */}
        <p>영향 범위: ☐ BOM ☐ 사양 ☐ 파일 ☐ 원가 ☐ 구매</p>
      </section>
      <h2 className="report-part">기술 검토 근거</h2>
      <section>
        <h2>1. 검토 대상</h2>
        {facts([
          ['프로젝트(회로)', d.project_name],
          [
            '회로 버전',
            d.circuit_version
              ? `v${d.circuit_version}`
              : d.circuit_version === 0
                ? '회로 없음'
                : '기록 없음',
          ],
          [
            '바꿀 부품',
            d.target_ref
              ? d.target_ref + (d.target_value ? ` · 원래 품번 ${d.target_value}` : '')
              : '기록 없음',
          ],
          ['회로 역할', role ?? '기록 없음'],
        ])}
      </section>
      <section>
        <h2>2. 대체 후보와 판정</h2>
        {facts([
          ['후보 품번', d.candidate_part],
          ['판정', <Badge verdict={d.verdict} />],
        ])}
        <p>{MEANINGS[d.verdict]}</p>
      </section>
      <section>
        <h2>3. 조건별 비교</h2>
        {c?.checks.length ? (
          <div className="report-table">
            <table>
              <thead>
                <tr>
                  <th scope="col">조건</th>
                  <th scope="col">필요 값</th>
                  <th scope="col">후보 값</th>
                  <th scope="col">결과</th>
                </tr>
              </thead>
              <tbody>
                {c.checks.map((check, i) => (
                  <tr key={i}>
                    <th scope="row">{check.code}</th>
                    {/* [왜] 화면의 후보 상세와 같은 표기: 긴 소수는 줄이고 받은 값은 title에 둔다(#44) */}
                    <td>
                      {check.op && opLabel(check.op) + ' '}
                      <Amount value={check.threshold} unit={check.unit} />
                    </td>
                    <td>
                      <Amount value={check.value} unit={check.unit} />
                    </td>
                    <td>{RESULTS[check.result.toLowerCase()] ?? '확인 안 됨'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">저장된 조건별 판정이 없습니다.</p>
        )}
      </section>
      <section>
        <h2>4. 근거 (데이터시트 인용)</h2>
        {d.evidence.length ? (
          <ol className="report-sources">
            {d.evidence.map((cite, i) => (
              <li key={i}>
                {[
                  cite.document || '문서명 미제공',
                  cite.page != null ? `${cite.page}쪽` : null,
                  cite.table,
                  cite.row,
                  cite.section,
                ]
                  .filter(Boolean)
                  .join(' · ')}
                {safeLink(cite.source_url) && (
                  <a href={safeLink(cite.source_url)} target="_blank" rel="noreferrer">
                    {safeLink(cite.source_url)}
                  </a>
                )}
              </li>
            ))}
          </ol>
        ) : (
          <p className="muted">저장된 근거 위치가 없습니다.</p>
        )}
      </section>
      <section>
        <h2>5. 검토 질문</h2>
        <p className="report-quote">{d.question || '기록 없음'}</p>
        <p className="muted">
          질문과 따로 적은 사용 조건·조건 답변은 이 기록에 저장되지 않습니다. 원래 대화에서
          확인하세요.
        </p>
      </section>
      <section>
        <h2>6. 승인</h2>
        {facts([
          ['승인 일시', new Date(d.created_at).toLocaleString('ko-KR')],
          // [왜] 사례는 주인만 열 수 있어(서버 404) 보고 있는 계정이 곧 승인한 계정이다
          ['승인 계정', email],
          [
            '견적',
            d.quotes.length
              ? d.quotes
                  .map(
                    (q) =>
                      `${q.part_number} · ${q.quantity}개 · ${new Date(q.created_at).toLocaleString('ko-KR')}`,
                  )
                  .join(' / ')
              : '저장한 견적 없음',
          ],
        ])}
      </section>
      <section>
        <h2>7. 한계와 확인 사항</h2>
        <ul>
          <li>판정은 데이터시트 값과 회로 조건의 비교이며 같은 동작은 보장하지 않습니다.</li>
          <li>실제 적용 전 사용 조건과 패키지·기판 변경을 확인해야 합니다.</li>
          <li>
            검토 답변은 생성형 AI를 이용해 작성되었으며 수치 비교와 판정은 코드가 수행했습니다.
          </li>
        </ul>
      </section>
      <div className="report-table report-sign">
        <table>
          <caption>확인 서명</caption>
          <thead>
            <tr>
              <td />
              <th scope="col">작성</th>
              <th scope="col">검토</th>
              <th scope="col">승인</th>
            </tr>
          </thead>
          <tbody>
            {/* [왜] ECO의 변경 심의(CCB) 승인자 칸: 같은 서명 칸에 부서 줄만 더한다(#56) */}
            {['부서', '이름', '서명', '날짜'].map((k) => (
              <tr key={k} className={k === '서명' ? 'report-sign-line' : undefined}>
                <th scope="row">{k}</th>
                <td />
                <td />
                <td />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}
