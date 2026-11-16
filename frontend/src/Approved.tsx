/** 승인 사례 목록과 사례 하나의 기록(원래 대화·판정·근거·견적). 저장한 값을 보이기만 하고 다시 판정하지 않는다. 출처: SPEC 4절·8.4절. */
import { useState } from 'react';
import { api } from './api';
import { formatAmount, opLabel } from './display';
import {
  Badge,
  Disclaimer,
  Empty,
  ErrorBox,
  Loading,
  Markdown,
  Modal,
  Source,
  useResource,
} from './ui';
import type { ApprovedCaseDetail } from './types';
const RESULTS: Record<string, string> = { pass: '통과', fail: '불충족' };
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
                      {new Date(q.created_at).toLocaleString('ko-KR')} 저장
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
                <button onClick={() => setRemove(c.id)}>사례 삭제</button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="아직 승인한 후보가 없습니다.">
          <p>검토 결과의 후보 상세에서 근거를 확인하고 승인하세요.</p>
          <a href="/app" className="button primary">
            프로젝트로
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
        </Modal>
      )}
    </div>
  );
}
