import { useEffect } from 'react'
import { Link } from 'react-router-dom'

const contents = [
  ['collection', '처리 목적과 항목'], ['retention', '보유 기간'], ['deletion', '파기 절차'],
  ['providers', '외부 서비스 이용'], ['overseas', '국외 이전'], ['ai', 'AI 분석과 추적'],
  ['storage', '쿠키와 브라우저 저장'], ['rights', '이용자 권리'], ['security', '안전조치'],
  ['contact', '담당자와 문의'], ['changes', '방침 변경'],
]

export default function PrivacyPage() {
  useEffect(() => { document.documentElement.scrollTop = 0 }, [])
  return <div className="landing privacy-page">
    <header className="land-nav"><Link className="brand" to="/"><img src="/assets/sojafit-icon.svg" alt="" width="24" height="24" />SojaFit</Link><Link className="btn" to="/">서비스 소개</Link></header>
    <article className="privacy-content" aria-labelledby="privacy-title">
      <h1 id="privacy-title">개인정보처리방침</h1>
      <p className="privacy-draft"><strong>안내 초안</strong> · 운영 정보 확인 중</p>
      <p>SojaFit 웹서비스의 개인정보 처리 내용을 설명합니다. 운영자명·문의 연락처와 외부 처리 계약 등 미확정 항목은 공개 전 확정할 항목에 구분했습니다. 이 문서는 확정·시행된 최종 방침이 아닌 검토본입니다.</p>
      <p className="privacy-review-date">검토 기준일: 2026년 11월 12일 · 시행일: 미정</p>
      <section className="privacy-summary" aria-labelledby="privacy-summary-heading">
        <h2 id="privacy-summary-heading">개인정보 처리 안내</h2>
        <p>계정 인증, 회로·대화의 저장과 분석, 선택한 내 설정의 활용, 보안과 사용량 관리를 위해 필요한 정보를 처리합니다. 아래 표에서 직접 입력한 정보와 서비스 이용 중 생성되는 정보를 구분해 확인할 수 있습니다.</p>
      </section>
      <div className="privacy-layout">
      <nav className="privacy-toc" aria-label="개인정보처리방침 목차"><ul>{contents.map(([id, label]) => <li key={id}><a href={`#privacy-${id}`}>{label}</a></li>)}</ul></nav>
      <div className="privacy-sections">
        <section id="privacy-collection" aria-labelledby="privacy-collection-heading">
          <h2 id="privacy-collection-heading">처리 목적과 항목</h2>
          <table aria-label="개인정보 처리 목적과 항목"><thead><tr><th scope="col">구분</th><th scope="col">처리하는 정보</th><th scope="col">이용 목적·수집 방법</th></tr></thead><tbody>
            <tr><th scope="row">계정 · 인증</th><td>회원번호, 이메일, 계정 상태·권한, Google 계정 식별자. 비밀번호 계정은 비밀번호의 해시값</td><td>가입·로그인과 본인 계정 확인. 직접 입력 또는 Google 인증 응답에서 수집</td></tr>
            <tr><th scope="row">프로젝트 · 분석</th><td>프로젝트명, 업로드한 회로와 연결 정보, 선택 부품, 질문·사용 조건·추가 답변, 첨부 NET·TXT에서 추출한 내용, 대화·분석 결과와 저장한 검토 기록</td><td>사용자 입력을 받아 회로 검토를 수행하고 프로젝트·이전 대화를 다시 표시</td></tr>
            <tr><th scope="row">내 설정 · 선택</th><td>소속, 직무, 선호 실장 방식과 검색용으로 변환한 정보</td><td>직접 저장한 경우 관련 설정을 찾아 답변 옆 참고 정보로 표시. 입력하지 않아도 계정을 이용할 수 있음</td></tr>
            <tr><th scope="row">보안 · 이용 기록</th><td>세션 식별정보, 접속·실행 시각, 요청·대화 식별자, 응답 상태, 모델·토큰·비용·시간 등 사용량, 로그인·가입 시도 식별정보</td><td>로그인 유지, 부정 이용 방지, 오류 확인·사용량 관리 과정에서 생성. 인증 시도 DB에는 이메일·IP의 해시를 사용하며 클라우드 접속 로그에는 IP 등 요청 정보가 남을 수 있음</td></tr>
          </tbody></table>
          <p>Google 비밀번호는 SojaFit이 받지 않습니다. Google 인증은 이메일과 계정 식별에 필요한 범위를 사용합니다. 이메일은 계정 확인을 위해 저장하며, 비밀번호를 설정한 계정의 비밀번호는 해시값으로 저장합니다.</p>
        </section>
        <section id="privacy-retention" aria-labelledby="privacy-retention-heading">
          <h2 id="privacy-retention-heading">보유 기간</h2>
          <table aria-label="개인정보 보유 기준"><thead><tr><th scope="col">정보</th><th scope="col">보유·삭제 기준</th></tr></thead><tbody>
            <tr><th scope="row">계정 · Google 연결</th><td>계정 이용 중 보관하며 계정 삭제가 성공하면 관련 계정·연결 정보를 삭제합니다.</td></tr>
            <tr><th scope="row">프로젝트 · 연결된 분석 기록</th><td>마지막 활동 후 60일이 지나면 삭제 대상이 됩니다. 직접 삭제 요청이 성공하면 대상 프로젝트와 연결된 기록을 서비스 DB에서 삭제합니다.</td></tr>
            <tr><th scope="row">분석 사건 · 로그인/가입 시도 · 일일 사용량</th><td>30일 경과한 기록이 정리 대상입니다. 유효한 잠금 등 보안 처리 중인 기록에는 별도 정리 조건이 적용됩니다.</td></tr>
            <tr><th scope="row">선택한 내 설정</th><td>해당 항목을 직접 삭제하거나 계정을 삭제할 때까지 보관합니다.</td></tr>
            <tr><th scope="row">로그인 세션</th><td>최대 8시간, 마지막 이용 후 2시간이 지나면 인증에 사용할 수 없습니다. 로그아웃 시 세션을 삭제하며 만료된 DB 세션의 정리는 새 로그인 요청 때 수행됩니다.</td></tr>
            <tr><th scope="row">클라우드 로그 · 외부 추적 · 백업 사본</th><td>위의 30일·60일 기준과 별개입니다. 실제 보관 기간과 삭제 반영 주기, 외부 서비스의 계약·설정은 공개 전 확인할 항목입니다.</td></tr>
          </tbody></table>
          <p className="privacy-important">기간이 지난 프로젝트·기록의 정리는 새 분석 요청 때 작은 묶음으로 실행됩니다. 기한이 되는 순간 모든 기록이 일괄 삭제되는 방식은 아니며, 정리 실패나 후속 요청 부재로 삭제가 늦어질 수 있습니다.</p>
        </section>
        <section id="privacy-deletion" aria-labelledby="privacy-deletion-heading">
          <h2 id="privacy-deletion-heading">파기 절차</h2>
          <p>프로젝트·대화·내 설정·계정의 삭제 요청이 성공하면 대상 데이터를 서비스 DB에서 삭제합니다. 프로젝트·계정에 연결된 기록도 해당 삭제 범위에 따라 함께 처리합니다. 화면에서 숨기는 기능과 데이터 삭제는 구분됩니다.</p>
          <p>분석이 진행 중이면 삭제가 제한될 수 있습니다. 관리자 계정은 일반 계정 탈퇴 기능으로 삭제할 수 없습니다. 실패 안내가 표시되면 삭제 완료로 간주하지 않으며, 중단된 삭제는 남은 데이터에 대해 다시 요청할 수 있습니다.</p>
          <p>운영 DB의 삭제와 외부 로그·백업 사본의 삭제는 같은 절차가 아닙니다. 백업 파기 방법·반영 주기와 별도 보존이 필요한 경우의 근거·기간은 확인 후 이 방침에 반영해야 합니다.</p>
        </section>
        <section id="privacy-providers" aria-labelledby="privacy-providers-heading">
          <h2 id="privacy-providers-heading">외부 서비스 이용</h2>
          <p>현재 확인한 외부 처리 경로는 아래와 같습니다. 단순히 외부 업체를 사용한다는 사실만으로 위탁·제3자 제공의 법적 구분이나 국외 보유 기간이 확정되는 것은 아닙니다.</p>
          <table aria-label="외부 서비스 처리 현황"><thead><tr><th scope="col">서비스</th><th scope="col">처리 목적·전달 정보</th><th scope="col">발생 시점·방식</th></tr></thead><tbody>
            <tr><th scope="row">Google 로그인</th><td>계정 인증. Google이 확인한 이메일·계정 식별자를 서비스가 받으며 인증 요청·응답을 처리</td><td>사용자가 Google 로그인을 시작할 때 HTTPS 인증 통신</td></tr>
            <tr><th scope="row">Google Cloud · 서비스 DB</th><td>웹/API 실행, 계정·프로젝트·대화·설정 저장, 접속·운영 로그 처리</td><td>서비스 요청과 저장 시 처리. DB 사업자·리전·백업 계약의 세부 내역은 확정 필요</td></tr>
            <tr><th scope="row">OpenRouter · 연결 모델 제공자</th><td>분석·답변 생성. 질문, 분석에 쓰는 이전 대화·사용 조건·회로 정보·첨부에서 추출한 내용·문서 조각 등</td><td>분석 요청 중 필요한 단계에서 HTTPS API로 전송. <a href="https://openrouter.ai/privacy" target="_blank" rel="noreferrer">OpenRouter 정책</a> · <a href="https://openrouter.ai/docs/guides/privacy/provider-logging" target="_blank" rel="noreferrer">모델 제공자별 처리 기준</a></td></tr>
            <tr><th scope="row">Voyage AI</th><td>의미 검색·검색 결과 정렬. 검색 질문·관련 문서 조각, 설정 검색을 켠 경우 내 설정 문장 등</td><td>검색·설정 저장/검색이 필요한 때 HTTPS API로 전송. <a href="https://www.voyageai.com/privacy" target="_blank" rel="noreferrer">Voyage AI 정책</a></td></tr>
            <tr><th scope="row">Langfuse</th><td>실행 추적. 사용자·대화/추적 식별자, 단계·모델·토큰·비용·시간·오류 유형 등 메타데이터</td><td>추적 기능이 켜진 분석 실행 중 전송. 서비스 경로는 내보내기 전에 질문·답변·검색값 등 본문을 제거</td></tr>
          </tbody></table>
          <p>실제 수탁·제공받는 법인명과 연락처, 재위탁, 각 보관 기간과 적용 계약은 확인 후 공개해야 합니다. 외부 사업자의 일반 공개 정책만으로 우리 서비스 계정의 적용 조건을 단정하지 않습니다.</p>
        </section>
        <section id="privacy-overseas" aria-labelledby="privacy-overseas-heading">
          <h2 id="privacy-overseas-heading">국외 이전</h2>
          <p>위 외부 API·클라우드 이용에는 국외 처리 여부 확인이 필요합니다. 서버의 실행 리전이나 사업자의 본사 주소만으로 실제 처리·저장 국가를 확정하지 않습니다.</p>
          <p>이전의 법적 근거, 실제 이전받는 자와 연락처, 국가, 이전 항목, 시기·방법, 목적, 보유·이용 기간, 거부 방법과 효과는 계약·계정 설정을 대조한 뒤 확정해야 합니다. 로그인·가입 화면의 별도 동의 체크는 사용하지 않으며, 이를 법적 고지가 모두 완료된 것으로 간주하지 않습니다.</p>
        </section>
        <section id="privacy-ai" aria-labelledby="privacy-ai-heading">
          <h2 id="privacy-ai-heading">AI 분석과 추적</h2>
          <p>채팅의 NET·TXT 첨부는 서버에서 읽으며 원본 파일은 저장하지 않습니다. 정규화한 연결 정보와 추출한 텍스트는 분석 입력으로 전달되고 기존 분석 기록의 보유·삭제 정책을 따릅니다.</p>
          <p>AI는 회로와 질문의 맥락을 읽고 대체 후보 검토에 필요한 분석·설명을 생성합니다. 입력한 글이나 회로에 개인정보가 포함되면 필요한 분석 입력과 함께 외부 처리 경로로 전달될 수 있습니다. 분석과 관계없는 개인 식별정보·민감정보는 입력하지 않는 것이 좋습니다.</p>
          <p>서비스 운영 코드에는 사용자 대화를 별도 모델 학습 데이터로 적재하는 절차가 없습니다. 다만 외부 업체의 학습 이용·로그 저장·보유 기간은 연결 모델과 계정 옵션·계약에 따라 달라질 수 있습니다. 해당 설정을 확인하지 않은 상태에서 학습 미사용이나 무보관을 보장하지 않습니다.</p>
        </section>
        <section id="privacy-storage" aria-labelledby="privacy-storage-heading">
          <h2 id="privacy-storage-heading">쿠키와 브라우저 저장</h2>
          <table aria-label="쿠키와 브라우저 저장 정보"><thead><tr><th scope="col">항목</th><th scope="col">목적·기간</th></tr></thead><tbody>
            <tr><th scope="row">sojafit_session</th><td>로그인 유지용 쿠키. 최대 8시간이며 서버에서 유휴 2시간 제한도 검사합니다. 운영 HTTPS에서 Secure·HttpOnly·SameSite 속성을 적용합니다.</td></tr>
            <tr><th scope="row">sojafit_google_browser</th><td>Google 인증의 브라우저 확인. 최대 10분이며 인증 완료·실패 처리 시 삭제합니다. 별도 동의 쿠키는 발급하지 않습니다.</td></tr>
            <tr><th scope="row">브라우저 로컬 저장소</th><td>사용자·프로젝트별 대화 고정 식별자와 이미 저장된 동작 효과 설정. 브라우저 사이트 데이터를 지울 때까지 남을 수 있으며 서버 계정 삭제·로그아웃만으로 모두 지워진다고 보장하지 않습니다.</td></tr>
          </tbody></table>
          <p>브라우저의 개인정보·사이트 데이터 설정에서 쿠키와 로컬 저장 정보를 삭제하거나 저장을 차단할 수 있습니다. 쿠키를 차단하면 로그인과 인증 유지가 제한될 수 있습니다.</p>
        </section>
        <section id="privacy-rights" aria-labelledby="privacy-rights-heading">
          <h2 id="privacy-rights-heading">이용자 권리와 행사 방법</h2>
          <p>본인의 개인정보에 대한 열람·정정·삭제·처리정지와 동의 철회를 요청할 수 있습니다. 서비스에서 직접 처리할 수 있는 항목은 다음과 같습니다.</p>
          <ul><li>프로젝트·대화: 작업대의 삭제 기능으로 요청</li><li>소속·직무·선호 실장 방식: ‘내 설정 관리’에서 조회·수정·항목 삭제</li><li>일반 계정 탈퇴: ‘내 설정 관리’의 계정 삭제 기능으로 요청. 진행 중 분석·관리자 계정 제한은 화면 안내에 따름</li></ul>
          <p>그 밖의 열람·처리정지·대리인 요청과 고충 처리를 받을 담당 창구는 아직 확정되지 않았습니다. 담당 연락처와 본인·대리인 확인 절차를 정식 공개 전에 마련해야 합니다.</p>
          <p>외부 권리 구제 안내: <a href="https://privacy.kisa.or.kr/" target="_blank" rel="noreferrer">개인정보침해 신고센터</a> · <a href="https://www.kopico.go.kr/" target="_blank" rel="noreferrer">개인정보분쟁조정위원회</a></p>
        </section>
        <section id="privacy-security" aria-labelledby="privacy-security-heading">
          <h2 id="privacy-security-heading">안전조치</h2>
          <p>HTTPS 통신, 비밀번호 해시, 보호 속성이 적용된 세션 쿠키, 로그인 시도 제한, 사용자별 소유권 확인과 관리자 권한 구분을 적용합니다. 서비스 분석 추적은 본문을 제외하도록 처리합니다.</p>
          <p>DB·백업의 저장 암호화, 실제 접근권한 운영, 외부 로그의 보관·삭제 등은 각각의 운영 설정과 계약을 확인해야 합니다. 구현 일부만으로 모든 보안 조치가 검증됐다고 표시하지 않습니다.</p>
        </section>
        <section id="privacy-contact" aria-labelledby="privacy-contact-heading">
          <h2 id="privacy-contact-heading">담당자와 문의</h2>
          <dl className="privacy-contact"><div><dt>개인정보처리자 · 운영자</dt><dd>확정 후 기재</dd></div><div><dt>보호책임자 또는 담당부서</dt><dd>확정 후 기재</dd></div><div><dt>개인정보 문의 연락처</dt><dd>확정 후 기재</dd></div></dl>
          <aside className="privacy-pending" role="region" aria-label="공개 전 확정할 항목"><h3>공개 전 확정할 항목</h3><ul><li>운영자·담당부서·실제 문의 창구와 권리 행사 절차</li><li>처리 근거, 수탁·제공 구분과 계약, 국외 이전의 필수 고지 항목</li><li>클라우드 로그·백업·외부 추적의 보관 기간과 삭제 반영 주기</li><li>14세 미만 아동 대상 제공 여부와 필요한 연령·보호자 확인 절차. 현재 연령 확인·보호자 동의 기능은 없음</li><li>시행일, 변경 고지와 이전 방침 열람 경로</li></ul></aside>
        </section>
        <section id="privacy-changes" aria-labelledby="privacy-changes-heading">
          <h2 id="privacy-changes-heading">방침 변경</h2>
          <p>시행일과 변경 고지 방식은 운영자가 확정한 뒤 표시합니다. 검토 기준일은 시행일이나 동의 완료일을 뜻하지 않습니다. 이 검토본은 실제 처리 내용·계약 확인과 운영자 검토를 거쳐 보완해야 합니다.</p>
          <p className="privacy-source">작성 참고: <a href="https://pipc.go.kr/np/cop/bbs/selectBoardArticle.do?bbsId=BS217&amp;nttId=12018" target="_blank" rel="noreferrer">개인정보보호위원회 「개인정보 처리방침 작성지침」(2026.4.)</a>. 지침의 구성과 실제 서비스 처리 코드를 대조해 작성했으며, 법적 적합성 인증을 받은 문서는 아닙니다.</p>
        </section>
      </div>
      </div>
      <p className="privacy-return"><Link to="/">서비스 소개로 돌아가기</Link></p>
    </article>
  </div>
}
