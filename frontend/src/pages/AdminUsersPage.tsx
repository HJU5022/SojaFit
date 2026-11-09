import { useEffect, useRef, useState } from 'react'
import { getUsers, setUserActive } from '../api/admin'
import type { Account } from '../api/admin'
import { errorMessage } from '../api/client'
import RequireAuth from '../auth/RequireAuth'

export default function AdminUsersPage() {
  return <RequireAuth admin><Users /></RequireAuth>
}
function Users() {
  const [users, setUsers] = useState<Account[]>([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const requests = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    requests.current = controller
    getUsers(controller.signal).then(({ users }) => { if (!controller.signal.aborted) setUsers(users) })
      .catch((error) => { if (!controller.signal.aborted) setError(error) })
      .finally(() => { if (!controller.signal.aborted) setBusy(false) })
    return () => { controller.abort() }
  }, [])
  async function toggle(account: Account) {
    const controller = requests.current
    if (busy || !controller || controller.signal.aborted) return
    setBusy(true); setError(null)
    try {
      await setUserActive(account.id, !account.is_active, controller.signal)
      if (controller.signal.aborted) return
      const result = await getUsers(controller.signal)
      if (!controller.signal.aborted) setUsers(result.users)
    } catch (error) {
      if (!controller.signal.aborted) { setUsers([]); setError(error) }
    } finally { if (!controller.signal.aborted) setBusy(false) }
  }
  return <><h1>사용자 관리</h1><p>일반 계정의 접근 권한을 관리합니다. 관리자 계정은 변경할 수 없습니다.</p>
    {busy && <p role="status">계정 정보를 확인 중입니다.</p>}
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    {users.length > 0 && <div className="panel table-scroll"><table>
      <thead><tr><th>이메일</th><th>역할</th><th>상태</th><th>접근 변경</th></tr></thead>
      <tbody>{users.map((account) => <tr key={account.id}>
        <td>{account.email}</td><td>{account.role === 'admin' ? '관리자' : '일반 사용자'}</td><td>{account.is_active ? '활성' : '비활성'}</td>
        <td>{account.role === 'user' ? <button disabled={busy} onClick={() => void toggle(account)}>{account.is_active ? '비활성화' : '활성화'}</button> : '변경 불가'}</td>
      </tr>)}</tbody>
    </table></div>}
    {!busy && !error && users.length === 0 && <p>등록된 계정이 없습니다.</p>}
  </>
}
