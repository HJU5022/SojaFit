/** 이메일·Google·데모 인증 화면. 세션 발급은 API가 한다. 출처: SPEC 8.6절. */
import {useState} from 'react';
import {ArrowLeft, ArrowRight} from 'lucide-react';
import {api} from './api';
import {Brand,ErrorBox,Loading,navigate,useResource} from './ui';
export function Auth({path,onLogin}:{path:string;onLogin:()=>Promise<void>}){
 const demo=useResource<{enabled:boolean}>('/auth/demo'),google=useResource<{enabled:boolean}>('/auth/google/status');
 const params=new URLSearchParams(location.search),finish=params.get('google')==='finish';
 const pending=useResource<{email:string}>(finish?'/auth/google/onboarding':null);
 const token=params.get('token')??'',signup=path.startsWith('/signup'),reset=path.startsWith('/password-reset'),confirm=!!token||path.endsWith('/confirm');
 const [error,setError]=useState<Error|null>(null),[busy,setBusy]=useState(false),[sent,setSent]=useState(false);
 async function act(fn:()=>Promise<any>,login=false){setBusy(true);setError(null);try{await fn();if(login){await onLogin();navigate('/app',true);}else setSent(true);}catch(e){setError(e as Error);}finally{setBusy(false);}}
 const heading=finish?'Google 계정 연결':confirm?'비밀번호 설정':signup?'이메일로 시작하기':reset?'비밀번호 재설정':'회로 검토를 시작하세요.';
 return <div className="auth-page"><header><Brand/><a href="/"><ArrowLeft size={16}/> 홈으로</a></header><main className="auth-card"><h1>{heading}</h1><p>{finish?'새 계정을 만들거나 기존 계정에 연결하세요.':signup?'인증 메일에서 비밀번호를 설정하면 가입이 끝납니다.':reset?'가입한 이메일로 재설정 링크를 보내드립니다.':'회로와 검토 기록을 한곳에서 이어갑니다.'}</p><ErrorBox error={error}/>{params.get('google')==='error'&&<ErrorBox error="Google 인증을 완료하지 못했습니다. 다시 로그인해 주세요."/>}
 {sent?<div className="notice" role="status"><h2>{confirm?'비밀번호를 설정했습니다.':'메일 요청을 접수했습니다.'}</h2><p>{confirm?'새 비밀번호로 로그인해 주세요.':'사용 가능한 이메일이면 인증 링크가 도착합니다. 받은편지함을 확인해 주세요.'}</p><a className="button primary" href="/login">로그인으로</a></div>:<>
 {finish&&<><p>{pending.data?.email}</p><ErrorBox error={pending.error} retry={pending.reload}/><button className="primary" disabled={busy||!pending.data} onClick={()=>act(()=>api('/auth/google/signup','POST',{}),true)}>새 Google 계정으로 가입</button><h2 className="subheading">기존 계정에 연결</h2></>}
 <form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);const data=confirm?{token,password:f.get('password')}:(signup||reset)?{email:f.get('email')}:{email:f.get('email'),password:f.get('password')};const endpoint=finish?'/auth/google/link':signup?'/auth/signup'+(confirm?'/confirm':''):reset?'/auth/password-reset'+(confirm?'/confirm':''):'/auth/login';void act(()=>api(endpoint,'POST',data),(!signup&&!reset));}}>
 {!confirm&&<label>이메일<input name="email" type="email" autoComplete="email" maxLength={100} required placeholder="name@company.com"/></label>}
 {(!(signup||reset)||confirm)&&<label>비밀번호<input name="password" type="password" autoComplete={confirm?'new-password':'current-password'} minLength={confirm?12:1} maxLength={1024} required/>{confirm&&<small>12~1024자 · 숫자만, 공백만, 단순 반복은 사용할 수 없습니다.</small>}</label>}
 <button className="primary" disabled={busy}>{busy?'처리 중…':confirm?'비밀번호 저장':signup||reset?'인증 메일 받기':finish?'기존 계정 연결':'로그인'}<ArrowRight size={16}/></button></form>
 {!signup&&!reset&&!finish&&<><div className="auth-links"><a href="/signup">회원가입</a><a href="/password-reset">비밀번호를 잊으셨나요?</a></div><button className="google-button" disabled={!google.data?.enabled||busy} onClick={()=>location.assign('/api/auth/google/start')}>Google로 계속{google.data?.enabled?'':' · 사용 불가'}</button>{google.error&&<ErrorBox error={google.error} retry={google.reload}/>}<div className="demo-login">{demo.loading?<Loading/>:demo.data?.enabled?<><h2>넷리스트 없이 먼저 살펴보세요.</h2><p>공개 데모 회로와 기록된 질문으로 체험합니다.</p><div className="demo-buttons">{['a','b'].map(a=><button key={a} disabled={busy} onClick={()=>act(()=>api('/auth/demo-login','POST',{account:a}),true)}>데모 사용자 {a.toUpperCase()} <ArrowRight size={15}/></button>)}</div></>:demo.error&&(demo.error as any).status!==404?<ErrorBox error={demo.error} retry={demo.reload}/>:null}</div></>}
 </>}<a className="privacy-link" href="/privacy">개인정보 처리방침</a></main><div className="auth-note">검토의 출발은 회로.<br/>판단의 기준은 근거.</div></div>;
}
