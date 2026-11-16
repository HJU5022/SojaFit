/** 설정·승인 사례·관리자·개인정보 안내. 출처: SPEC 8.5·8.6절. */
import { useEffect, useState } from 'react';
import { api } from './api';
import {
  Badge,
  Brand,
  Disclaimer,
  Empty,
  ErrorBox,
  Loading,
  Modal,
  plainClick,
  useResource,
} from './ui';
import type { Fact, User } from './types';
// [왜] 직무는 #24 전까지 이 코드 중에서 골랐다. 그때 저장한 값은 글 칸에 화면 이름으로 보인다(서버도 같은 코드를 이 이름으로 받음)
const oldJobRoles: Record<string, string> = {
  design: '설계',
  purchasing: '구매',
  student: '학생',
  other: '기타',
};
export function Settings({ user, onLogout }: { user: User; onLogout: () => void }) {
  const memory = useResource<Fact[]>('/me/memory');
  const [values, setValues] = useState<Record<string, string>>({}),
    [error, setError] = useState<Error | null>(null),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(''),
    [deleting, setDeleting] = useState(false);
  useEffect(() => {
    if (memory.data)
      setValues(
        Object.fromEntries(
          memory.data.map((f) => [
            f.kind,
            f.kind === 'job_role' ? (oldJobRoles[f.value] ?? f.value) : f.value,
          ]),
        ),
      );
  }, [memory.data]);
  async function save() {
    setBusy(true);
    setError(null);
    setNotice('');
    try {
      const body = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()));
      // [왜] PATCH에서 빠진 칸은 유지되므로, 사용자가 비운 기존 기억은 DELETE로 지운다.
      for (const fact of memory.data ?? [])
        if (!values[fact.kind]?.trim()) await api('/me/memory?kind=' + fact.kind, 'DELETE');
      if (Object.keys(body).length) await api('/me/memory', 'PATCH', body);
      memory.reload();
      setNotice('내 설정을 저장했습니다.');
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  async function remove(kind?: string) {
    setError(null);
    setBusy(true);
    try {
      await api('/me/memory' + (kind ? '?kind=' + kind : ''), 'DELETE');
      memory.reload();
      setNotice('기억을 삭제했습니다.');
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="page-content settings">
      <h1>내 설정</h1>
      <p className="page-intro">
        여기에 입력한 정보는 계정에 기억되어 새 대화에서도 유지됩니다. 대화 내용에서 자동으로
        기억하지 않으며, 이 화면에서 직접 입력한 것만 기억합니다.
      </p>
      <ErrorBox error={error} />
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <section className="settings-row">
        <div>
          {/* [주의] 문구는 SPEC 8.5(기억 칸·에이전트 활용·기억이 아닌 것)와 맞춘다(#25) */}
          <h2>기억해 두는 정보</h2>
          <p>
            <strong>선호 실장 방식</strong>: 질문에 실장 방식이 없을 때, 같은 판정을 받은 후보
            가운데 이 방식의 패키지가 있는 후보를 먼저 보여 줍니다. 판정 결과는 바뀌지 않으며,
            질문에 실장 방식을 적으면 질문을 따릅니다. 후보가 많으면 보이는 후보가 달라질 수
            있습니다.
          </p>
          <p>
            <strong>소속·직무</strong>: 기억만 하고, 판정이나 답변을 만드는 데에는 쓰지 않습니다.
          </p>
          <p>
            <strong>기억하지 않는 것</strong>: 전압·전류 같은 회로 값은 회로마다 다르므로 검토할
            때마다 그 회로에서 다시 확인합니다. 승인한 후보는 승인 사례에, 주문 수량은 견적에 따로
            저장됩니다.
          </p>
          <p>
            기억은 기한 없이 보관되며, 칸별로 또는 한 번에 모두 지울 수 있습니다. 지운 내용은 다음
            질문부터 반영됩니다.
          </p>
        </div>
        <div className="settings-panel">
          {memory.loading ? (
            <Loading />
          ) : memory.error ? (
            <ErrorBox error={memory.error} retry={memory.reload} />
          ) : (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void save();
              }}
            >
              <label>
                소속
                <input
                  maxLength={100}
                  value={values.affiliation ?? ''}
                  onChange={(e) => setValues({ ...values, affiliation: e.target.value })}
                  placeholder="소속을 입력하세요"
                />
              </label>
              {memory.data?.some((f) => f.kind === 'affiliation') && (
                <button type="button" className="text-button" onClick={() => remove('affiliation')}>
                  소속 기억 삭제
                </button>
              )}
              <label>
                직무
                <input
                  maxLength={100}
                  value={values.job_role ?? ''}
                  onChange={(e) => setValues({ ...values, job_role: e.target.value })}
                  placeholder="예: 하드웨어 회로 설계, 부품 구매, 생산 기술"
                />
              </label>
              {memory.data?.some((f) => f.kind === 'job_role') && (
                <button type="button" className="text-button" onClick={() => remove('job_role')}>
                  직무 기억 삭제
                </button>
              )}
              <label>
                선호 실장 방식
                <select
                  aria-label="선호 실장 방식"
                  value={values.mounting_preference ?? ''}
                  onChange={(e) => setValues({ ...values, mounting_preference: e.target.value })}
                >
                  <option value="">선택 안 함</option>
                  <option value="smd">SMD</option>
                  <option value="through_hole">스루홀</option>
                  <option value="any">상관없음</option>
                </select>
              </label>
              {memory.data?.some((f) => f.kind === 'mounting_preference') && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => remove('mounting_preference')}
                >
                  실장 방식 기억 삭제
                </button>
              )}
              <div className="actions">
                <button className="primary" disabled={busy}>
                  설정 저장
                </button>
                <button
                  type="button"
                  disabled={busy || !memory.data?.length}
                  onClick={() => remove()}
                >
                  기억 모두 삭제
                </button>
              </div>
              {memory.data?.length === 0 && <p className="muted">저장된 기억이 없습니다.</p>}
            </form>
          )}
        </div>
      </section>
      <section className="settings-row">
        <div>
          <h2>계정</h2>
          <p>{user.email}</p>
        </div>
        <div className="settings-panel">
          <button onClick={() => setDeleting(true)} disabled={user.role === 'admin'}>
            계정 탈퇴
          </button>
          <p>탈퇴하면 프로젝트, 대화, 승인, 견적과 기억이 삭제됩니다.</p>
          {user.role === 'admin' && <p>관리자 계정은 이 화면에서 탈퇴할 수 없습니다.</p>}
        </div>
      </section>
      {deleting && (
        <Modal title="계정을 삭제할까요?" close={() => setDeleting(false)}>
          <p>내 프로젝트와 모든 기록이 삭제됩니다. 복구할 수 없습니다.</p>
          <ErrorBox error={error} />
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api('/me', 'DELETE');
                onLogout();
              } catch (e) {
                setError(e as Error);
              } finally {
                setBusy(false);
              }
            }}
          >
            모든 기록과 계정 삭제
          </button>
        </Modal>
      )}
    </div>
  );
}
export function ApprovedCases() {
  const data = useResource<any[]>('/approved-cases'),
    [error, setError] = useState<Error | null>(null),
    [remove, setRemove] = useState<number | null>(null);
  return (
    <div className="page-content">
      <h1>승인 사례</h1>
      <p className="page-intro">
        사람이 확인하고 승인한 후보입니다. 새 검토의 판정 근거로 재사용하지 않습니다.
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
              <button onClick={() => setRemove(c.id)}>사례 삭제</button>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="아직 승인한 후보가 없습니다.">
          <p>검토 결과의 후보 상세에서 근거를 확인하고 승인하세요.</p>
          <a href="/projects" className="button primary">
            프로젝트로
          </a>
        </Empty>
      )}
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
export function Admin() {
  const users = useResource<{ users: any[] }>('/admin/users'),
    [error, setError] = useState<Error | null>(null),
    [busy, setBusy] = useState(false);
  return (
    <div className="page-content">
      <h1>사용자 관리</h1>
      <p className="page-intro">계정을 비활성화하면 기존 세션도 종료됩니다.</p>
      <ErrorBox error={error} />
      {users.loading ? (
        <Loading />
      ) : users.error ? (
        <ErrorBox error={users.error} retry={users.reload} />
      ) : users.data?.users.length ? (
        <div className="case-list">
          {users.data.users.map((u) => (
            <article key={u.id}>
              <div>
                <h2>{u.email}</h2>
                <p>
                  {u.role === 'admin' ? '관리자' : '일반 사용자'} ·{' '}
                  {u.is_active ? '활성' : '비활성'}
                </p>
              </div>
              <button
                disabled={u.role === 'admin' || busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api(`/admin/users/${u.id}`, 'PATCH', { is_active: !u.is_active });
                    users.reload();
                  } catch (e) {
                    setError(e as Error);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {u.is_active ? '비활성화' : '활성화'}
              </button>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="사용자 목록이 없습니다." />
      )}
    </div>
  );
}
/** `/privacy` 주소로 바로 들어왔을 때의 페이지. 화면 안에서는 아래 PrivacyLink가 같은 본문을 작은 창으로 연다(#20). */
export function Privacy() {
  return (
    <div className="privacy-page">
      <Brand />
      <main>
        <h1>개인정보 처리 안내</h1>
        <PrivacyText />
      </main>
    </div>
  );
}
/** 화면 아래쪽의 조용한 "개인정보 처리방침" 링크. 보통 클릭은 작은 창으로 열고, 새 탭으로 열면 `/privacy` 페이지가 된다(#20). */
export function PrivacyLink({ className }: { className?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <a
        className={className}
        href="/privacy"
        onClick={(e) => {
          if (!plainClick(e)) return;
          e.preventDefault(); // [주의] 문서 전체 링크 위임(followLink)이 이 클릭을 페이지 이동으로 바꾸지 않게 한다
          setOpen(true);
        }}
      >
        개인정보 처리방침
      </a>
      {open && (
        <Modal title="개인정보 처리 안내" close={() => setOpen(false)}>
          <PrivacyText />
        </Modal>
      )}
    </>
  );
}
function PrivacyText() {
  return (
    <div className="privacy-text">
      <p>SojaFit의 현재 명세에 따른 데이터 처리 안내입니다.</p>
      <h2>계정과 검토 기록</h2>
      <p>
        이메일과 인증 정보를 계정 관리에 사용합니다. 프로젝트의 회로 연결, 대화, 판정, 승인 및
        견적은 계정별로 저장됩니다. 비밀번호는 해시로 저장되며 Google 가입 계정은 비밀번호 없이
        인증할 수 있습니다.
      </p>
      <h2>기억해 두는 정보</h2>
      <p>
        설정에서 소속, 직무, 선호 실장 방식만 저장합니다. 대화에서 자동으로 추출하지 않습니다.
        사용자가 삭제할 때까지 보관하며 설정에서 한 칸 또는 전체를 삭제할 수 있습니다.
      </p>
      <h2>외부 서비스</h2>
      <p>
        실제 분석 모드에서는 모델과 검색 서비스를 사용합니다. 기억의 의미 검색이 활성화된 환경에서는
        소속·직무를 포함한 기억 문장을 Voyage로 보내 임베딩합니다. 데모 재생은 기록된 응답을
        사용합니다. 요청 시 조회하는 Mouser 가격과 재고는 저장하지 않습니다.
      </p>
      <h2>보관과 삭제</h2>
      <p>
        프로젝트와 대화·승인·견적은 마지막 활동 뒤 60일, 분석 사건·사용량·로그인·가입 시도는 30일을
        기준으로 정리합니다. 사용자 사실에는 자동 만료가 없습니다. 대화나 프로젝트를 직접 삭제할 수
        있으며, 탈퇴 시 계정과 관련 기록을 삭제합니다.
      </p>
      <h2>계정 보호</h2>
      <p>
        세션 쿠키로 로그인 상태를 확인합니다. 세션은 절대 8시간, 유휴 2시간 기준으로 만료됩니다.
        로그아웃하면 세션이 종료됩니다.
      </p>
      <p className="notice">
        운영 주체·개인정보 담당자 연락처는 제공된 명세에 없습니다. 공개 서비스에 사용하기 전에
        운영자가 확정해야 합니다.
      </p>
    </div>
  );
}
