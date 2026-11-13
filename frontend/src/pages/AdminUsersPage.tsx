import { useEffect, useRef, useState } from 'react'
import { getUsers, setUserActive } from '../api/admin'
import type { Account } from '../api/admin'
import { errorMessage, requestIdProps } from '../api/client'
import PageShell from '../components/PageShell'

// 이메일은 서버가 가려서 보낸다(auth.mask_email). 화면은 받은 값을 그대로 보인다.
export default function AdminUsersPage() {
  const [users, setUsers] = useState<Account[]>([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [stopping, setStopping] = useState<number | null>(null)
  const requests = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    requests.current = controller
    getUsers(controller.signal).then(({ users }) => { if (!controller.signal.aborted) setUsers(users) })
      .catch(reason => { if (!controller.signal.aborted) setError(reason) })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => { controller.abort() }
  }, [])
  async function toggle(account: Account) {
    const controller = requests.current
    if (busy || !controller || controller.signal.aborted) return
    setBusy(true); setError(null); setStopping(null)
    try {
      await setUserActive(account.id, !account.is_active, controller.signal)
      if (controller.signal.aborted) return
      const result = await getUsers(controller.signal)
      if (!controller.signal.aborted) setUsers(result.users)
    } catch (reason) { if (!controller.signal.aborted) setError(reason) }
    finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <PageShell wide title="사용자 관리" lead="일반 계정의 접근을 정지하거나 다시 엽니다. 관리자 계정은 여기서 바꿀 수 없습니다.">
    {error ? <p className="notice" role="alert" {...requestIdProps(error)}>계정 정보를 처리하지 못했습니다. {errorMessage(error)}</p> : null}
    {busy && users.length === 0 ? <div className="skeleton" role="status"><span className="sr-only">계정 정보를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>
      : users.length === 0 ? (!error && <p className="empty">등록된 계정이 없습니다.</p>)
        : <div className="table-scroll"><table className="rows rows-static">
          <caption className="sr-only">계정 목록과 접근 상태</caption>
          <thead><tr><th scope="col">이메일</th><th scope="col">역할</th><th scope="col">상태</th><th scope="col">조작</th></tr></thead>
          <tbody>{users.map(account => <tr key={account.id} className={account.is_active ? undefined : 'dim-row'}>
            <th scope="row">{account.email}</th>
            <td data-label="역할">{account.role === 'admin' ? '관리자' : '일반 사용자'}</td>
            <td data-label="상태">{account.is_active ? '이용 중' : '정지됨'}</td>
            <td data-label="조작">{account.role !== 'user' ? '변경 불가' : <span className="row-actions">
              {stopping === account.id ? <><button className="btn" disabled={busy} onClick={() => void toggle(account)}>정지 확인</button><button className="btn" onClick={() => setStopping(null)}>취소</button></>
                : account.is_active ? <button className="btn" disabled={busy} onClick={() => setStopping(account.id)}>정지</button>
                  : <button className="btn" disabled={busy} onClick={() => void toggle(account)}>정지 해제</button>}
            </span>}</td>
          </tr>)}</tbody>
        </table></div>}
    <p className="page-note">이메일은 서버가 가려서 보냅니다. 가림 해제와 강제 탈퇴는 서버 기능이 생긴 뒤에 붙입니다.</p>
  </PageShell>
}
