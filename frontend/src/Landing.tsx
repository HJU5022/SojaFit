/** 제품 소개. 예시 수치는 기록된 데모 결과(data/demo/recordings/outcomes.json, 질문 v3-01)에서 옮긴 값이고 실시간 판정이 아니다. */
import { useEffect, useState } from 'react';
import { ArrowRight, FileText, MessageSquare, Check, ArrowUpRight } from 'lucide-react';
import { Brand, Badge, Disclaimer } from './ui';
export function Landing() {
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('revealed');
            observer.unobserve(e.target);
          }
        }),
      { threshold: 0.1 },
    );
    document
      .querySelectorAll(
        '.landing section>h2,.landing section>p,.how li,.guide-row,.limits>div,.product-proof figure',
      )
      .forEach((e) => {
        e.classList.add('reveal');
        observer.observe(e);
      });
    return () => observer.disconnect();
  }, []);
  const [basis, setBasis] = useState<'original' | 'role'>('role');
  return (
    <div className="landing">
      <header className="landing-nav">
        <Brand />
        <nav>
          <a href="#principle">판정 기준</a>
          <a href="#how">검토 과정</a>
          <a href="/login">
            로그인 <ArrowUpRight size={15} />
          </a>
        </nav>
      </header>
      <main>
        <section className="hero">
          <h1>
            부품은 바뀌어도,
            <br />
            판단에는 근거가.
          </h1>
          <p className="hero-copy">
            단종, 품절, 원가 때문에 다이오드를 바꿔야 할 때.
            <br className="desktop-only" /> 회로 역할과 데이터시트로 교체 후보를 검토하세요.
          </p>
          <a className="button primary" href="/login">
            내 회로 검토하기 <ArrowRight size={18} />
          </a>
          <div className="hero-sample">
            <div className="sample-top">
              <span>다이오드 교체 검토</span>
              <span>기록된 데모 결과 · v3-01</span>
            </div>
            <div className="sample-body">
              <div className="sample-circuit">
                <span>ATtiny85 Time Switch · D1 · 1N4007RLG</span>
                <svg viewBox="0 0 320 100" aria-label="D1 다이오드 교체 예시 연결" role="img">
                  <path
                    d="M20 50h105m70 0h105M125 20v60l70-30-70-30Zm70 0v60"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                  <text x="20" y="90">
                    15 V
                  </text>
                  <text x="265" y="90">
                    0.12 A
                  </text>
                </svg>
                <p>D1을 TSC 1N4007G로 바꿔도 될까요?</p>
              </div>
              <div className="sample-verdict">
                <div>
                  <strong>1N4007G</strong>
                  <Badge verdict="ROLE_SUFFICIENT" />
                </div>
                <p>회로가 요구하는 전압·전류 조건을 만족합니다.</p>
                <dl>
                  <div>
                    <dt>역전압</dt>
                    <dd>
                      18.75 V 이상 <ArrowRight size={14} /> <b>1000 V</b>
                      <Check size={16} />
                    </dd>
                  </div>
                  <div>
                    <dt>순방향 전류</dt>
                    <dd>
                      0.171 A 이상 <ArrowRight size={14} /> <b>1 A</b>
                      <Check size={16} />
                    </dd>
                  </div>
                  <div>
                    <dt>서지 전류</dt>
                    <dd>
                      2 A 이상 <ArrowRight size={14} /> <b>30 A</b>
                      <Check size={16} />
                    </dd>
                  </div>
                </dl>
                <small>
                  허용 전압강하를 알 수 없어 순방향 전압은 판정에서 뺐고, 패키지가 달라 기판 수정이
                  필요합니다.
                </small>
                <Disclaimer />
              </div>
            </div>
          </div>
        </section>
        <section id="principle" className="principle">
          <h2>
            원래 정격보다,
            <br />이 회로에 필요한 조건.
          </h2>
          <p>같은 후보라도 무엇을 기준으로 보느냐에 따라 판단이 달라집니다.</p>
          <div className="comparison">
            <div className="segmented" aria-label="비교 기준">
              <button aria-pressed={basis === 'original'} onClick={() => setBasis('original')}>
                원래 부품의 정격
              </button>
              <button aria-pressed={basis === 'role'} onClick={() => setBasis('role')}>
                이 회로의 역할
              </button>
            </div>
            <h3>
              {basis === 'role'
                ? '15 V·120 mA 회로에서 필요한 여유를 봅니다.'
                : '원래 부품의 정격을 기준으로 비교합니다.'}
            </h3>
            {basis === 'role' ? (
              <>
                <div className="equations">
                  <div>
                    <span>필요 역전압</span>
                    <strong>15 V × 1.25</strong>
                    <b>18.75 V 이상</b>
                  </div>
                  <div>
                    <span>필요 순방향 전류</span>
                    <strong>0.12 A × 1.43</strong>
                    <b>0.171 A 이상</b>
                  </div>
                </div>
                <p>
                  1N4007G: 1000 V / 1 A <ArrowRight size={16} /> <Badge verdict="ROLE_SUFFICIENT" />
                </p>
              </>
            ) : (
              <div className="original-copy">
                <p>원래 부품의 주요 정격을 모두 같거나 넘는지 확인합니다.</p>
                <p>
                  회로가 실제로 요구하는 조건은 별도로 살펴야 합니다. 원래 부품의 정격에 못 미쳐도
                  회로 역할에 충분한 후보가 있습니다.
                </p>
              </div>
            )}
            <small>
              ATtiny85 Time Switch의 기록된 데모 질문(v3-01) 결과입니다. 실제 후보 판정은 업로드한
              회로와 서버 결과를 따릅니다.
            </small>
          </div>
        </section>
        <section id="how" className="how">
          <h2>
            회로에서 시작해,
            <br />
            근거까지 확인하세요.
          </h2>
          <ol>
            <li>
              <FileText />
              <div>
                <h3>넷리스트를 올리고 부품을 고르세요.</h3>
                <p>KiCad 넷리스트에서 다이오드와 핀 연결을 확인합니다.</p>
              </div>
            </li>
            <li>
              <MessageSquare />
              <div>
                <h3>평소 쓰는 말로 물어보세요.</h3>
                <p>“D1을 이 부품으로 바꿔도 될까?” 빠진 사용 조건은 검토 중에 다시 묻습니다.</p>
              </div>
            </li>
            <li>
              <Check />
              <div>
                <h3>조건별 판정과 원문을 확인하세요.</h3>
                <p>
                  필요 값, 후보 값, 시험 조건을 나란히 보고 데이터시트의 쪽·표·행으로 돌아갑니다.
                </p>
              </div>
            </li>
          </ol>
        </section>
        <section className="product-proof">
          <h2>
            빠진 조건은 묻고,
            <br />
            판정 근거는 펼쳐봅니다.
          </h2>
          <p>기록된 데모를 이 작업대에서 실행한 화면입니다.</p>
          <div>
            <figure>
              <a
                href="/assets/product/missing-condition.png"
                target="_blank"
                rel="noreferrer"
                aria-label="추가 조건 입력 화면 크게 보기"
              >
                <img
                  src="/assets/product/missing-condition.png"
                  alt="허용 전압강하를 묻고 값을 입력해 재개하는 실제 데모 화면"
                  width="872"
                  height="366"
                  loading="lazy"
                />
              </a>
              <figcaption>허용 전압강하처럼 빠진 사용 조건을 확인합니다.</figcaption>
            </figure>
            <figure>
              <a
                href="/assets/product/condition-evidence.png"
                target="_blank"
                rel="noreferrer"
                aria-label="조건별 판정 근거 화면 크게 보기"
              >
                <img
                  src="/assets/product/condition-evidence.png"
                  alt="1N4007G의 필요 역전압 18.75 V와 후보 값 1000 V, 데이터시트 인용을 보여 주는 실제 데모 화면"
                  width="622"
                  height="551"
                  loading="lazy"
                />
              </a>
              <figcaption>필요 값과 후보 값을 비교하고, 데이터시트 원문으로 돌아갑니다.</figcaption>
            </figure>
          </div>
        </section>
        <section className="verdict-guide">
          <h2>
            쓸 수 있는지,
            <br />
            아직 모르는지 분명하게.
          </h2>
          <div className="guide-row">
            <h3>승인할 수 있는 후보</h3>
            <div>
              <Badge verdict="IDENTICAL" />
              <Badge verdict="SPEC_EQUIVALENT" />
              <Badge verdict="ROLE_SUFFICIENT" />
              <p>같은 제품인지, 주요 정격이 동등한지, 회로 역할에 충분한지 구분합니다.</p>
            </div>
          </div>
          <div className="guide-row">
            <h3>조건을 충족하지 못한 후보</h3>
            <div>
              <Badge verdict="NOT_SUFFICIENT" />
              <p>필수 조건을 만족하지 못하면 승인할 수 없습니다.</p>
            </div>
          </div>
          <div className="guide-row">
            <h3>근거가 더 필요한 후보</h3>
            <div>
              <Badge verdict="NOT_VERIFIED" />
              <p>문서에 값이 없거나 시험 조건이 다르면 결론을 유보합니다.</p>
            </div>
          </div>
        </section>
        <section className="limits">
          <h2>마지막 판단은 사람이 합니다.</h2>
          <div>
            <p>
              같은 동작은 보장하지 않습니다. 지금은 다이오드를 검토하며, 실제 적용 전에는 사용
              조건과 실장 변경을 확인해야 합니다.
            </p>
            <p>사람이 후보를 승인한 뒤에만 수량을 넣어 견적서를 저장합니다.</p>
            <a className="button primary" href="/login">
              내 회로 검토하기 <ArrowRight size={18} />
            </a>
          </div>
        </section>
      </main>
      <footer>
        <Brand />
        <span>회로를 이해하고, 근거로 교체합니다.</span>
        <a href="/privacy">개인정보 처리방침</a>
      </footer>
    </div>
  );
}
