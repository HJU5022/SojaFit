import { useState } from 'react'
import { Link } from 'react-router-dom'
import AccessibleDialog from './AccessibleDialog'

export default function AccountMenu({ user, onLogout, logoutBusy = false, onMotionChange }: {
  user?: { email?: string; role: 'user' | 'admin' }
  onLogout?: () => Promise<void>
  logoutBusy?: boolean
  onMotionChange?: (reduced: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [reduceMotion, setReduceMotion] = useState(() => window.localStorage?.getItem('sojafit-reduce-motion') === 'true')
  return <div className="workbench-account">
    <button className="account-menu-trigger secondary" title={user?.email || '계정'} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <svg aria-hidden="true" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" /></svg><span>{user?.email || '계정'}</span>
    </button>
    {open && <div className="account-menu-popover" role="menu" aria-label="계정 메뉴">{user ? <>
      <div className="account-menu-summary"><strong>{user.email || '계정'}</strong><span>{user.role === 'admin' ? '관리자' : '일반 사용자'}</span></div>
      <button role="menuitem" onClick={() => { setOpen(false); setSettingsOpen(true) }}>개인 설정</button>
      <Link role="menuitem" to="/settings" onClick={() => setOpen(false)}>내 설정 관리</Link>
      {user.role === 'admin' && <div className="account-menu-admin" role="group" aria-label="관리자 메뉴">
        <span className="account-menu-section-title" aria-hidden="true">관리자 메뉴</span>
        <Link role="menuitem" to="/admin/users" onClick={() => setOpen(false)}>사용자 관리</Link>
      </div>}
      <button role="menuitem" disabled={logoutBusy} onClick={() => { setOpen(false); void onLogout?.() }}>{logoutBusy ? '로그아웃 중…' : '로그아웃'}</button>
    </> : <Link role="menuitem" to="/login" onClick={() => setOpen(false)}>로그인</Link>}</div>}
    {settingsOpen && <AccessibleDialog title="개인 설정" onClose={() => setSettingsOpen(false)}>
      <div className="personal-settings"><p>이 화면 설정은 현재 브라우저에 저장됩니다.</p>
        <label className="setting-toggle"><input type="checkbox" checked={reduceMotion} onChange={event => {
          const checked = event.target.checked
          setReduceMotion(checked); window.localStorage?.setItem('sojafit-reduce-motion', String(checked)); onMotionChange?.(checked)
        }} />동작 효과 줄이기</label>
      </div><div className="dialog-actions"><button onClick={() => setSettingsOpen(false)}>확인</button></div>
    </AccessibleDialog>}
  </div>
}
