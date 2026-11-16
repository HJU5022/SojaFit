/** 이메일·Google·데모 인증 화면. 세션 발급은 API가 한다. 출처: SPEC 8.6절, docs/specs/login-auth.md "로그인 실패 안내". */
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { api, ApiError } from './api';
import { Brand, ErrorBox, Loading, navigate, useResource } from './ui';
import { PrivacyLink } from './Account';
/** 로그인·계정 연결 POST의 401이 아닌 실패를 원인별 문구로 바꾼다(401은 화면이 횟수와 함께 따로 보인다). */
function loginFailure(e: unknown): string {
  // [왜] 연결이 끊기면 fetch가 ApiError가 아닌 TypeError를 던진다(api.ts의 checked를 거치지 않는다)
  if (!(e instanceof ApiError))
    return '서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.';
  // [주의] 로그인 경로가 내는 상태는 401 · 403(ORIGIN_MISMATCH) · 422 · 503 · 500뿐이다(backend/api/auth.py login). 429는 내지 않는다
  if (e.status === 422) return '이메일 주소 형식을 확인해 주세요.';
  if (e.status === 403)
    return '요청 출처를 확인하지 못했어요. 페이지를 새로고침한 뒤 다시 시도해 주세요.';
  if (e.status >= 500) return '로그인 서버에 일시적인 문제가 있어요. 잠시 후 다시 시도해 주세요.';
  return e.message;
}
export function Auth({ path, onLogin }: { path: string; onLogin: () => Promise<void> }) {
  const demo = useResource<{ enabled: boolean }>('/auth/demo'),
    google = useResource<{ enabled: boolean }>('/auth/google/status');
  const params = new URLSearchParams(location.search),
    finish = params.get('google') === 'finish';
  const pending = useResource<{ email: string }>(finish ? '/auth/google/onboarding' : null);
  // 메일 링크는 토큰을 #token=…에 싣는다(backend/services/mail.py). 읽은 뒤 주소와 방문 기록에서 지운다.
  const [token] = useState(
    () => new URLSearchParams(location.hash.slice(1)).get('token') ?? params.get('token') ?? '',
  );
  useEffect(() => {
    if (location.hash) history.replaceState(history.state, '', location.pathname + location.search);
  }, []);
  const signup = path.startsWith('/signup') || path === '/verify-email',
    reset = path.startsWith('/password-reset') || path === '/reset-password',
    confirm = !!token || path.endsWith('/confirm');
  const [error, setError] = useState<Error | string | null>(null),
    [busy, setBusy] = useState(false),
    [sent, setSent] = useState(false),
    // 이 화면에서 같은 이메일로 401을 받은 횟수. [주의] 서버 잠금 횟수(다른 탭·이전 시도 포함)와 다를 수 있어 '이 화면에서'라고만 쓴다
    [wrong, setWrong] = useState({ email: '', count: 0, shown: false });
  const password = useRef<HTMLInputElement>(null);
  /** email은 비밀번호로 로그인·연결하는 폼에서만 넘긴다(그때만 실패를 원인별 문구로 바꾼다). */
  async function act(fn: () => Promise<any>, login = false, email?: string) {
    setBusy(true);
    setError(null);
    setWrong((w) => ({ ...w, shown: false }));
    let posted = false;
    try {
      await fn();
      posted = true;
      if (login) {
        await onLogin();
        navigate('/app', true);
      } else setSent(true);
    } catch (e) {
      // [왜] 로그인 POST가 성공한 뒤 /auth/me 확인이 실패한 것은 비밀번호 문제가 아니다. 로그인 POST는 다시 보내지 않는다
      if (posted)
        setError('로그인은 됐지만 로그인 상태를 확인하지 못했어요. 페이지를 새로고침해 주세요.');
      else if (email === undefined) setError(e as Error);
      else if (e instanceof ApiError && e.status === 401) {
        setWrong({ email, count: wrong.email === email ? wrong.count + 1 : 1, shown: true });
        if (password.current) password.current.value = ''; // 실패하면 비밀번호만 비우고 이메일은 둔다
      } else setError(loginFailure(e));
    } finally {
      setBusy(false);
    }
  }
  const heading = finish
    ? 'Google 계정 연결'
    : confirm
      ? '비밀번호 설정'
      : signup
        ? '이메일로 시작하기'
        : reset
          ? '비밀번호 재설정'
          : '로그인';
  return (
    <div className="auth-page">
      <header>
        <Brand />
        <a href="/">
          <ArrowLeft size={16} /> 홈으로
        </a>
      </header>
      <main className="auth-card">
        <h1>{heading}</h1>
        {(finish || signup || reset) && (
          <p>
            {finish
              ? '새 계정을 만들거나 기존 계정에 연결하세요.'
              : signup
                ? '인증 메일에서 비밀번호를 설정하면 가입이 끝납니다.'
                : '가입한 이메일로 재설정 링크를 보내드립니다.'}
          </p>
        )}
        {/* [왜] 서버는 계정 없음·비밀번호 틀림·계정 잠금(5회/15분)·IP 잠금(30회/15분)·비활성을 같은 401로 돌려 어느 쪽인지 알 수 없다
            (backend/api/auth.py login, 계정 열거 방지). 그래서 어느 칸이 틀렸는지 말하지 않고, 이 화면의 횟수와 잠금 규칙만 보인다 */}
        <ErrorBox
          error={
            wrong.shown
              ? wrong.count < 5
                ? `이메일 또는 비밀번호가 맞지 않아요. 이 화면에서 이 이메일로 ${wrong.count}번 틀렸어요.`
                : `이메일 또는 비밀번호가 맞지 않거나, 계정이 15분 동안 잠겼을 수 있어요. 이 화면에서 이 이메일로 ${wrong.count}번 틀렸어요.`
              : error
          }
        />
        {wrong.shown && (
          <p className="auth-help">
            같은 계정으로 15분 안에 5번 틀리면 15분 동안 로그인할 수 없어요. 비밀번호가 기억나지
            않으면 <a href="/password-reset">비밀번호 재설정</a>
            {!finish && (
              <>
                , 가입한 적이 없으면 <a href="/signup">회원가입</a>
                {google.data?.enabled && ", Google로 가입했다면 아래 'Google로 계속'"}
              </>
            )}
            을 이용해 주세요.
          </p>
        )}
        {params.get('google') === 'error' && (
          <ErrorBox error="Google 인증을 완료하지 못했습니다. 다시 로그인해 주세요." />
        )}
        {sent ? (
          <div className="notice" role="status">
            <h2>{confirm ? '비밀번호를 설정했습니다.' : '메일 요청을 접수했습니다.'}</h2>
            <p>
              {confirm
                ? '새 비밀번호로 로그인해 주세요.'
                : '사용 가능한 이메일이면 인증 링크가 도착합니다. 받은편지함을 확인해 주세요.'}
            </p>
            <a className="button primary" href="/login">
              로그인으로
            </a>
          </div>
        ) : (
          <>
            {finish && (
              <>
                <p>{pending.data?.email}</p>
                <ErrorBox error={pending.error} retry={pending.reload} />
                <button
                  className="primary"
                  disabled={busy || !pending.data}
                  onClick={() => act(() => api('/auth/google/signup', 'POST', {}), true)}
                >
                  새 Google 계정으로 가입
                </button>
                <h2 className="subheading">기존 계정에 연결</h2>
              </>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                const data = confirm
                  ? { token, password: f.get('password') }
                  : signup || reset
                    ? { email: f.get('email') }
                    : { email: f.get('email'), password: f.get('password') };
                const endpoint = finish
                  ? '/auth/google/link'
                  : signup
                    ? '/auth/signup' + (confirm ? '/confirm' : '')
                    : reset
                      ? '/auth/password-reset' + (confirm ? '/confirm' : '')
                      : '/auth/login';
                // 같은 계정의 횟수를 세려고 서버(backend/api/auth.py Login.check_email)처럼 공백을 떼고 소문자로 맞춘다
                const email = String(f.get('email') ?? '')
                  .trim()
                  .toLowerCase();
                void act(
                  () => api(endpoint, 'POST', data),
                  !signup && !reset,
                  !signup && !reset && !confirm ? email : undefined,
                );
              }}
            >
              {!confirm && (
                <label>
                  이메일
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    maxLength={100}
                    required
                    placeholder="name@company.com"
                  />
                </label>
              )}
              {(!(signup || reset) || confirm) && (
                <label>
                  비밀번호
                  <input
                    ref={password}
                    name="password"
                    type="password"
                    autoComplete={confirm ? 'new-password' : 'current-password'}
                    minLength={confirm ? 12 : 1}
                    maxLength={1024}
                    required
                  />
                  {confirm && (
                    <small>12~1024자 · 숫자만, 공백만, 단순 반복은 사용할 수 없습니다.</small>
                  )}
                </label>
              )}
              <button className="primary" disabled={busy}>
                {busy
                  ? '처리 중…'
                  : confirm
                    ? '비밀번호 저장'
                    : signup || reset
                      ? '인증 메일 받기'
                      : finish
                        ? '기존 계정 연결'
                        : '로그인'}
                <ArrowRight size={16} />
              </button>
            </form>
            {!signup && !reset && !finish && (
              <>
                <div className="auth-links">
                  <a href="/signup">회원가입</a>
                  <a href="/password-reset">비밀번호를 잊으셨나요?</a>
                </div>
                <button
                  className="google-button"
                  disabled={!google.data?.enabled || busy}
                  onClick={() => location.assign('/api/auth/google/start')}
                >
                  Google로 계속{google.data?.enabled ? '' : ' · 사용 불가'}
                </button>
                {google.error && <ErrorBox error={google.error} retry={google.reload} />}
                <div className="demo-login">
                  {demo.loading ? (
                    <Loading />
                  ) : demo.data?.enabled ? (
                    <>
                      <h2>넷리스트 없이 먼저 살펴보세요.</h2>
                      <p>공개 데모 회로와 기록된 질문으로 체험합니다.</p>
                      <div className="demo-buttons">
                        {['a', 'b'].map((a) => (
                          <button
                            key={a}
                            disabled={busy}
                            onClick={() =>
                              act(() => api('/auth/demo-login', 'POST', { account: a }), true)
                            }
                          >
                            데모 사용자 {a.toUpperCase()} <ArrowRight size={15} />
                          </button>
                        ))}
                      </div>
                    </>
                  ) : demo.error && (demo.error as any).status !== 404 ? (
                    <ErrorBox error={demo.error} retry={demo.reload} />
                  ) : null}
                </div>
              </>
            )}
          </>
        )}
      </main>
      {/* [왜] 카드 안에 두면 로그인 단추 다음으로 눈에 띈다. 화면 맨 아래에 조용히 둔다(#20) */}
      <PrivacyLink className="privacy-link" />
    </div>
  );
}
