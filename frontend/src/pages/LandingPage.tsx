import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

export function CircuitPreview() {
  return <svg className="public-circuit" viewBox="0 0 300 195" role="img" aria-label="D1과 주변 부품의 합성 연결 개념 예시. 실제 회로도 아님.">
    <path d="M49 52 150 96 251 52M150 96v66" />
    <rect x="23" y="34" width="52" height="36" rx="5" /><text x="49" y="57">J1</text>
    <rect x="225" y="34" width="52" height="36" rx="5" /><text x="251" y="57">U1</text>
    <rect className="circuit-target" x="112" y="74" width="76" height="44" rx="7" /><text x="150" y="102">D1</text>
    <rect x="124" y="144" width="52" height="36" rx="5" /><text x="150" y="168">C1</text>
  </svg>
}

const features = [
  { id: 'context', icon: '⌁', title: '회로 맥락', detail: '대상과 주변 연결', scene: '대상 D1과 사용 조건을 먼저 확인합니다.' },
  { id: 'compare', icon: '≋', title: '후보 비교', detail: '판정과 기판 수정', scene: '후보별 판정과 기판 수정 여부를 나란히 검토합니다.' },
  { id: 'evidence', icon: '⌕', title: '문서 근거', detail: '쪽·표·행 확인', scene: '선택한 항목의 데이터시트 인용 위치를 확인합니다.' },
  { id: 'approval', icon: '✓', title: '사람 승인', detail: '검토 후 견적 저장', scene: '판정과 미확인 항목을 확인한 뒤 사람이 승인합니다.' },
]

export default function LandingPage() {
  const { user } = useAuth()
  const start = user ? '/app' : '/login'
  const [feature, setFeature] = useState(features[0])
  return <div className="public-site landing-page">
    <header className="public-header"><Link className="public-brand" to="/"><img className="brand-logo" src="/assets/sojafit-logo.svg" alt="SOJAFIT" width="174" height="48" /></Link>
      <nav aria-label="서비스 안내"><a href="#service">서비스 소개</a><a href="#workflow">사용 방법</a>
        {!user && <Link to="/login">로그인</Link>}<Link className="public-primary" to={start}>{user ? '작업대 열기' : '검토 시작'}</Link></nav>
    </header>
    <section className="public-hero" id="service" aria-labelledby="landing-heading">
      <h1 id="landing-heading">부품을 바꾸기 전에,<br />회로에 맞는지 확인하세요.</h1>
      <p className="public-lead">회로와 사용 조건에서 시작해,<br />대체 후보의 판정과 데이터시트 근거를 함께 검토하세요.</p>
      <div className="public-features" role="group" aria-label="SojaFit 사용 장면 미리보기">
        {features.map(item => <button key={item.id} className="public-feature" aria-pressed={feature.id === item.id} aria-controls="workflow" onClick={() => setFeature(item)}>
          <span aria-hidden="true">{item.icon}</span><strong>{item.title}</strong><small>{item.detail}</small>
        </button>)}
      </div>
      <Link className="public-primary public-start" to={start}>회로 검토 시작</Link>
      <p className="public-caption">KiCad 넷리스트로 시작(로컬 데모 모드에서는 샘플 회로도 가능)<br />첫 대상은 다이오드 · 같은 동작은 보장하지 않습니다.</p>
      <div className="public-product" id="workflow" data-feature={feature.id}>
        <div className="public-product-heading"><span aria-live="polite">{feature.scene}</span><span>합성 예시 화면</span></div>
        <div className="public-product-content">
          <section className="public-context"><h2>소형 전원 회로 / D1</h2><CircuitPreview /><p>12 V / 1 A / 60 °C</p><p>주변 연결 개념도</p></section>
          <section className="public-comparison"><h2>교체할 후보를 나란히 검토</h2><table aria-label="합성 후보 비교 예시">
            <thead><tr><th scope="col">후보</th><th scope="col">판정</th><th scope="col">기판 수정</th></tr></thead>
            <tbody><tr><td>후보 A</td><td>역할상 충분</td><td>필요</td></tr><tr><td>후보 B</td><td>문서로 확인 안 됨</td><td>미확인</td></tr><tr><td>후보 C</td><td>불충족</td><td>미확인</td></tr></tbody>
          </table></section>
          <section className="public-proof"><h2>선택 항목의 문서 근거</h2><p><strong>역전압 / VRRM</strong></p><p>기준 24 V 이상 / 후보값 40 V</p><p className="public-proof-pass">조건 충족 예시</p><p>후보 A 자료.pdf</p><p>2쪽 / 정격값 표 / VRRM</p><p>원문 대신 인용 위치 표시</p></section>
        </div>
        <div className="public-product-footer"><span>사양·기판 수정·미확인 항목 확인 후 사람 승인</span><Link to={start}>검토 화면 살펴보기</Link></div>
      </div>
    </section>
    <footer className="public-footer"><div><h2>판정과 근거를 보고, 직접 결정하세요.</h2><p>가격·재고는 별도로 조회하고, 견적은 승인 후 저장합니다.</p></div><Link className="public-secondary" to={start}>SojaFit 시작</Link></footer>
  </div>
}
