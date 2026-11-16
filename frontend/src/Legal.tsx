/** 화면 맨 아래 고지 한 줄(이용약관·개인정보처리방침·AI 이용 안내·출처·라이선스·문의·©)과 그 문서들(#27). 보통 클릭은 작은 창으로 열고, 주소로 바로 열면 페이지가 된다. */
import { useState } from 'react';
import { contactEmail, PrivacyText } from './Account';
import { Brand, Modal, plainClick } from './ui';
// [왜] 순서가 곧 하단 줄의 순서다. 경로 표(App.tsx)도 이 키로 공개 경로를 가린다
const docs: Record<string, { title: string; body: () => React.ReactNode }> = {
  '/terms': { title: '이용약관', body: Terms },
  '/privacy': { title: '개인정보처리방침', body: PrivacyText },
  '/ai-notice': { title: 'AI 이용 안내', body: AiNotice },
  '/licenses': { title: '출처·라이선스', body: Licenses },
};
export const isLegalPath = (path: string) => Object.hasOwn(docs, path);
/** 고지 문서 주소로 바로 들어왔을 때의 페이지. */
export function LegalPage({ path }: { path: string }) {
  const doc = docs[path];
  return (
    <div className="legal-page">
      <Brand />
      <main>
        <h1>{doc.title}</h1>
        <doc.body />
      </main>
      <Footer />
    </div>
  );
}
function LegalLink({ path }: { path: string }) {
  const [open, setOpen] = useState(false),
    doc = docs[path];
  return (
    <>
      <a
        href={path}
        onClick={(e) => {
          if (!plainClick(e)) return;
          e.preventDefault(); // [주의] 문서 전체 링크 위임(followLink)이 이 클릭을 페이지 이동으로 바꾸지 않게 한다
          setOpen(true);
        }}
      >
        {/* [왜] 개인정보처리방침은 국내 관행대로 굵게 보인다 */}
        {path === '/privacy' ? <strong>{doc.title}</strong> : doc.title}
      </a>
      {open && (
        <Modal title={doc.title} close={() => setOpen(false)}>
          <doc.body />
        </Modal>
      )}
    </>
  );
}
/** 랜딩·로그인 계열 화면 맨 아래 한 줄. compact는 사이드바 맨 아래용(좁아서 줄을 바꿈). */
export function Footer({ compact = false }: { compact?: boolean }) {
  return (
    // [왜] <nav>로 감싸지 않는다. 사이드바의 `.sidebar nav a`(메뉴 단추 모양)가 이 링크에 걸린다
    <footer className={compact ? 'site-footer compact' : 'site-footer'}>
      {Object.keys(docs).map((path) => (
        <LegalLink key={path} path={path} />
      ))}
      <a href={'mailto:' + contactEmail}>문의</a>
      <small>© 2026 SojaFit</small>
    </footer>
  );
}
function Terms() {
  return (
    <div className="legal-text">
      <p>이 약관은 SojaFit(이하 "서비스")을 이용하는 조건을 정합니다. 시행일: 2026년 11월 16일.</p>
      <h2>1. 서비스의 성격</h2>
      <p>
        서비스는 회로(넷리스트)와 데이터시트를 근거로 부품 대체 후보를 검토하는 참고 도구입니다.
        판정은 데이터시트에 적힌 값과 회로 조건을 비교한 결과이며, 같은 동작은 보장하지 않습니다.
        실제 회로에 적용하기 전에 사용 조건, 패키지·기판, 시험 결과를 이용자가 직접 확인해야 합니다.
      </p>
      <h2>2. 계정</h2>
      <p>
        본인 이메일로 가입하고 비밀번호와 로그인 상태를 스스로 관리합니다. 계정을 다른 사람과 함께
        쓰거나 넘기지 않습니다. 도용이 의심되면 바로 문의해 주세요. 탈퇴는 내 설정에서 언제든 할 수
        있습니다.
      </p>
      <h2>3. 금지 행위</h2>
      <ul>
        <li>다른 사람의 계정을 쓰거나 인증을 우회하는 행위</li>
        <li>
          프로그램으로 화면이나 API를 대량 수집(스크래핑)하거나 지나치게 많은 요청을 보내는 행위
        </li>
        <li>서버나 다른 이용자를 공격하거나 보안 취약점을 악용하는 행위</li>
        <li>올릴 권리가 없는 자료를 올리거나 법령을 어기는 행위</li>
      </ul>
      <p>이런 행위가 확인되면 이용을 제한하거나 계정을 비활성화할 수 있습니다.</p>
      <h2>4. 이용자가 올린 자료</h2>
      <p>
        넷리스트와 질문 등 이용자가 올린 자료의 권리는 이용자에게 있습니다. 서비스는 그 자료를 검토
        결과를 만들고 저장·표시하는 데에만 씁니다. 보관과 삭제는 개인정보처리방침을 따릅니다.
      </p>
      <h2>5. 데이터시트와 외부 자료</h2>
      <p>
        데이터시트, 가격·재고, 공개 회로도의 권리는 각 출처에 있습니다. 출처와 이용 조건은
        「출처·라이선스」에 적었습니다.
      </p>
      <h2>6. 서비스 변경과 중단</h2>
      <p>
        기능은 바뀔 수 있고, 점검·장애·외부 서비스 사정으로 서비스를 잠시 또는 완전히 멈출 수
        있습니다. 미리 알릴 수 있으면 서비스 화면에 알립니다.
      </p>
      <h2>7. 책임의 제한</h2>
      <p>
        서비스는 고의 또는 중대한 과실이 없는 한, 판정·답변을 근거로 한 부품 선택·설계·구매의 결과와
        외부 서비스 장애로 생긴 손해에 책임지지 않습니다.
      </p>
      <h2>8. 약관 변경과 문의</h2>
      <p>
        약관을 바꾸면 시행일과 바뀐 내용을 이 화면에 알립니다. 문의:{' '}
        <a href={'mailto:' + contactEmail}>{contactEmail}</a>
      </p>
    </div>
  );
}
function AiNotice() {
  return (
    <div className="legal-text">
      <p>
        「인공지능 발전과 신뢰 기반 조성 등에 관한 기본법」(AI 기본법) 제31조에 따라, 이 서비스가
        생성형 AI를 쓴다는 것을 알립니다.
      </p>
      <h2>AI가 하는 일</h2>
      <p>
        대화에 보이는 답변과 설명 글은 생성형 AI를 이용해 만듭니다. AI는 질문을 이해해 할 일을
        정하고, 데이터시트에서 필요한 값을 찾아 읽고, 설명 글을 씁니다. 대화의 답에는 "AI 생성"
        표시가 붙습니다.
      </p>
      <h2>코드가 하는 일</h2>
      {/* [주의] AGENTS.md 지킬 것 7, SPEC 2절 답 조립의 출력 경계·6절 신뢰 경계와 맞춘다 */}
      <p>
        판정 5종(동일품·사양 동등·역할상 충분·불충족·문서로 확인 안 됨)과 숫자·단위 비교는 AI 모델이
        아니라 정해진 규칙의 코드가 계산합니다. 판정 답의 조건 표와 인용도 코드가 정한 틀로
        만듭니다. 인용 번호가 붙은 설명 문장의 숫자가 인용한 문서에 없으면 코드가 그 문장을 빼거나
        답을 거절합니다.
      </p>
      <h2>확인할 것</h2>
      <p>
        AI가 쓴 글은 틀릴 수 있습니다. 답에 붙은 데이터시트의 쪽·표를 직접 확인하세요. 같은 동작은
        보장하지 않습니다.
      </p>
      <h2>쓰는 외부 AI·검색 서비스</h2>
      <ul>
        <li>OpenRouter를 거친 Anthropic Claude 모델(Haiku·Sonnet): 질문 이해, 값 읽기, 설명 글</li>
        <li>Voyage AI(voyage-4-large, rerank-3): 문서 검색과 순위 매기기</li>
        <li>Exa: 공식 데이터시트와 공개 회로도 웹 검색</li>
      </ul>
      <p>
        계정 이메일과 내 설정의 소속·직무는 AI 모델에 보내지 않습니다. 보내는 정보는
        개인정보처리방침에 적었습니다.
      </p>
    </div>
  );
}
function Licenses() {
  return (
    <div className="legal-text">
      <h2>데이터시트</h2>
      {/* 출처: SPEC 6절 이용 조건(TSC 약관 3절 b항, Infineon 약관 11-02 확인) */}
      <ul>
        <li>
          Taiwan Semiconductor(TSC): 검색에 쓰는 데이터시트입니다. 사이트 약관에 따라 정보·비상업
          목적으로, 원본을 고치지 않고 저작권 고지와 출처를 유지합니다. 답의 인용에는
          문서·개정판·쪽과 원본 PDF 주소를 붙입니다.
        </li>
        <li>
          Infineon Technologies AG: 공식 데이터시트 웹 근거입니다. 같은 조건(정보·비상업 목적, 원본
          그대로, 저작권 표시·출처 유지)을 따르고 원본 링크와 출처를 붙입니다.
        </li>
      </ul>
      <h2>가격·재고</h2>
      <p>
        Mouser Electronics의 Search API로 조회한 값입니다. Mouser 약관에 따라 저장하지 않고, 조회
        시각과 출처를 붙여 그때만 보여 줍니다.
      </p>
      <h2>회로도</h2>
      <p>
        예제 회로와 원본 회로도는 그림 옆에 출처·라이선스·원본 링크를 함께 보입니다. KiCad 원본
        회로도는 KiCad(GPL-3.0-or-later)의 kicad-cli를 고치지 않고 별도 변환 서비스에서 실행해
        그림으로 바꿉니다.
      </p>
      <h2>오픈소스 소프트웨어</h2>
      {/* 출처: frontend/package.json · pyproject.toml 패키지의 license 메타데이터(11-16 확인) */}
      <p>
        화면: React·React DOM·react-markdown·remark-gfm·Vite(MIT), Lucide 아이콘(ISC), Noto Sans KR
        글꼴(OFL-1.1)
      </p>
      <p>
        서버: FastAPI·Pydantic·LangGraph·LangChain OpenAI·Langfuse SDK·MCP
        SDK·pgvector·pdfplumber·PyYAML(MIT), Uvicorn·HTTPX·Authlib·joserfc(BSD-3-Clause), OpenAI
        Python SDK·rank-bm25·python-multipart(Apache-2.0), psycopg(LGPL-3.0-only),
        CairoSVG(LGPL-3.0-or-later), Pillow(MIT-CMU), pypdfium2(BSD-3-Clause·Apache-2.0)
      </p>
      <p>각 라이선스 전문은 해당 패키지에 들어 있습니다.</p>
    </div>
  );
}
