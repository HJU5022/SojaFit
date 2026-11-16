/** 페이지·세션 경계. 로그아웃 때 업무 상태를 폐기한다. 사이드바는 대화가 먼저다(SPEC 2절). 출처: SPEC 8.6절. */
import { useEffect, useState } from 'react';
import {
  CheckCheck,
  ChevronsUpDown,
  LibraryBig,
  LogOut,
  Mail,
  Menu,
  Plus,
  Settings as SettingsIcon,
  Shield,
  X,
} from 'lucide-react';
import { api, ApiError } from './api';
import {
  Brand,
  ErrorBox,
  followLink,
  Loading,
  navigate,
  ResizeHandle,
  RowMenu,
  useLocation,
} from './ui';
import { Landing } from './Landing';
import { Auth } from './Auth';
import { contactEmail, Settings } from './Account';
import { ApprovedCases, CaseReport } from './Approved';
import { Admin } from './Admin';
import { Library } from './Library';
import { isLegalPath, LegalModal, LegalPage, legalDocs } from './Legal';
import { ConversationNav, NewConversation } from './Conversations';
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
    [legal, setLegal] = useState<string | null>(null),
    [error, setError] = useState<Error | null>(null);
  const demo = user.email.startsWith('demo-'),
    initial = (demo ? user.email[5] : user.email[0]).toUpperCase(),
    name = demo ? '데모 사용자 ' + initial : user.email;
  const params = new URLSearchParams(path.split('?')[1]),
    pathname = path.split('?')[0];
  useEffect(() => setOpen(false), [path]);
  return (
    <div className="app-shell">
      <header className="mobile-header">
        <button
          aria-label="메뉴 열기"
          title="메뉴 열기"
          className="icon-button"
          onClick={() => setOpen(true)}
        >
          <Menu size={21} />
        </button>
        <Brand />
        <a href="/settings" className="icon-button" aria-label="내 설정" title="내 설정">
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
            title="메뉴 닫기"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </div>
        <button className="new-project-button primary" onClick={() => navigate('/app')}>
          <Plus size={17} />새 대화
        </button>
        <nav>
          <a href="/approved" className={path === '/approved' ? 'nav-active' : ''}>
            <CheckCheck size={17} />
            승인 사례
          </a>
          <a href="/library" className={pathname === '/library' ? 'nav-active' : ''}>
            <LibraryBig size={17} />
            데이터시트 서재
          </a>
        </nav>
        {/* [왜] 내 설정·사용자 관리는 계정 화면이라 대화·프로젝트 목록을 보이지 않는다(#21). 돌아가기는 위 "새 대화"·메뉴로 한다 */}
        {pathname !== '/settings' && !pathname.startsWith('/admin') && (
          <ConversationNav projectId={params.get('project')} threadId={params.get('thread')} />
        )}
        {/* [왜] Claude 앱처럼 맨 아래는 계정 줄 하나만 두고, 설정 · 관리 · 고지 · 문의 · 로그아웃은 위로 여는 계정 메뉴에 모은다(#43) */}
        <div className="sidebar-bottom">
          <RowMenu
            label={name + ' 계정 메뉴'}
            className="account-menu"
            up
            icon={
              <>
                <span className="avatar">{initial}</span>
                <span className="account-name">{name}</span>
                <ChevronsUpDown size={15} />
              </>
            }
            items={[
              {
                label: '내 설정',
                icon: <SettingsIcon size={15} />,
                onSelect: () => navigate('/settings'),
              },
              ...(user.role === 'admin'
                ? [
                    {
                      label: '사용자 관리',
                      icon: <Shield size={15} />,
                      sep: true,
                      onSelect: () => navigate('/admin'),
                    },
                  ]
                : []),
              ...legalDocs.map(([doc, title], i) => ({
                label: title,
                strong: doc === '/privacy', // 개인정보처리방침은 국내 관행대로 굵게
                sep: i === 0,
                onSelect: () => setLegal(doc),
              })),
              {
                label: '문의',
                icon: <Mail size={15} />,
                sep: true,
                onSelect: () => (location.href = 'mailto:' + contactEmail),
              },
              {
                label: '로그아웃',
                icon: <LogOut size={15} />,
                sep: true,
                onSelect: async () => {
                  try {
                    await api('/auth/logout', 'POST');
                    onLogout();
                  } catch (e) {
                    setError(e as Error);
                  }
                },
              },
            ]}
          />
          <ErrorBox error={error} />
        </div>
        <ResizeHandle
          name="sidebar-w"
          label="사이드바 너비 조절"
          min={200}
          max={420}
          edge="right"
        />
      </aside>
      {legal && <LegalModal path={legal} close={() => setLegal(null)} />}
      <div className="app-frame">
        {/* [왜] 상단 "지금 지원" 문구는 뺐다. 지원 범위는 내 설정에 따로 둔다(#37) */}
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
    document.addEventListener('click', followLink);
    return () => {
      window.removeEventListener('session-expired', logout);
      document.removeEventListener('click', followLink);
    };
  }, []);
  const publicPage =
    pathname === '/' ||
    isLegalPath(pathname) || // 이용약관 · 개인정보처리방침 · AI 이용 안내 · 출처·라이선스(#27)
    pathname === '/login' ||
    pathname.startsWith('/signup') ||
    pathname.startsWith('/password-reset') ||
    // 백엔드가 보내는 메일 링크: {AUTH_ORIGIN}/verify-email#token=… · /reset-password#token=… (backend/services/mail.py)
    pathname === '/verify-email' ||
    pathname === '/reset-password';
  useEffect(() => {
    if (!checking && !user && !publicPage && !error) navigate('/login', true);
    // [왜] 프로젝트 목록 페이지는 사이드바 나무로 옮겼다(#34). 옛 주소 /projects는 새 대화 화면으로 바꾼다
    if (!checking && user && (pathname === '/login' || pathname === '/projects'))
      navigate('/app', true);
  }, [checking, user, publicPage, error, pathname]);
  if (pathname === '/') return <Landing />;
  if (isLegalPath(pathname)) return <LegalPage path={pathname} />;
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
  // 인쇄용 보고서는 사이드바 없이 화면 전체에 그린다(#44)
  const report = pathname.match(/^\/approved\/(\d+)\/report$/);
  if (report) return <CaseReport id={Number(report[1])} email={user.email} />;
  const params = new URLSearchParams(path.split('?')[1]),
    project = params.get('project'),
    thread = params.get('thread');
  return (
    <Shell key={generation} user={user} path={path} onLogout={logout}>
      {pathname === '/settings' ? (
        <Settings user={user} onLogout={logout} />
      ) : pathname === '/approved' ? (
        <ApprovedCases />
      ) : pathname === '/library' ? (
        <Library search={params.toString()} />
      ) : pathname === '/admin' || pathname === '/admin/users' ? (
        user.role === 'admin' ? (
          <Admin />
        ) : (
          <div className="page-content">
            <h1>관리자만 접근할 수 있습니다.</h1>
            <a href="/app">새 대화로</a>
          </div>
        )
      ) : pathname === '/app' || pathname === '/projects' ? (
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
