/** 회로 부품 점검표(#68): 부품마다 종류 · 판정 지원 · 데이터시트 유무를 한 표로 본다. 분류 · 지원 · 코퍼스 대조는 서버(GET /api/projects/{id}/parts)가 정한다. */
import { useState } from 'react';
import { Paperclip } from 'lucide-react';
import { filterParts, reviewQuestion } from './circuit';
import type { PartsCheck } from './types';
import { ErrorBox, Loading, Modal, useResource } from './ui';
export function PartsDialog({
  projectId,
  version,
  close,
  onReview,
  onAttach,
}: {
  projectId: string;
  /** 작업대가 보이는 회로 버전(대화가 고정한 버전). 0이면 회로가 없다 */
  version: number;
  close: () => void;
  /** 질문을 입력창에 써 둔다. 보내지 않는다 */
  onReview: (question: string) => void;
  onAttach: () => void;
}) {
  const check = useResource<PartsCheck>(
    version ? `/projects/${projectId}/parts?circuit_version=${version}` : null,
  );
  const [kind, setKind] = useState(''),
    [supportedOnly, setSupportedOnly] = useState(false);
  const all = check.data?.parts ?? [],
    rows = filterParts(all, kind, supportedOnly);
  return (
    <Modal title="부품 점검표" close={close} wide>
      {!version ? (
        <>
          <p>
            아직 회로가 없어요. 넷리스트(.net)나 회로도(.kicad_sch)를 첨부하면 부품마다 종류 · 판정
            지원 · 데이터시트를 보여 드려요.
          </p>
          <button className="primary" onClick={onAttach}>
            <Paperclip size={15} />
            넷리스트 첨부
          </button>
        </>
      ) : check.loading ? (
        <Loading />
      ) : check.error ? (
        <ErrorBox error={check.error} retry={check.reload} />
      ) : (
        <>
          {/* [왜] 종류별 개수 칩이 곧 종류 거르기다. 순서는 서버가 정한 많은 순 */}
          <div className="kind-chips" role="group" aria-label="종류">
            <button aria-pressed={!kind} onClick={() => setKind('')}>
              전체 {all.length}
            </button>
            {check.data?.counts.map((c) => (
              <button key={c.kind} aria-pressed={kind === c.kind} onClick={() => setKind(c.kind)}>
                {c.name} {c.count}
              </button>
            ))}
          </div>
          <p className="muted">
            판정 지원 {all.filter((p) => p.judge_supported).length}개 · 데이터시트 있음{' '}
            {all.filter((p) => p.datasheet).length}개
          </p>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={supportedOnly}
              onChange={(e) => setSupportedOnly(e.target.checked)}
            />
            판정 지원 부품만
          </label>
          <div className="audit-scroll">
            <table className="audit-table parts-table">
              <thead>
                <tr>
                  <th>기호</th>
                  <th>값</th>
                  <th>종류</th>
                  <th>판정 지원</th>
                  <th>데이터시트</th>
                  <th>풋프린트</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr key={p.ref}>
                    <td>{p.ref}</td>
                    <td>{p.value}</td>
                    <td>{p.kind_name}</td>
                    <td>
                      {p.judge_supported ? (
                        <>
                          지원{' '}
                          <button
                            className="text-button"
                            onClick={() => onReview(reviewQuestion(p.ref))}
                          >
                            이 부품 검토
                          </button>
                        </>
                      ) : (
                        // [왜] 칸 값은 명사로 쓴다. 왜 안 되는지는 종류 칸(LED · 커패시터 …)이 이미 보인다
                        <span className="muted">추후 지원 예정</span>
                      )}
                    </td>
                    <td>
                      {/* #67 데이터시트 서재 화면으로 옮긴다 */}
                      {p.datasheet ? (
                        <a href={`/library?q=${encodeURIComponent(p.datasheet)}`}>{p.datasheet}</a>
                      ) : (
                        <span className="muted">없음</span>
                      )}
                    </td>
                    <td>{p.footprint}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!rows.length && <p className="muted">조건에 맞는 부품이 없습니다.</p>}
        </>
      )}
    </Modal>
  );
}
