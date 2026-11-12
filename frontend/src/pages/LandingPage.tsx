import '@fontsource-variable/noto-sans-kr'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import LandingGuide from '../components/LandingGuide'

// R1 #27, 2026-11-04: quality on 38 test questions; retrieve latency on 103 calls.
const metrics = [
  { id: 'recall', value: '93.42', unit: '%', label: '근거 회수율' },
  { id: 'all-evidence', value: '92.11', unit: '%', label: '필요한 근거 모두 검색' },
  { id: 'latency', value: '1.18', unit: '초', label: '검색 중앙값' },
]

export default function LandingPage() {
  const { user } = useAuth()
  const start = user ? '/app' : '/login'
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
      <div className="landing-section-heading"><h2 id="how-heading">사용 방법</h2><p>궁금한 스텝을 누르면 그 자리에서 조작 과정을 확인할 수 있습니다.</p></div>
      <LandingGuide />
    </section>
    <footer className="public-footer"><div><h2>최종 선택은 근거를 확인한 뒤에.</h2><p>같은 동작은 보장하지 않습니다. 실제 사용 전 회로 조건과 부품 문서를 확인하세요.</p></div><nav className="public-legal" aria-label="서비스 정책"><Link to="/privacy">개인정보처리방침</Link></nav></footer>
  </div>
}
