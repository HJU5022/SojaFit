export default function LandingServiceIntroduction({ onStart }: { onStart: () => void }) {
  return <div className="landing-services">
    <div className="service-trace" aria-hidden="true" />

    <article className="service-feature">
      <div className="service-copy">
        <span className="service-kicker">회로 맥락</span>
        <h2>회로 안에서 역할을 먼저 봅니다</h2>
        <p>부품 하나만 떼어 보지 않고, 연결된 넷과 주변 부품을 함께 확인합니다. 대체 후보가 원래 부품의 역할을 이어갈 수 있는지 판단할 출발점입니다.</p>
        <ul className="service-points"><li>대상 부품과 직접 연결 표시</li><li>주변 부품과 넷 관계 확인</li></ul>
      </div>
      <div className="service-visual circuit-preview" aria-hidden="true">
        <div className="preview-toolbar"><span>교체 대상 부품 주변 연결</span><span className="preview-status">역할 확인</span></div>
        <div className="preview-circuit-grid">
          <span className="preview-wire wire-a" /><span className="preview-wire wire-b" /><span className="preview-wire wire-c" />
          <span className="preview-node node-c1">C1<small>+5V</small></span>
          <span className="preview-node node-f1">F1</span>
          <span className="preview-node node-u1 target">U1<small>LM7805</small></span>
          <span className="preview-node node-d1">D1<small>1N4001</small></span>
          <span className="preview-node node-s1">S1</span>
        </div>
        <div className="preview-footer"><strong>대상 U1</strong><span>전압 조절 역할과 주변 연결을 함께 확인</span></div>
      </div>
    </article>

    <article className="service-feature reverse">
      <div className="service-copy">
        <span className="service-kicker">후보와 근거</span>
        <h2>후보와 근거를 한 화면에서 비교합니다</h2>
        <p>전기 조건과 패키지 검토 결과를 후보별로 나란히 보고, 판단에 사용한 데이터시트 위치까지 이어서 확인합니다.</p>
        <ul className="service-points"><li>후보별 판정과 점검 항목 비교</li><li>데이터시트 출처와 근거 위치 확인</li></ul>
      </div>
      <div className="service-visual comparison-preview" aria-hidden="true">
        <div className="preview-toolbar"><span>후보 비교</span><span>근거</span></div>
        <div className="candidate-row candidate-head"><span>후보</span><span>판정</span><span>확인 항목</span></div>
        <div className="candidate-row selected"><strong>SS34</strong><span className="verdict-chip">역할상 충분</span><span>전기 조건 · 패키지</span></div>
        <div className="candidate-row"><strong>1N5819</strong><span>조건부</span><span>정격 확인</span></div>
        <div className="evidence-strip"><span>데이터시트 근거</span><strong>SS34.pdf</strong><small>Electrical Characteristics</small></div>
      </div>
    </article>

    <article className="service-feature">
      <div className="service-copy">
        <span className="service-kicker">사람 승인</span>
        <h2>마지막 결정은 사람이 내립니다</h2>
        <p>분석 결과와 근거를 확인한 뒤 승인할 후보를 직접 선택합니다. 승인된 결과는 필요한 수량을 담은 견적으로 이어집니다.</p>
        <ul className="service-points"><li>후보와 판정을 다시 확인한 뒤 승인</li><li>승인 결과에서 수량 기반 견적 작성</li></ul>
      </div>
      <div className="service-visual approval-preview" aria-hidden="true">
        <div className="approval-flow">
          <div className="approval-step complete"><span>1</span><div><small>분석 결과</small><strong>SS34 · 역할상 충분</strong></div></div>
          <div className="approval-step complete"><span>2</span><div><small>근거 검토</small><strong>데이터시트 확인</strong></div></div>
          <div className="approval-step active"><span>3</span><div><small>사람 승인</small><strong>후보와 판정 확인</strong></div></div>
          <div className="approval-step"><span>4</span><div><small>견적</small><strong>수량 입력</strong></div></div>
        </div>
        <div className="approval-summary"><span>승인할 후보</span><strong>SS34</strong><span className="preview-action">확인 후 승인</span></div>
      </div>
    </article>

    <section className="landing-final-cta" aria-labelledby="landing-final-heading">
      <span className="eyebrow">SOJAFIT 분석 흐름</span>
      <h2 id="landing-final-heading">회로에서 시작해, 근거로 결정하세요</h2>
      <p>교체하려는 부품과 사용 조건을 적으면 첫 단계부터 시작할 수 있습니다.</p>
      <button type="button" onClick={onStart}>질문 입력하기</button>
    </section>
  </div>
}
