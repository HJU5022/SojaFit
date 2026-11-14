import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { CandidateDto } from '../api/conversations'
import { useAuth } from '../auth/AuthProvider'
import { Checks } from '../components/ReviewDetails'
import { VERDICT_LABELS, VERDICT_TONE } from '../lib/judgement'

// 첫 화면의 예시. 작업대와 같은 표 컴포넌트에 넣어 실제 결과 화면과 똑같이 보이게 한다.
const SOURCE = 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf'
const SAMPLE = {
  part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: true,
  checks: [
    { code: 'VRRM', op: '>=', basis: '입력 최대 전압 12 V × 안전 여유 1.25', value: 40, threshold: 15, unit: 'V', result: 'pass',
      citation: { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'VRRM', source_url: SOURCE } },
    { code: 'IF_AV', op: '>=', basis: '최대 순방향 전류 1 A × 안전 여유 1.43', value: 3, threshold: 1.43, unit: 'A', result: 'pass',
      citation: { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'IF(AV)', source_url: SOURCE } },
  ],
} as unknown as CandidateDto

// 판정의 뜻은 SPEC 3절의 정의를 옮긴 것이다.
const VERDICTS: [CandidateDto['verdict'], string][] = [
  ['IDENTICAL', '같은 품번이거나, 제조사가 같은 제품이라고 밝힌 품번입니다.'],
  ['SPEC_EQUIVALENT', '품번은 다르지만 원래 부품의 주요 정격을 모두 같거나 넘습니다.'],
  ['ROLE_SUFFICIENT', '원래 정격에는 못 미치지만 이 회로에서 맡은 역할의 필수 조건은 모두 만족합니다.'],
  ['NOT_SUFFICIENT', '필수 조건이 하나라도 만족하지 않습니다.'],
  ['NOT_VERIFIED', '필요한 값이 문서에 없거나 시험 조건이 다릅니다. 추측으로 채우지 않습니다.'],
]
// 값은 EVAL_REPORT.md 1절·1-1절의 측정값이다. 판정 일치는 재측정 뒤에 이 구역 맨 앞에 넣는다.
const PARSERS: [string, number][] = [['SojaFit이 쓰는 파서', 41], ['pdfplumber', 36], ['pdftotext', 33], ['PyMuPDF', 23], ['pypdf', 22]]
const RING = 2 * Math.PI * 52

export default function LandingPage() {
  const { user } = useAuth()
  const start = user ? '/app' : '/login'
  return <div className="landing">
    <header className="land-nav"><Link className="brand" to="/"><img src="/assets/sojafit-icon.svg" alt="" width="24" height="24" />SojaFit</Link>
      <Link className="btn" to={start}>{user ? '작업대 열기' : '로그인'}</Link></header>
    <main>
      <section className="land-hero" aria-labelledby="hero-title">
        <div className="land-pitch">
          <h1 id="hero-title">이 부품, 바꿔도 되는지 데이터시트로 확인합니다.</h1>
          <p>회로와 후보 부품을 알려 주면 다섯 가지 판정 중 하나로 답하고, 그 판정에 쓴 데이터시트의 쪽과 표, 행을 함께 보여 줍니다.</p>
          <div className="land-actions"><Link className="btn btn-primary btn-large" to={start}>시작하기<ArrowRight aria-hidden="true" /></Link><a className="btn btn-large" href="#how">쓰는 법 보기</a></div>
        </div>
        <figure className="land-sample">
          <p className="land-question"><span>질문</span>입력 12 V, 1 A에서 D1(1N4001)을 SS34L로 바꿔도 되나요?</p>
          <div className={`doc-head tone-${VERDICT_TONE[SAMPLE.verdict]}`}>
            <strong className={`verdict dot tone-${VERDICT_TONE[SAMPLE.verdict]}`}>{VERDICT_LABELS[SAMPLE.verdict]}</strong>
            <p className="land-swap"><span className="ref">D1</span><span>1N4001</span><ArrowRight aria-label="교체 후보" /><span>SS34L</span></p>
          </div>
          <Checks candidate={SAMPLE} resolved />
          <p className="caution">기판 수정이 필요합니다. Sub SMA 패키지의 풋프린트와 극성을 확인해야 합니다.</p>
          <figcaption className="fine">예시 화면입니다. 같은 동작은 보장하지 않습니다.</figcaption>
        </figure>
      </section>

      <section className="land-section" id="how" aria-labelledby="how-title">
        <header><span className="land-no">1</span><h2 id="how-title">쓰는 법</h2><p>세 단계면 첫 판정을 받습니다.</p></header>
        <ol className="land-steps">
          <li><h3>회로를 올립니다</h3><p>KiCad 넷리스트 파일을 올리면 부품과 연결을 읽어, 판정할 수 있는 다이오드를 골라 보여 줍니다.</p>
            <div className="land-frag"><span className="ref">D1</span><span>1N4001</span><span className="land-frag-end">판정 가능</span></div></li>
          <li><h3>부품을 고르고 묻습니다</h3><p>바꾸려는 후보 품번과 사용 조건을 평소 말하듯 적습니다. 빠진 값이 있으면 되묻습니다.</p>
            <div className="land-frag">12 V, 1 A에서 SS34L로 바꿔도 되나요?</div></li>
          <li><h3>판정과 근거를 받습니다</h3><p>조건마다 요구 값과 후보 값을 나란히 놓고, 그 값을 읽은 데이터시트 위치를 붙입니다.</p>
            <div className="land-frag"><span className="dot tone-sufficient">역할상 충분</span><span className="land-frag-end">1쪽 MAXIMUM RATINGS</span></div></li>
        </ol>
      </section>

      <section className="land-section" aria-labelledby="verdict-title">
        <header><span className="land-no">2</span><h2 id="verdict-title">답은 다섯 가지 중 하나입니다</h2><p>된다, 안 된다로 뭉개지 않습니다. 모르면 모른다고 답합니다.</p></header>
        <dl className="land-verdicts">{VERDICTS.map(([code, meaning]) => <div key={code}><dt><span className={`dot tone-${VERDICT_TONE[code]}`}>{VERDICT_LABELS[code]}</span></dt><dd>{meaning}</dd></div>)}</dl>
      </section>

      <section className="land-section" aria-labelledby="trust-title">
        <header><span className="land-no">3</span><h2 id="trust-title">왜 믿어도 되는가</h2><p>판정은 모델의 기억이 아니라, 데이터시트에서 읽은 값을 코드로 비교한 결과입니다.</p></header>
        <dl className="land-stats">
          <div><dt>판정에 쓰는 품번</dt><dd>9,589<small>개</small></dd></div>
          <div><dt>읽어 둔 데이터시트</dt><dd>1,360<small>건</small></dd></div>
          <div><dt>데이터시트 쪽수</dt><dd>7,725<small>쪽</small></dd></div>
          <div><dt>다이오드 분류</dt><dd>13<small>개</small></dd></div>
        </dl>
        <div className="land-charts">
          <figure className="land-chart land-ring">
            <svg width="128" height="128" viewBox="0 0 128 128" role="img" aria-label="표 숫자 93,947개 중 93,940개가 원문과 일치">
              <circle cx="64" cy="64" r="52" /><circle className="on" cx="64" cy="64" r="52" strokeDasharray={`${RING * 0.99993} ${RING}`} transform="rotate(-90 64 64)" />
            </svg>
            <div><strong>99.993%</strong><p>읽어 낸 표 숫자가 데이터시트 원문과 일치합니다.</p><small>93,947개 중 93,940개</small></div>
          </figure>
          <figure className="land-chart">
            <figcaption><strong>표에서 값과 그 뜻을 함께 읽어 낸 개수</strong><small>사람이 원문과 대조한 정답 41개 기준</small></figcaption>
            <ul className="land-bars">{PARSERS.map(([name, count], index) => <li key={name} className={index === 0 ? 'on' : undefined}>
              <span>{name}</span><span className="land-bar"><span style={{ width: `${(count / 41) * 100}%` }} /></span><span>{count}</span></li>)}</ul>
          </figure>
        </div>
        <p className="fine">Taiwan Semiconductor 다이오드 데이터시트 기준, 2026년 11월 측정입니다.</p>
      </section>

      <section className="land-section" aria-labelledby="limit-title">
        <header><span className="land-no">4</span><h2 id="limit-title">하지 않는 것</h2><p>할 수 있는 척하지 않는 것도 기능입니다.</p></header>
        <ul className="land-limits">
          <li><h3>같은 동작은 보장하지 않습니다</h3><p>판정은 데이터시트 값과 입력한 조건을 비교한 결과입니다. 실제 기판에서의 동작은 직접 확인해야 합니다.</p></li>
          <li><h3>지금은 다이오드만 판정합니다</h3><p>Taiwan Semiconductor 다이오드 데이터시트에 있는 품번만 다룹니다. 그 밖의 부품은 답하지 않습니다.</p></li>
          <li><h3>최종 승인은 사람이 합니다</h3><p>판정은 검토 자료입니다. 승인 버튼을 사람이 누르기 전에는 견적으로 넘어가지 않습니다.</p></li>
        </ul>
      </section>

      <section className="land-close" aria-labelledby="close-title"><h2 id="close-title">바꾸려는 부품이 있다면 지금 확인해 보세요.</h2>
        <Link className="btn btn-primary btn-large" to={start}>시작하기<ArrowRight aria-hidden="true" /></Link></section>
    </main>
    <footer className="land-foot"><span>SojaFit</span><Link to="/privacy">개인정보처리방침</Link></footer>
  </div>
}
