import '@fontsource-variable/noto-sans-kr'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import AccessibleDialog from '../components/AccessibleDialog'

const steps = [
  { title: '회로와 부품 선택', image: 'landing-guide-project.png', alt: '현재 프로젝트 만들기 창의 넷리스트 첨부와 파일로 만들기', description: '현재 프로젝트 옆 +에서 넷리스트를 첨부하세요. 생성 후 현재 프로젝트를 눌러 분석할 부품을 선택합니다.' },
  { title: '질문에 조건 입력', image: 'landing-guide-question.png', alt: '현재 작업대의 질문 한 칸과 선택 부품의 연결 개념도', description: '전압·전류·기판 수정 여부를 질문에 함께 적으세요. 부족한 값은 추가 입력으로 답합니다.' },
  { title: '판정과 근거 확인', image: 'landing-guide-evidence.png', alt: '현재 작업대의 답변과 데이터시트 문서 근거 패널', description: '답변의 후보 비교·문서 근거로 상세를 여세요. 견적은 판정을 확인하고 승인한 뒤 저장합니다.' },
]
// R1 #27, 2026-11-04: quality on 38 test questions; retrieve latency on 103 calls.
const metrics = [
  { id: 'recall', value: '93.42', unit: '%', label: '근거 회수율' },
  { id: 'all-evidence', value: '92.11', unit: '%', label: '필요한 근거 모두 검색' },
  { id: 'latency', value: '1.18', unit: '초', label: '검색 중앙값' },
]

export default function LandingPage() {
  const { user } = useAuth()
  const start = user ? '/app' : '/login'
  const [expanded, setExpanded] = useState<(typeof steps)[number] | null>(null)
  return <div className="public-site landing-page">
    <header className="public-header"><Link className="public-brand" to="/#top"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link>
      <nav aria-label="서비스 안내"><a href="#service">서비스 소개</a><a href="#how-it-works">사용 방법</a>{!user && <Link to="/login">로그인</Link>}</nav>
    </header>
    <section className="public-hero" id="top" aria-labelledby="landing-heading">
      <div className="public-intro">
        <h1 id="landing-heading">회로를 읽고,<br />대체 부품을 검토하세요.</h1>
        <p className="public-lead">KiCad 넷리스트와 사용 조건으로<br />후보의 판정과 데이터시트 근거를 함께 확인하세요.</p>
        <Link className="public-primary public-start" to={start}>회로 검토 시작</Link>
        <p className="public-caption">소형 MCU 회로의 다이오드부터 · 같은 동작은 보장하지 않습니다.</p>
      </div>
    </section>
    <section id="service" className="landing-section landing-service" aria-label="서비스 소개" tabIndex={-1}>
      <dl className="landing-stats" aria-label="검색 실측 요약">
        {metrics.map(metric => <div key={metric.id} data-metric={metric.id}><dt>{metric.label}</dt><dd><strong>{metric.value}</strong><span>{metric.unit}</span></dd></div>)}
      </dl>
      <p className="landing-measurement-note">2026.11.04 실측 · 품질 38문항 / 검색 시간 103회 · 답변 생성 시간 제외<br />과거 검색 실험이며 현재 운영 답변 정확도를 뜻하지 않습니다.</p>
      <details className="landing-measurement-details"><summary>측정 조건과 지표</summary><p>상위 5개 검색 결과를 기준으로, 근거 회수율은 필요한 정답 페이지 중 찾은 비율의 문항별 평균입니다. 필요한 근거 모두 검색은 정답 페이지를 모두 찾은 문항 비율(35/38)입니다.</p><p>검색 중앙값은 R1 84문항과 v2 19문항, 총 103회 retrieve() 호출에서 잰 1.176초를 반올림했습니다. 별도 질의 재작성과 최종 답변 생성 시간은 포함하지 않습니다.</p><p>설정: voyage-4-large · 고정 재작성 질의 · 품번+카드 종류 필터 · 비트 후보 3,200개+정확 재정렬 · rerank-3.<br />출처: 사전 등록 #27<br /><code>evals/results/retrieval/service_r1_bits_2026-11-04.json</code></p></details>
    </section>
    <section id="how-it-works" className="landing-section landing-how" aria-labelledby="how-heading" tabIndex={-1}>
      <div className="landing-section-heading"><h2 id="how-heading">사용 방법</h2><p>회로를 등록하고, 질문하고, 근거를 확인하세요.</p></div>
      <ol className="landing-guides" aria-label="사용 단계">
        {steps.map((step, index) => <li className="landing-guide-step" key={step.title}>
          <div className="landing-guide-copy"><span className="landing-step-number" aria-hidden="true">{String(index + 1).padStart(2, '0')}</span><h3>{step.title}</h3><p>{step.description}</p></div>
          <figure className="landing-screen">
            <button type="button" className="landing-screen-button" aria-label={step.title + ' 화면 크게 보기'} onClick={() => setExpanded(step)}><img src={'/assets/' + step.image} alt={step.alt} width="1440" height="1000" loading="lazy" /></button>
            <figcaption><span>화면을 누르면 크게 볼 수 있습니다.</span><span>예시 데이터 · 실제 분석 결과가 아닙니다.</span></figcaption>
          </figure>
        </li>)}
      </ol>
      <p className="landing-limitation">회로 등록은 프로젝트의 넷리스트 첨부를 사용하세요.</p>
    </section>
    <footer className="public-footer"><div><h2>최종 선택은 근거를 확인한 뒤에.</h2><p>같은 동작은 보장하지 않습니다. 실제 사용 전 회로 조건과 부품 문서를 확인하세요.</p></div><nav className="public-legal" aria-label="서비스 정책"><Link to="/privacy">개인정보처리방침</Link></nav></footer>
    {expanded && <AccessibleDialog title={expanded.title} className="landing-image-dialog" onClose={() => setExpanded(null)}><p>현재 개발 화면 · 예시 데이터. 가로·세로로 이동해 확인하세요.</p><div className="landing-image-scroll" tabIndex={0} role="region" aria-label={expanded.title + ' 확대 화면'}><img src={'/assets/' + expanded.image} alt={expanded.alt} width="1440" height="1000" /></div></AccessibleDialog>}
  </div>
}
