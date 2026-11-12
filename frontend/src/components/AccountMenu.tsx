import { useState } from 'react'
import { Link } from 'react-router-dom'

export default function AccountMenu({ user, onLogout, logoutBusy = false }: {
  user?: { email?: string; role: 'user' | 'admin' }
  onLogout?: () => Promise<void>
  logoutBusy?: boolean
}) {
  const [open, setOpen] = useState(false)
  return <div className="workbench-account">
    <button className="account-menu-trigger secondary" title={user?.email || '계정'} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <svg aria-hidden="true" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" /></svg><span>{user?.email || '계정'}</span>
    </button>
    {open && <div className="account-menu-popover" role="menu" aria-label="계정 메뉴">{user ? <>
      <div className="account-menu-summary"><strong>{user.email || '계정'}</strong><span>{user.role === 'admin' ? '관리자' : '일반 사용자'}</span></div>
      <Link role="menuitem" to="/settings" onClick={() => setOpen(false)}>내 설정 관리</Link>
      {user.role === 'admin' && <div className="account-menu-admin" role="group" aria-label="관리자 메뉴">
        <span className="account-menu-section-title" aria-hidden="true">관리자 메뉴</span>
        <Link role="menuitem" to="/admin/users" onClick={() => setOpen(false)}>사용자 관리</Link>
      </div>}
      <button role="menuitem" disabled={logoutBusy} onClick={() => { setOpen(false); void onLogout?.() }}>{logoutBusy ? '로그아웃 중…' : '로그아웃'}</button>
    </> : <Link role="menuitem" to="/login" onClick={() => setOpen(false)}>로그인</Link>}</div>}
  </div>
}
