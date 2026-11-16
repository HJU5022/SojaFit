/**
 * 제품 소개. 예시 수치는 기록된 데모 결과(data/demo/recordings/outcomes.json, 질문 v3-01)에서 옮긴 값이고 실시간 판정이 아니다.
 * 판정 기준 구간(#criteria)의 숫자는 판정 규칙 코드에서 옮겼다(출처는 그 구간 주석). 판정을 계산하지 않는다.
 */
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
        '.landing section>h2,.landing section>p,.how li,.criteria>ol,.rules,.limits>div,.product-proof figure',
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
          <a href="#how">검토 과정</a>
          <a href="#criteria">판정 기준</a>
          <a href="/login">
            로그인 <ArrowUpRight size={15} />
          </a>
        </nav>
      </header>
      <main>
        <section className="hero">
          <h1>대체 부품을 내 회로에 써도 되는지 데이터시트로 판정합니다.</h1>
          <p className="hero-copy">
            KiCad 넷리스트에서 부품의 회로 역할과 필요한 전압·전류 조건을 정하고, 후보 데이터시트의
            표 값과 비교해 판정합니다. 판정마다 데이터시트의 쪽·표·행을 인용합니다.
          </p>
          {/* [주의] 판정 규칙은 다이오드에만 있다(SPEC 1절 "하는 일"·"하지 않는 것"). 역할 23종은 backend/judge/rules/roles.yaml R01~R23. 다른 부품이 된다고 읽히게 쓰지 않는다 */}
          <p className="hero-scope">
            지금 지원: 다이오드(소형 MCU 회로, 회로 역할 23종). 다른 부품은 아직 판정하지 않습니다.
          </p>
          <a className="button primary" href="/login">
            내 회로 검토하기 <ArrowRight size={18} />
          </a>
          <div className="hero-sample">
            <div className="sample-top">
              <span>검토 예시</span>
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
          <h2>비교 기준: 원래 부품 정격과 회로 조건</h2>
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
          <h2>검토 과정</h2>
          <ol>
            <li>
              <FileText />
              <div>
                <h3>넷리스트를 올리고 부품을 고르세요.</h3>
                <p>KiCad 넷리스트에서 바꿀 부품(지금은 다이오드)과 핀 연결을 확인합니다.</p>
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
          <h2>실제 검토 화면</h2>
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
        {/* 판정 방법·기준식·판정 5종. 숫자와 순서는 코드에서 옮겼다. 규칙이 바뀌면 이 구간도 같이 고친다.
            - 1.25 · ÷0.7: backend/judge/rules/roles.yaml 머리 주석(kV = 1.25, kI = 1/0.7), 역할 수 23: 같은 파일 R01~R23
            - 역할 예 3종: 같은 파일 R01(역극성 보호) · R05(AC · 브리지 정류) · R13(플라이백 전원 출력 정류)
            - 질문에 적은 규격을 필수 조건으로 더함: backend/judge/conditions.py user_conditions
            - 판정 순서: backend/judge/verdict.py judge_part(동일품 → 불충족 → 확인 안 됨 → 사양 동등 → 역할상 충분), 뜻은 SPEC 3절
            - 역할상 충분 = 조건 모두 통과 + 사양 동등 확인 실패: verdict.py _not_worse가 거짓(major 없는 역할 R13 · R14 · R17 포함)
            - 예시가 역할상 충분인 이유(원래 1N4007RLG 데이터시트 없음): data/demo/recordings/outcomes.json v3-01 답 */}
        <section id="criteria" className="criteria">
          <h2>판정 방법과 기준</h2>
          <p>회로 조건과 데이터시트 값을 코드로 비교하고, 조건마다 데이터시트 위치를 인용합니다.</p>
          <ol className="method">
            <li>
              <b>1. 회로 조건</b>
              넷리스트의 핀 연결로 부품의 회로 역할을 정하고, 입력 최대 전압·최대 전류 같은 회로
              값을 받습니다. 빠진 값은 되묻습니다.
            </li>
            <li>
              <b>2. 데이터시트 값</b>
              후보 데이터시트의 표 행에서 정격 값과 시험 조건(온도·펄스 폭 등)을 읽습니다.
            </li>
            <li>
              <b>3. 코드로 비교</b>
              기준식 계산과 숫자·단위 비교는 모델이 아니라 판정 코드가 합니다. 시험 조건이 다르면
              비교하지 않습니다.
            </li>
            <li>
              <b>4. 근거 인용</b>
              조건마다 데이터시트 파일과 쪽·표·행을 붙입니다.
            </li>
          </ol>
          <h3>필수 조건의 기준식</h3>
          <p>
            대부분의 역할은 정격에 여유를 둡니다. 전압은 정격의 80%까지만 쓰도록 회로 값 × 1.25,
            전류는 70%까지만 쓰도록 회로 값 ÷ 0.7(약 × 1.43) 이상인 정격을 요구합니다. 다이오드 회로
            역할 23종마다 조건과 기준식이 있고, 아래는 그중 3종입니다. 질문에 적은 규격(예: 서지
            전류 2 A 이상)도 필수 조건으로 더합니다.
          </p>
          <div className="rules">
            <div>
              <strong>역극성 보호(직렬)</strong>
              <dl>
                <div>
                  <dt>역전압 VRRM·VR</dt>
                  <dd>입력 최대 전압 × 1.25 이상</dd>
                </div>
                <div>
                  <dt>평균 순방향 전류 IF(AV)</dt>
                  <dd>최대 전류 ÷ 0.7 이상</dd>
                </div>
                <div>
                  <dt>순방향 전압 VF</dt>
                  <dd>허용 전압강하 이하(값을 알려 준 경우만)</dd>
                </div>
              </dl>
            </div>
            <div>
              <strong>AC · 브리지 정류</strong>
              <dl>
                <div>
                  <dt>역전압 VRRM</dt>
                  <dd>AC 실효값 × √2 × 1.25 이상(DC 입력이면 입력 최대 전압 × 1.25)</dd>
                </div>
                <div>
                  <dt>평균 순방향 전류 IF(AV)</dt>
                  <dd>부하 전류 ÷ 0.7 이상(다이오드 4개를 따로 쓰면 그 절반)</dd>
                </div>
              </dl>
            </div>
            <div>
              <strong>플라이백 전원 출력 정류</strong>
              <dl>
                <div>
                  <dt>역전압 VRRM</dt>
                  <dd>(출력 전압 + 입력 최대 전압 × 권선비) × 2 이상(스너버가 있으면 × 1.25)</dd>
                </div>
                <div>
                  <dt>평균 순방향 전류 IF(AV)</dt>
                  <dd>출력 전류 ÷ 0.7 이상</dd>
                </div>
                <div>
                  <dt>역회복 시간 trr</dt>
                  <dd>75 ns 이하</dd>
                </div>
              </dl>
            </div>
          </div>
          <h3>판정 5종</h3>
          <p>후보마다 위에서부터 차례로 따져, 처음 맞는 판정 하나를 냅니다.</p>
          <ol className="verdict-order">
            <li>
              <Badge verdict="IDENTICAL" />
              <p>
                같은 품번, 같은 기본 품번에 주문 코드만 다른 품번, 또는 제조사가 같은 제품이라고
                밝힌 품번입니다.
              </p>
            </li>
            <li>
              <Badge verdict="NOT_SUFFICIENT" />
              <p>
                조건 중 하나라도 기준에 못 미칩니다. 다른 조건을 확인하지 못했어도 불충족입니다.
              </p>
            </li>
            <li>
              <Badge verdict="NOT_VERIFIED" />
              <p>
                필요한 값이 데이터시트에 없거나 시험 조건이 달라 비교하지 못했습니다. 견적에 넣지
                않습니다.
              </p>
            </li>
            <li>
              <Badge verdict="SPEC_EQUIVALENT" />
              <p>
                조건을 모두 통과했고, 역할마다 정한 주요 정격(역전압·평균 전류·서지 전류 등)도 같은
                시험 조건에서 원래 부품과 같거나 낫습니다. 원래 부품의 데이터시트가 있어야 합니다.
              </p>
            </li>
            <li>
              <Badge verdict="ROLE_SUFFICIENT" />
              <p>
                조건은 모두 통과했지만 사양 동등을 확인하지 못했습니다. 원래보다 낮은 주요 정격이
                있거나, 같은 시험 조건의 원래 값이 없거나, 원래 부품의 데이터시트가 없거나, 그
                역할에 주요 정격이 정해져 있지 않은 경우입니다. 첫 화면의 1N4007G 예시는 원래 부품
                1N4007RLG의 데이터시트를 찾지 못해 이 판정입니다.
              </p>
            </li>
          </ol>
        </section>
        <section className="limits">
          <h2>판정의 한계와 승인</h2>
          <div>
            {/* [왜] "같은 동작은 보장하지 않습니다"는 위 예시 결과(Disclaimer)에 있어 이 화면에서 두 번 쓰지 않는다 */}
            <p>
              판정은 데이터시트에 적힌 값과 회로 조건의 비교입니다. 실제 적용 전에는 사용 조건과
              실장(패키지·기판) 변경을 확인해야 합니다.
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
        <a href="/privacy">개인정보 처리방침</a>
      </footer>
    </div>
  );
}
