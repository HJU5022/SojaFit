/** 페이지·세션 경계. 로그아웃 때 업무 상태를 폐기한다. 사이드바는 대화가 먼저다(SPEC 2절). 출처: SPEC 8.6절. */
import { useEffect, useState } from 'react';
import {
  CheckCheck,
  Folder,
  LogOut,
  Menu,
  Plus,
  Settings as SettingsIcon,
  Shield,
  X,
} from 'lucide-react';
import { api, ApiError } from './api';
import { Brand, ErrorBox, Loading, navigate, useLocation } from './ui';
import { Landing } from './Landing';
import { Auth } from './Auth';
import { Admin, ApprovedCases, Privacy, Settings } from './Account';
import { ConversationNav, NewConversation } from './Conversations';
import { ProjectList } from './Projects';
import { Workbench } from './Workbench';
import type { User } from './types';
function Shell({
  user,
  path,
  children,
  onLogout,
}: {
  user: User;
  path: string;
  children: React.ReactNode;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const params = new URLSearchParams(path.split('?')[1]),
    pathname = path.split('?')[0];
  useEffect(() => setOpen(false), [path]);
  return (
    <div className="app-shell">
      <header className="mobile-header">
        <button aria-label="메뉴 열기" className="icon-button" onClick={() => setOpen(true)}>
          <Menu size={21} />
        </button>
        <Brand />
        <a href="/settings" aria-label="내 설정">
          <SettingsIcon size={19} />
        </a>
      </header>
      {open && (
        <button className="nav-scrim" aria-label="메뉴 닫기" onClick={() => setOpen(false)} />
      )}
      <aside className={'sidebar ' + (open ? 'open' : '')}>
        <div className="sidebar-brand">
          <Brand />
          <button
            className="mobile-only icon-button"
            aria-label="메뉴 닫기"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <button className="new-project-button primary" onClick={() => navigate('/app')}>
          <Plus size={17} />새 대화
        </button>
        <nav>
          <a href="/projects" className={pathname === '/projects' ? 'nav-active' : ''}>
            <Folder size={17} />
            프로젝트
          </a>
          <a href="/approved" className={path === '/approved' ? 'nav-active' : ''}>
            <CheckCheck size={17} />
            승인 사례
          </a>
        </nav>
        <ConversationNav projectId={params.get('project')} threadId={params.get('thread')} />
        <div className="sidebar-bottom">
          <a href="/settings">
            <SettingsIcon size={17} />내 설정
          </a>
          {user.role === 'admin' && (
            <a href="/admin">
              <Shield size={17} />
              사용자 관리
            </a>
          )}
          <div className="account-info">
            <span className="avatar">
              {user.email.startsWith('demo-')
                ? user.email[5].toUpperCase()
                : user.email[0].toUpperCase()}
            </span>
            <span>
              {user.email.startsWith('demo-')
                ? '데모 사용자 ' + user.email[5].toUpperCase()
                : user.email}
            </span>
            <button
              className="icon-button"
              aria-label="로그아웃"
              onClick={async () => {
                try {
                  await api('/auth/logout', 'POST');
                  onLogout();
                } catch (e) {
                  setError(e as Error);
                }
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
          <ErrorBox error={error} />
          <a className="privacy-small" href="/privacy">
            개인정보 처리방침
          </a>
        </div>
      </aside>
      <div className="app-frame">
        <div className="app-topbar">
          <span>다이오드 대체 검토</span>
        </div>
        <main className="app-sheet">{children}</main>
      </div>
    </div>
  );
}
export default function App() {
  const path = useLocation(),
    pathname = path.split('?')[0];
  const [user, setUser] = useState<User | null>(null),
    [checking, setChecking] = useState(true),
    [error, setError] = useState<Error | null>(null),
    [generation, setGeneration] = useState(0);
  async function check() {
    setError(null);
    setChecking(true);
    try {
      setUser(await api<User>('/auth/me'));
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) setError(e as Error);
      setUser(null);
    } finally {
      setChecking(false);
    }
  }
  function logout() {
    setUser(null);
    setGeneration((v) => v + 1);
    sessionStorage.clear();
    navigate('/login', true);
  }
  useEffect(() => {
    void check();
    window.addEventListener('session-expired', logout);
    return () => window.removeEventListener('session-expired', logout);
  }, []);
  const publicPage =
    pathname === '/' ||
    pathname === '/privacy' ||
    pathname === '/login' ||
    pathname.startsWith('/signup') ||
    pathname.startsWith('/password-reset') ||
    // 백엔드가 보내는 메일 링크: {AUTH_ORIGIN}/verify-email#token=… · /reset-password#token=… (backend/services/mail.py)
    pathname === '/verify-email' ||
    pathname === '/reset-password';
  useEffect(() => {
    if (!checking && !user && !publicPage && !error) navigate('/login', true);
    if (!checking && user && pathname === '/login') navigate('/app', true);
  }, [checking, user, publicPage, error, pathname]);
  if (pathname === '/') return <Landing />;
  if (pathname === '/privacy') return <Privacy />;
  if (checking)
    return (
      <div className="page-content">
        <Loading label="로그인 상태 확인 중" />
      </div>
    );
  if (error)
    return (
      <div className="page-content">
        <Brand />
        <ErrorBox error={error} retry={check} />
      </div>
    );
  if (publicPage)
    return (
      <Auth
        key={pathname}
        path={pathname}
        onLogin={async () => {
          setUser(await api<User>('/auth/me'));
        }}
      />
    );
  if (!user) return null;
  const params = new URLSearchParams(path.split('?')[1]),
    project = params.get('project'),
    thread = params.get('thread');
  return (
    <Shell key={generation} user={user} path={path} onLogout={logout}>
      {pathname === '/settings' ? (
        <Settings user={user} onLogout={logout} />
      ) : pathname === '/approved' ? (
        <ApprovedCases />
      ) : pathname === '/admin' || pathname === '/admin/users' ? (
        user.role === 'admin' ? (
          <Admin />
        ) : (
          <div className="page-content">
            <h1>관리자만 접근할 수 있습니다.</h1>
            <a href="/app">새 대화로</a>
          </div>
        )
      ) : pathname === '/projects' ? (
        <ProjectList />
      ) : pathname === '/app' ? (
        project ? (
          <Workbench key={project} projectId={project} threadId={thread} />
        ) : (
          <NewConversation />
        )
      ) : (
        <div className="page-content">
          <h1>페이지를 찾을 수 없습니다.</h1>
          <a href="/app">새 대화로</a>
        </div>
      )}
    </Shell>
  );
}
