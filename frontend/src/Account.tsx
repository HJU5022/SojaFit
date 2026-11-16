/** 설정·개인정보 안내. 승인 사례는 Approved.tsx, 관리자는 Admin.tsx. 출처: SPEC 8.5·8.6절. */
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
// [주의] 운영자가 정한 공개 연락처는 이 메일 하나다. 사람 이름은 적지 않는다(#27)
export const contactEmail = 'hajeongun.dev@gmail.com';
/** 개인정보처리방침 본문. 하단 고지 줄(Legal.tsx)이 작은 창과 `/privacy` 페이지로 연다(#20 #27). */
// 출처: 개인정보 보호법 제26·28조의8·30조, 시행령 제31조. 사실 근거는 SPEC 6·7·8.5·8.6절, db/020·029·030, backend/auth.py, docs/GATES.md(DB 서울), README(Cloud Run 서울), docs/deliverables/DELIVERABLES.md(Langfuse EU)
export function PrivacyText() {
  const mail = <a href={'mailto:' + contactEmail}>{contactEmail}</a>;
  return (
    <div className="legal-text">
      <p>
        SojaFit(이하 "서비스")은 「개인정보 보호법」 제30조에 따라 이용자의 개인정보를 어떻게
        처리하는지 알립니다. 시행일: 2026년 11월 16일.
      </p>
      <h2>1. 처리 목적과 항목</h2>
      <table>
        <thead>
          <tr>
            <th>목적</th>
            <th>항목</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>가입·로그인·계정 관리</td>
            <td>
              이메일(로그인 아이디), 비밀번호(해시로만 저장). Google로 가입하면 Google이 확인한
              이메일과 Google 계정 식별값
            </td>
          </tr>
          <tr>
            <td>회로 검토</td>
            <td>프로젝트 이름, 올린 넷리스트(부품·핀·연결), 질문과 대화, 판정·승인·견적 수량</td>
          </tr>
          <tr>
            <td>내 설정(선택)</td>
            <td>소속, 직무, 선호 실장 방식. 직접 입력한 것만 저장하고 대화에서 뽑지 않습니다</td>
          </tr>
          <tr>
            <td>부정 이용 방지·보안</td>
            <td>
              로그인·가입 시도 횟수(이메일과 접속 IP 주소는 해시로 바꿔 저장), 로그인 세션, 서버
              접속 기록(요청 경로·시각·결과)
            </td>
          </tr>
          <tr>
            <td>운영·비용 관리</td>
            <td>분석 기록(상태·단계별 시간), 하루 사용량</td>
          </tr>
        </tbody>
      </table>
      <h2>2. 보유 기간과 파기</h2>
      <table>
        <tbody>
          <tr>
            <td>계정(이메일·비밀번호 해시·Google 계정 식별값)</td>
            <td>탈퇴할 때까지</td>
          </tr>
          <tr>
            <td>프로젝트와 딸린 넷리스트·대화·판정·승인·견적</td>
            <td>마지막 활동 뒤 60일. 그 전에 직접 지울 수 있습니다</td>
          </tr>
          <tr>
            <td>내 설정(소속·직무·선호 실장 방식)</td>
            <td>직접 지우거나 탈퇴할 때까지(자동 만료 없음)</td>
          </tr>
          <tr>
            <td>분석 기록·하루 사용량·로그인·가입 시도 기록</td>
            <td>30일</td>
          </tr>
          <tr>
            <td>로그인 세션</td>
            <td>최대 8시간, 2시간 동안 쓰지 않으면 만료. 로그아웃하면 바로 끝납니다</td>
          </tr>
          <tr>
            <td>가입 확인·비밀번호 재설정 메일 링크, Google 가입 연결 요청</td>
            <td>각각 60분·15분·15분 동안만 유효</td>
          </tr>
          <tr>
            <td>관리자 처리 이력(이메일 가림 해제·계정 정지·탈퇴 처리)</td>
            <td>1년(계정을 삭제한 뒤에도 남습니다)</td>
          </tr>
        </tbody>
      </table>
      <p>
        관리자의 이메일 가림 해제·계정 정지·탈퇴 처리는 처리한 관리자, 대상 계정 번호와 가린 이메일,
        사유, 시각으로 기록되며 계정을 삭제한 뒤에도 1년 동안 남습니다.
      </p>
      <p>
        보유 기간이 지난 정보는 서비스가 새 분석을 시작할 때마다 찾아 데이터베이스에서 지웁니다.
        이용자가 지우거나 탈퇴하면 숨김 처리가 아니라 바로 지웁니다.
      </p>
      <h2>3. 제3자 제공</h2>
      <p>
        이용자의 개인정보를 제3자에게 제공하지 않습니다. 법령에 특별한 규정이 있으면 예외입니다.
      </p>
      <h2>4. 처리 위탁</h2>
      <p>서비스 운영을 위해 아래 업체에 개인정보 처리를 맡깁니다(「개인정보 보호법」 제26조).</p>
      <table>
        <thead>
          <tr>
            <th>수탁자</th>
            <th>맡기는 일</th>
            <th>받는 정보</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Google Cloud(Cloud Run, 서울 리전)</td>
            <td>서비스 서버 운영, 서버 로그</td>
            <td>서비스를 오가는 정보 전부</td>
          </tr>
          <tr>
            <td>Supabase(서울 리전)</td>
            <td>데이터베이스 보관</td>
            <td>1절의 정보 전부(서버 접속 기록 제외)</td>
          </tr>
          <tr>
            <td>OpenRouter</td>
            <td>AI 모델 호출 중계(Anthropic Claude 모델)</td>
            <td>질문·대화, 넷리스트에서 뽑은 회로 정보, 검색한 데이터시트 글</td>
          </tr>
          <tr>
            <td>Voyage AI</td>
            <td>문서 검색·순위 매기기, 내 설정 검색</td>
            <td>질문과 거기서 만든 검색 문장, 내 설정 문장</td>
          </tr>
          <tr>
            <td>Langfuse</td>
            <td>실행 기록(성능·비용·오류 점검)</td>
            <td>계정 번호, 대화 번호, 단계·모델·토큰 수·비용·시간</td>
          </tr>
          <tr>
            <td>Google(Gmail)</td>
            <td>가입 확인·비밀번호 재설정 메일 발송</td>
            <td>받는 사람 이메일, 확인 링크</td>
          </tr>
        </tbody>
      </table>
      <p>
        가격 조회(Mouser)에는 품번만, 공식 데이터시트·원본 회로도 찾기(Exa, Raspberry Pi 사이트)에는
        품번, 프로젝트 이름이나 직접 적은 검색어만 보냅니다. 계정 정보는 보내지 않습니다.
      </p>
      <h2>5. 국외 이전</h2>
      <p>
        질문 분석과 실행 기록을 위해 아래 업체로 개인정보를 보냅니다(「개인정보 보호법」 제28조의8).
        모두 암호화된 연결(HTTPS·SMTP 암호화)로 보냅니다.
      </p>
      <h3>OpenRouter</h3>
      <ul>
        <li>이전받는 자: OpenRouter, Inc.(privacy@openrouter.ai)</li>
        <li>국가: 미국</li>
        <li>
          항목: 질문·대화, 넷리스트에서 뽑은 회로 정보, 검색한 데이터시트 글. 계정 이메일과 내
          설정의 소속·직무는 보내지 않습니다
        </li>
        <li>시기·방법: 질문할 때마다 API로 전송</li>
        <li>목적: 질문 이해, 데이터시트 값 읽기, 설명 글 작성(Anthropic Claude 모델로 전달)</li>
        <li>보유·이용 기간: 각 업체 정책에 따름</li>
        <li>
          거부: 질문하지 않거나 계정을 탈퇴하면 보내지 않습니다. 거부하면 회로 검토를 쓸 수 없습니다
        </li>
      </ul>
      <h3>Voyage AI</h3>
      <ul>
        <li>이전받는 자: Voyage AI Innovations, Inc.(MongoDB 자회사, privacy@mongodb.com)</li>
        <li>국가: 미국</li>
        <li>
          항목: 질문과 거기서 만든 검색 문장, 검색 후보 데이터시트 글, 내 설정 문장(입력한 경우)
        </li>
        <li>시기·방법: 질문할 때와 내 설정을 저장할 때 API로 전송</li>
        <li>목적: 문서 검색과 순위 매기기, 내 설정 검색</li>
        <li>보유·이용 기간: 각 업체 정책에 따름</li>
        <li>
          거부: 내 설정을 비워 두면 그 문장은 보내지 않습니다. 질문하지 않거나 계정을 탈퇴하면
          질문도 보내지 않습니다. 질문 검색을 거부하면 회로 검토를 쓸 수 없습니다
        </li>
      </ul>
      <h3>Langfuse</h3>
      <ul>
        <li>
          항목: 계정 번호, 대화 번호, 단계 이름·모델·토큰 수·비용·소요 시간·오류 수준. 질문·답·내
          설정 글은 보내기 전에 지웁니다
        </li>
        <li>국가: 아일랜드(Langfuse EU 리전, AWS eu-west-1)</li>
        <li>시기·방법: 질문을 분석할 때마다 API로 전송</li>
        <li>목적: 서비스 성능·비용 점검과 오류 확인</li>
        <li>보유·이용 기간: 각 업체 정책에 따름</li>
        <li>거부: 질문하지 않거나 계정을 탈퇴하면 보내지 않습니다</li>
      </ul>
      <h3>Google(Gmail)</h3>
      <ul>
        <li>이전받는 자: Google LLC(Gmail SMTP 메일 발송)</li>
        <li>국가: 미국</li>
        <li>항목: 받는 사람 이메일, 확인 링크</li>
        <li>시기·방법: 가입 확인·비밀번호 재설정 메일을 보낼 때 메일 서버로 전송</li>
        <li>목적: 메일 발송</li>
        <li>보유·이용 기간: 각 업체 정책에 따름</li>
        <li>
          거부: Google로 가입하면 가입 확인 메일을 보내지 않고, 비밀번호 재설정을 쓰지 않거나 계정을
          탈퇴하면 메일을 보내지 않습니다
        </li>
      </ul>
      <h2>6. 쿠키</h2>
      <p>
        로그인 상태를 유지하려고 세션 쿠키(<code>sojafit_session</code>, 최대 8시간)를 씁니다.
        브라우저 스크립트가 읽을 수 없게 설정합니다. Google 로그인 중에만 쓰는 쿠키 2개는 10분·15분
        뒤 만료됩니다. 광고·방문 분석용 쿠키와 외부 분석 스크립트는 쓰지 않습니다. 브라우저 설정에서
        쿠키를 막을 수 있지만, 막으면 로그인할 수 없습니다.
      </p>
      <h2>7. 이용자의 권리와 행사 방법</h2>
      <p>
        이용자는 개인정보의 열람·정정·삭제·처리정지를 요구할 수 있습니다. 화면에서 바로 할 수 있는
        것은 다음과 같습니다.
      </p>
      <ul>
        <li>대화·프로젝트 삭제: 사이드바 대화 메뉴, 프로젝트 목록</li>
        <li>내 설정 수정·삭제: 내 설정에서 칸별 또는 전체</li>
        <li>탈퇴: 내 설정 → 계정 탈퇴(계정과 모든 기록 삭제)</li>
      </ul>
      <p>그 밖의 요구는 {mail}로 보내 주세요. 본인임을 확인한 뒤 지체 없이 처리합니다.</p>
      <h2>8. 안전성 확보 조치</h2>
      <ul>
        <li>비밀번호는 원문 없이 scrypt 해시로만 저장합니다</li>
        <li>
          세션 토큰은 해시만 저장하고, 쿠키는 스크립트가 읽을 수 없게(HttpOnly·SameSite) 설정합니다
        </li>
        <li>
          세션은 최대 8시간·미사용 2시간에 만료되고, 로그인 실패가 계정당 15분 안에 5번이면 15분
          동안 잠급니다
        </li>
        <li>정보를 바꾸는 요청은 보낸 화면의 출처(Origin)를 확인합니다</li>
        <li>프로젝트·대화·내 설정은 계정마다 나눠 본인 것만 조회합니다</li>
        <li>서버 로그에서 주소의 검색어를 지우고, 실행 기록에서 질문·답 글을 지웁니다</li>
      </ul>
      <h2>9. 개인정보 보호책임자</h2>
      <p>
        SojaFit 운영자 · {mail}
        <br />
        개인정보 관련 문의, 불만 처리, 피해 구제 요청은 이 메일로 받습니다.
      </p>
      <h2>10. 권익침해 구제 방법</h2>
      <ul>
        <li>개인정보 분쟁조정위원회: 1833-6972</li>
        <li>개인정보침해신고센터(한국인터넷진흥원): 118</li>
        <li>대검찰청: 1301</li>
        <li>경찰청: 182</li>
      </ul>
      <h2>11. 시행일과 변경 이력</h2>
      <ul>
        <li>시행일: 2026년 11월 16일</li>
        <li>
          2026-11-16: 보호책임자·처리 위탁·국외 이전·쿠키·권리 행사·안전성 확보 조치·구제 방법을
          더해 처리방침으로 고침(이전 "개인정보 처리 안내"를 대체)
        </li>
      </ul>
    </div>
  );
}
