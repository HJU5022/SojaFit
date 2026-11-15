/** 후보 근거·승인·견적 상세. 숫자를 판정에 사용하지 않는다. 출처: SPEC 3·4·8.4절. */
import { useState } from 'react';
import { ArrowUpRight, Check, ChevronDown, Package, ShoppingCart } from 'lucide-react';
import { api, ApiError } from './api';
import {
  basisLabel,
  explainNames,
  formatAmount,
  opLabel,
  roundLongDecimals,
  safeLink,
} from './display';
import { inputLabel } from './inputLabels';
import {
  Badge,
  Disclaimer,
  ErrorBox,
  Loading,
  Modal,
  Source,
  partsOf,
  pinsOf,
  useResource,
} from './ui';
import type { Approval, Candidate as CandidateType, Project, Result, Role } from './types';
export function PriceLookup({ part }: { part: string }) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState<Error | null>(null),
    [loading, setLoading] = useState(false);
  async function load() {
    setLoading(true);
    setError(null);
    try {
      setData(await api('/prices?parts=' + encodeURIComponent(part.replace(/^TSC\s+/, ''))));
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }
  return (
    <div className="price-lookup">
      <button onClick={load} disabled={loading}>
        <ShoppingCart size={16} />
        {loading ? '조회 중…' : '가격·재고 조회'}
      </button>
      <ErrorBox error={error} retry={load} />
      {data &&
        (data.available ? (
          <div>
            <p>
              {data.source} 실시간 조회 · {new Date(data.fetched_at).toLocaleString('ko-KR')}
            </p>
            {data.parts.length ? (
              data.parts.map((p: any, i: number) => (
                <div key={i}>
                  <strong>{p.part_number}</strong>
                  <p>재고: {p.availability ?? '미제공'}</p>
                  {p.price_breaks.map((b: any, j: number) => (
                    <p key={j}>
                      {b.quantity ?? '—'}개부터 · {b.price ?? '—'} {b.currency}
                    </p>
                  ))}
                  {safeLink(p.product_url) && (
                    <a href={safeLink(p.product_url)} target="_blank" rel="noreferrer">
                      판매처에서 보기 <ArrowUpRight size={14} />
                    </a>
                  )}
                </div>
              ))
            ) : (
              <p>조회된 부품이 없습니다.</p>
            )}
            <small>세금·배송비·환율 미포함 · 저장하지 않음</small>
          </div>
        ) : (
          <p role="status">{data.message}</p>
        ))}
    </div>
  );
}
/** 서버 숫자를 보기 좋게 줄여 보이고, 받은 값 그대로는 마우스를 올리면 보인다. */
function Amount({ value, unit }: { value: any; unit?: string | null }) {
  const shown = formatAmount(value, unit);
  const raw = value == null ? '' : [value].flat().join(' ~ ') + (unit ? ' ' + unit : '');
  return <span title={raw && raw !== shown ? raw : undefined}>{shown}</span>;
}
/** 판정 기준식: 아는 이름은 한국어로 풀고(원문은 마우스 올리면), 모르면 원문을 코드 모양으로 보인다. */
function Basis({ basis }: { basis?: string }) {
  if (!basis) return <>미제공</>;
  const b = basisLabel(basis);
  return b.known ? <span title={basis}>{b.text}</span> : <code>{basis}</code>;
}
function checkLabel(result: string) {
  return (
    (
      {
        pass: '통과',
        fail: '불충족',
        unknown: '확인 안 됨',
        unverified: '확인 안 됨',
        PASS: '통과',
        FAIL: '불충족',
        UNKNOWN: '확인 안 됨',
        NOT_VERIFIED: '확인 안 됨',
      } as Record<string, string>
    )[result] ?? result
  );
}
export function CandidateDetails({
  candidate: c,
  result,
  project,
  target,
  messageId,
  roles,
  close,
}: {
  candidate: CandidateType;
  result: Result;
  project: Project | null;
  target: string;
  messageId: number | null;
  roles: Role[];
  close: () => void;
}) {
  const saved = useResource<Approval[]>(messageId ? `/messages/${messageId}/approvals` : null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [quantity, setQuantity] = useState(100),
    [notice, setNotice] = useState('');
  const approval = saved.data?.find((a) => a.candidate_part === c.part),
    approvable =
      ['IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT'].includes(c.verdict) &&
      result.status === 'completed';
  const part = partsOf(project).find((p) => p.ref === target),
    pins = pinsOf(project, target);
  async function approve() {
    if (!messageId) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/messages/${messageId}/approvals`, 'POST', {
        candidate_part: c.part,
        verdict: c.verdict,
      });
      saved.reload();
      setNotice('후보 승인을 저장했습니다.');
    } catch (e) {
      if (e instanceof ApiError && e.code === 'ALREADY_APPROVED') {
        saved.reload();
        setNotice('이미 승인된 결과입니다. 저장된 승인을 확인합니다.');
      } else setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  async function quote() {
    if (!approval) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/approvals/${approval.id}/quotes`, 'POST', { quantity });
      saved.reload();
      setNotice('견적서를 저장했습니다. 프로젝트의 견적 목록에서 확인할 수 있습니다.');
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="후보 상세" close={close} wide>
      <div className="candidate-heading">
        <h1>{c.part}</h1>
        <Badge verdict={c.verdict} />
        <p>
          <Package size={16} />
          {c.board_change === true
            ? '기판 수정 필요'
            : c.board_change === false
              ? '기판 수정 불필요'
              : '기판 수정 여부 확인 안 됨'}
        </p>
        <Disclaimer />
      </div>
      <section>
        <h2>입력 조건</h2>
        {result.judgement.input_conditions?.length ? (
          <dl className="facts">
            {result.judgement.input_conditions.map((v, i) => (
              <div key={i}>
                <dt>{inputLabel(v.code)}</dt>
                <dd>{v.value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="muted">
            이 결과에는 입력 조건이 제공되지 않았습니다. 대화의 질문과 사용 조건을 확인해 주세요.
          </p>
        )}
      </section>
      <section>
        <h2>조건별 검토</h2>
        <p className="muted">행을 펼치면 판정 근거와 원문 위치가 보입니다.</p>
        <div className="checks-heading">
          <span>조건</span>
          <span>필요 값</span>
          <span>후보 값</span>
          <span>결과</span>
        </div>
        {c.checks.length ? (
          c.checks.map((check, i) => (
            <details className="check-row" key={i}>
              <summary>
                <strong>{check.code}</strong>
                <span>
                  {check.op && <small>{opLabel(check.op)} </small>}
                  <Amount value={check.threshold} unit={check.unit} />
                </span>
                <Amount value={check.value} unit={check.unit} />
                <span className={'check-status ' + check.result.toLowerCase()}>
                  {checkLabel(check.result)}
                  <ChevronDown size={13} />
                </span>
              </summary>
              <div className="check-evidence">
                <dl>
                  <div>
                    <dt>판정 기준</dt>
                    <dd>
                      <Basis basis={check.basis} />
                    </dd>
                  </div>
                  <div>
                    <dt>시험 조건</dt>
                    <dd>{check.condition ? roundLongDecimals(check.condition) : '미제공'}</dd>
                  </div>
                  {check.why && (
                    <div>
                      <dt>설명</dt>
                      <dd>{roundLongDecimals(explainNames(check.why))}</dd>
                    </div>
                  )}
                </dl>
                {check.citation ? (
                  <Source cite={check.citation} />
                ) : (
                  <p>인용 정보가 제공되지 않았습니다.</p>
                )}
              </div>
            </details>
          ))
        ) : (
          <p>조건별 수치 비교가 제공되지 않은 판정입니다.</p>
        )}
      </section>
      {c.cautions.length + c.missing.length + c.uncertain.length > 0 && (
        <section>
          <h2>적용 전에 확인하세요.</h2>
          {[
            ['주의 사항', c.cautions],
            ['문서에 없는 값', c.missing],
            ['불확실한 값', c.uncertain],
          ].map(
            ([label, values]) =>
              (values as string[]).length > 0 && (
                <div className="caution" key={label as string}>
                  <h3>{label as string}</h3>
                  <ul>
                    {(values as string[]).map((v, i) => (
                      <li key={i}>{v}</li>
                    ))}
                  </ul>
                </div>
              ),
          )}
        </section>
      )}
      <section>
        <h2>회로 정보</h2>
        <dl className="facts">
          <div>
            <dt>역할</dt>
            <dd>{roles.find((r) => r.code === c.role)?.name ?? c.role ?? '미제공'}</dd>
          </div>
          <div>
            <dt>선택 부품</dt>
            <dd>
              {target} · {part?.value ?? '미제공'}
            </dd>
          </div>
          <div>
            <dt>풋프린트</dt>
            <dd>{part?.footprint || '미제공'}</dd>
          </div>
          {pins.map((p) => (
            <div key={p.pin}>
              <dt>핀 {p.pin}</dt>
              <dd>{p.net}</dd>
            </div>
          ))}
          <div>
            <dt>회로 구성</dt>
            <dd>
              부품 {partsOf(project).length}개 · 네트{' '}
              {Array.isArray(project?.connections.nets) ? project.connections.nets.length : 0}개
            </dd>
          </div>
        </dl>
        {c.package_citation && <Source cite={c.package_citation} />}
      </section>
      <section>
        <h2>문서 근거</h2>
        {result.evidence.length ? (
          result.evidence.map((cite, i) => <Source cite={cite} key={i} />)
        ) : (
          <p>별도 문서 목록이 없습니다. 조건별 인용을 확인해 주세요.</p>
        )}
      </section>
      <section>
        <h2>가격과 재고</h2>
        <p>데이터시트 판정과 별도로, 요청할 때 조회합니다.</p>
        <PriceLookup part={c.part} />
      </section>
      <section className="approval-section">
        <h2>검토 후 승인</h2>
        <p>회로 조건과 기판 변경을 확인한 사람이 승인합니다.</p>
        <ErrorBox error={saved.error} retry={saved.reload} />
        <ErrorBox error={error} />
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
        {saved.loading ? (
          <Loading />
        ) : approval ? (
          <>
            <p className="approved-mark">
              <Check size={17} /> 승인된 후보
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void quote();
              }}
              className="quote-form"
            >
              <label>
                견적 수량
                <input
                  type="number"
                  min={1}
                  max={100000}
                  value={quantity}
                  onChange={(e) => setQuantity(Number(e.target.value))}
                  required
                />
              </label>
              <button className="primary" disabled={busy}>
                견적서 저장
              </button>
            </form>
            {approval.quotes?.map((q) => (
              <p key={q.id} className="saved-quote">
                {q.part_number} · {q.quantity.toLocaleString()}개 · 저장된 견적
              </p>
            ))}
          </>
        ) : approvable ? (
          <button
            className="primary"
            disabled={busy || !messageId || !!saved.error}
            onClick={approve}
          >
            이 후보 승인하기 <Check size={16} />
          </button>
        ) : (
          <p>이 판정은 승인하거나 견적에 넣을 수 없습니다.</p>
        )}
      </section>
    </Modal>
  );
}
