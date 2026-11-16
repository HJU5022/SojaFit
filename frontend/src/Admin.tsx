/**
 * 관리자 영역: 계정 목록(이메일은 기본으로 가림), 사유를 적은 가림 해제, 정지·재활성화, 탈퇴 처리, 작업 이력.
 * 권한은 서버가 정한다(관리자가 아니면 403). 가림 해제·정지·재활성화·탈퇴 처리는 서버 이력(admin_audit)에 남고 화면은 따로 남기지 않는다.
 * 출처: SPEC 4절·8.6절.
 */
import { useEffect, useState } from 'react';
import { api } from './api';
import { Empty, ErrorBox, Loading, Modal, useResource } from './ui';
import type { Account, AuditEntry } from './types';
const REVEAL_MS = 60_000; // 원문을 보여 두는 시간. 자리를 비워도 화면에 남아 있지 않게 한다
const ACTIONS: Record<AuditEntry['action'], string> = {
  unmask: '가림 해제',
  deactivate: '정지',
  activate: '재활성화',
  delete: '탈퇴 처리',
};
/** 서버(backend/api/admin.py Unmask)처럼 겹친 공백을 한 칸으로 줄인 길이. */
const reasonLength = (text: string) => text.split(/\s+/).filter(Boolean).join(' ').length;
type Pending = { kind: 'unmask' | 'suspend' | 'delete'; account: Account };
export function Admin() {
  const users = useResource<{ users: Account[] }>('/admin/users'),
    audit = useResource<AuditEntry[]>('/admin/audit');
  const [error, setError] = useState<Error | null>(null),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(''),
    [shown, setShown] = useState<{ id: number; email: string } | null>(null),
    [pending, setPending] = useState<Pending | null>(null),
    [reason, setReason] = useState(''),
    [confirmId, setConfirmId] = useState('');
  useEffect(() => {
    if (!shown) return;
    const timer = setTimeout(() => setShown(null), REVEAL_MS);
    return () => clearTimeout(timer);
  }, [shown]);
  function ask(kind: Pending['kind'], account: Account) {
    setPending({ kind, account });
    setReason('');
    setConfirmId('');
    setError(null);
  }
  async function run(action: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError(null);
    setNotice('');
    try {
      await action();
      setPending(null);
      setNotice(done);
      users.reload();
      audit.reload();
    } catch (e) {
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  const setActive = (account: Account, active: boolean) =>
    run(
      () => api(`/admin/users/${account.id}`, 'PATCH', { is_active: active }),
      active ? '계정을 다시 활성화했습니다.' : '계정을 정지했습니다. 기존 세션도 끝났습니다.',
    );
  const target = pending?.account;
  return (
    <div className="page-content admin-page">
      <p className="admin-kicker">관리자 영역</p>
      <h1>사용자 관리</h1>
      <p className="page-intro">
        관리자만 보는 화면입니다. 이메일은 가려서 보이고, 원문은 사유를 적어야 60초 동안 볼 수
        있습니다. 가림 해제·정지·재활성화·탈퇴 처리는 아래 작업 이력에 남습니다.
      </p>
      {!pending && <ErrorBox error={error} />}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {users.loading ? (
        <Loading />
      ) : users.error ? (
        <ErrorBox error={users.error} retry={users.reload} />
      ) : users.data?.users.length ? (
        <div className="case-list">
          {users.data.users.map((u) => (
            <article key={u.id}>
              <div>
                <h2>{shown?.id === u.id ? shown.email : u.email}</h2>
                <p>
                  #{u.id} · {u.role === 'admin' ? '관리자' : '일반 사용자'} ·{' '}
                  {u.is_active ? '활성' : '정지됨'}
                  {shown?.id === u.id && ' · 원문 표시 중(60초 뒤 다시 가림)'}
                </p>
              </div>
              <div className="case-actions">
                {shown?.id === u.id ? (
                  <button onClick={() => setShown(null)}>다시 가리기</button>
                ) : (
                  <button disabled={busy} onClick={() => ask('unmask', u)}>
                    가림 해제
                  </button>
                )}
                {u.is_active ? (
                  <button disabled={u.role === 'admin' || busy} onClick={() => ask('suspend', u)}>
                    정지
                  </button>
                ) : (
                  <button disabled={u.role === 'admin' || busy} onClick={() => setActive(u, true)}>
                    재활성화
                  </button>
                )}
                <button
                  className="danger"
                  disabled={u.role === 'admin' || busy}
                  onClick={() => ask('delete', u)}
                >
                  탈퇴 처리
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty title="사용자 목록이 없습니다." />
      )}
      <section className="admin-audit">
        <h2>작업 이력</h2>
        <p className="muted">최근 100건입니다. 이력은 고치거나 지울 수 없습니다.</p>
        {audit.loading ? (
          <Loading />
        ) : audit.error ? (
          <ErrorBox error={audit.error} retry={audit.reload} />
        ) : audit.data?.length ? (
          <div className="audit-scroll" role="region" aria-label="작업 이력" tabIndex={0}>
            <table className="audit-table">
              <thead>
                <tr>
                  <th>시각</th>
                  <th>작업</th>
                  <th>대상</th>
                  <th>처리한 관리자</th>
                  <th>사유</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.map((a) => (
                  <tr key={a.id}>
                    <td>{new Date(a.created_at).toLocaleString('ko-KR')}</td>
                    <td>
                      {ACTIONS[a.action]}
                      {a.fields.length ? ` (${a.fields.join(', ')})` : ''}
                    </td>
                    <td>
                      #{a.target_id} {a.target_email}
                    </td>
                    <td>{a.actor_email}</td>
                    <td>{a.reason ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">아직 작업 기록이 없습니다.</p>
        )}
      </section>
      {pending?.kind === 'unmask' && target && (
        <Modal title="이메일 가림 해제" close={() => setPending(null)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                const raw = await api<{ email: string }>(
                  `/admin/users/${target.id}/unmask`,
                  'POST',
                  {
                    reason,
                  },
                );
                setShown({ id: target.id, email: raw.email });
              }, '가림을 해제했습니다. 60초 뒤 다시 가립니다. 이 열람은 사유와 함께 작업 이력에 남았습니다.');
            }}
          >
            <p>
              #{target.id} {target.email}의 이메일 원문을 봅니다. 사유는 작업 이력에 그대로
              남습니다.
            </p>
            <label>
              사유(5~500자)
              <textarea
                value={reason}
                maxLength={500}
                rows={3}
                onChange={(e) => setReason(e.target.value)}
                placeholder="예: 사용자 문의에 답하려고 가입 이메일을 확인함"
              />
            </label>
            <p className="muted">{reasonLength(reason)}/500</p>
            <ErrorBox error={error} />
            <button className="primary" disabled={busy || reasonLength(reason) < 5}>
              사유 남기고 해제
            </button>
          </form>
        </Modal>
      )}
      {pending?.kind === 'suspend' && target && (
        <Modal title="계정을 정지할까요?" close={() => setPending(null)}>
          <p>
            #{target.id} {target.email} 계정의 로그인을 막고 기존 세션을 바로 끝냅니다. 다시
            활성화해도 예전 세션은 돌아오지 않습니다.
          </p>
          <ErrorBox error={error} />
          <button className="primary" disabled={busy} onClick={() => setActive(target, false)}>
            정지
          </button>
        </Modal>
      )}
      {pending?.kind === 'delete' && target && (
        <Modal title="탈퇴 처리할까요?" close={() => setPending(null)}>
          <p>
            #{target.id} {target.email} 계정과 그 프로젝트·대화·분석 기록·승인·견적·기억을 모두
            삭제합니다. 되돌릴 수 없습니다.
          </p>
          <label>
            확인을 위해 계정 번호 {target.id}를 입력하세요
            <input
              inputMode="numeric"
              value={confirmId}
              onChange={(e) => setConfirmId(e.target.value)}
            />
          </label>
          <ErrorBox error={error} />
          <button
            className="primary"
            disabled={busy || confirmId.trim() !== String(target.id)}
            onClick={() =>
              run(
                () => api(`/admin/users/${target.id}`, 'DELETE'),
                `#${target.id} 계정을 탈퇴 처리했습니다.`,
              )
            }
          >
            계정과 모든 기록 삭제
          </button>
        </Modal>
      )}
    </div>
  );
}
