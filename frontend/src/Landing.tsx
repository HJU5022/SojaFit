/**
 * 공개 제품 소개와 기록된 판정 예시. 실시간 분석·판정 계산은 하지 않는다.
 * 출처: SPEC 2절 공개 랜딩, data/demo/recordings/outcomes.json 질문 v3-01.
 */
import { useEffect, useState, type ReactNode } from 'react';
import { ArrowDown, ArrowRight, FileText, Check, ArrowUpRight } from 'lucide-react';
import { Brand, Badge, plainClick } from './ui';
import { legalDocs, LegalModal } from './Legal';
import { contactEmail } from './Account';

// [왜] 랜딩 전체의 문구·예시·미디어를 한곳에서 교체한다. 문구 안의 \\u00a0은 줄바꿈 없는 공백으로, 붙어 있어야 하는 낱말이 줄 끝에서 갈라지지 않게 한다. 히어로 검토 장면은 미디어와 독립적이다.
// 이미지/GIF는 그대로, mp4·webm·ogv는 재생 컨트롤이 있는 영상으로 표시한다.
const LANDING = {
  title: ['대체 부품 검토,', '회로를 기준으로.'],
  description:
    '회로에서 부품이 맡은 역할과 대체 조건을 읽고, 데이터시트에서 판정 근거를 찾아 보여 줍니다.',
  action: '내 회로 검토하기',
  actionHref: '/login',
  navigation: [
    { label: '검토 과정', href: '#workflow' },
    { label: '판정 근거', href: '#evidence' },
    { label: '승인과 기록', href: '#approval' },
  ],
  login: '로그인',
  navigationLabel: '주 탐색',
  disclaimer: '같은 동작은 보장하지 않습니다.',
  media: {
    hero: {
      src: '',
      alt: '회로를 읽고 대체 후보의 조건과 데이터시트 근거를 확인하는 SojaFit 검토 화면',
      caption: '회로 연결부터 근거 확인까지 이어지는 검토 흐름입니다.',
    },
    circuit: {
      src: '',
      alt: '넷리스트에서 부품의 연결과 회로 역할을 확인하는 제품 화면',
      caption: '회로의 연결을 보고 부품이 맡은 역할을 확인합니다.',
    },
    report: {
      src: '',
      alt: '후보를 승인하고 견적과 검토 보고서를 확인하는 제품 화면',
      caption: '사람이 확인하고 승인한 검토를 기록으로 남깁니다.',
    },
    fallback: '실제 검토 화면을 준비하고 있습니다.',
  },
  overview: {
    title: ['질문에서 검토까지,', '하나의 작업대에서.'],
    description:
      '회로를 올리고 바꿀 부품을 물어보세요. 필요한 조건부터 후보의 판정과 근거까지 한 화면에서 보여 줍니다.',
    preview: '검토 흐름 미리보기',
    file: '내 회로.net',
    fileType: 'KiCad 넷리스트',
    question: '이 부품을 다른 부품으로 바꿔도 될까요?',
    stages: ['회로 읽기', '조건 확인', '후보 검토', '근거 확인'],
    answer: '회로가 요구하는 조건과 후보의 정격을 함께 확인합니다.',
    output: '조건별 판정 · 데이터시트 출처',
  },
  workflow: {
    title: ['품번만 보지 않고,', '쓰이는 회로를 봅니다.'],
    description:
      '같은 부품도 어디에 쓰이느냐에 따라 필요한 조건이 달라집니다. 검토는 부품이 연결된 자리에서 시작합니다.',
    steps: [
      {
        title: '회로에서 부품의 연결 확인',
        text: 'KiCad 넷리스트에서 바꿀 부품과 그 핀이 어디에 연결되는지 확인합니다.',
      },
      {
        title: '부품의 역할과 사용 조건 정리',
        text: '부품이 회로에서 맡은 역할을 읽고, 판정에 필요한 전압과 전류\u00a0조건을 정리합니다.',
      },
      {
        title: '빠진 조건은 다시 질문',
        text: '회로만으로 알 수 없는 값은 다시 묻고, 답을 받으면 이어서 검토합니다.',
      },
    ],
    previewTitle: '검토가 시작되는 순서',
    previewInput: 'KiCad 넷리스트',
    previewTarget: '교체할 부품',
    previewOutput: '회로 역할 · 필요한 조건',
  },
  evidence: {
    title: ['판정 옆에는', '찾아갈 수 있는 근거.'],
    description:
      '비교한 조건과 값, 그리고 그 값이 있는 데이터시트의 쪽, 표, 행을 함께 보여 줍니다.',
    stepsLabel: '검토 단계',
    next: '다음 단계',
    restart: '처음 단계로',
    // [왜] 판정 장면을 큰 화면 하나에 두고 단계 버튼으로 넘겨 본다. src에 캡처 · GIF · 영상 경로를 넣으면 그 단계의 화면이 바뀌고, 비어 있으면 자리 표시가 보인다.
    steps: [
      {
        label: '회로와 질문',
        caption: '넷리스트를 올리고 바꿀 부품을 평소 쓰는 말로 묻습니다.',
        src: '/assets/product/question.png',
        alt: '넷리스트를 올린 회로에서 D1 교체를 묻고 사용 조건을 적는 운영 화면',
      },
      {
        label: '빠진 조건 확인',
        caption: '허용 전압강하처럼 빠진 사용 조건은 검토 중에 다시 묻습니다.',
        src: '/assets/product/missing-condition.png',
        alt: '회로에서 읽은 역할과 함께 빠진 조건(허용 전압 강하)을 묻는 운영 화면',
      },
      {
        label: '조건별 판정',
        caption: '필요 값과 후보 값을 조건마다 나란히 비교합니다.',
        src: '/assets/product/condition-evidence.png',
        alt: '1N4007G의 입력 조건과 조건마다 필요 값 · 후보 값을 나란히 보여 주는 운영 화면',
      },
      {
        label: '근거 원문',
        caption: '조건마다 데이터시트의 쪽, 표, 행을 열어 확인합니다.',
        src: '/assets/product/evidence-source.png',
        alt: '판정 근거가 된 데이터시트 원문 위치를 여는 제품 화면',
      },
    ],
    note: '판정은 데이터시트 값과 회로 조건을 비교한 결과입니다. 실제\u00a0적용\u00a0전에는 사용 조건과 실장 변경을 확인하세요.',
  },
  approval: {
    title: ['마지막 결정은', '검토하는 사람이 합니다.'],
    description:
      '후보와 근거를 확인한 뒤 승인합니다. 견적과 검토 보고서는 사람이 승인한 뒤에만 남깁니다.',
    previewTitle: '부품 교체 검토 보고서',
    previewStatus: '승인 전 확인',
    previewFields: [
      { label: '검토 대상', value: '회로 · 교체할 부품' },
      { label: '검토 내용', value: '필요 조건 · 후보별 판정' },
      { label: '판정 근거', value: '데이터시트 · 인용 위치' },
      { label: '승인 기록', value: '검토자 · 승인한 후보' },
    ],
    previewNote: '보고서 구성 예시',
  },
  footer: {
    wordmark: 'SojaFit',
    description: '회로를 읽는 전자부품 교체 검토',
    top: '맨 위로',
    contact: '문의',
    contactHref: `mailto:${contactEmail}`,
    copyright: '© 2026 SojaFit',
    legalLabel: '서비스 고지',
    links: legalDocs,
  },
  example: {
    label: '기록된 검토 예시',
    circuit: 'ATtiny85 Time Switch',
    original: '1N4007RLG',
    candidate: '1N4007G',
    ref: 'D1',
    role: '전원 입력 · 역극성 보호',
    input: '15 V',
    load: '120 mA',
    diagramLabel: '연결 개념도',
    partLabel: '교체할 부품',
    inputLabel: '전원 입력',
    loadLabel: '회로 부하',
    question: 'D1을 이 부품으로 바꿔도 될까?',
    resultLabel: '대체 후보',
    verdict: 'ROLE_SUFFICIENT' as const,
    result: '이 회로의 조건을 만족합니다.',
    conditionLabel: '필요 조건',
    valueLabel: '후보 정격',
    sourceLabel: '데이터시트 근거',
    sourceHint: '조건을 누르면 근거 행이 바뀝니다.',
    document: '1N4001G SERIES_P2104.pdf',
    location: '1쪽 · ABSOLUTE MAXIMUM RATINGS',
    temperature: 'TA = 25°C unless otherwise noted',
    manufacturer: 'Taiwan Semiconductor',
    notice: '패키지가 달라 기판 수정이 필요합니다. 순방향 전압은 이번 판정에서 제외했습니다.',
    recorded: '기록된 검토 결과(v3-01)를 다시 그린 화면입니다.',
    conditions: [
      {
        name: '역전압',
        symbol: 'VRRM',
        required: '18.75 V 이상',
        value: '1000',
        unit: 'V',
        row: 'Repetitive peak reverse voltage',
        note: '최대 입력 전압 15 V에 여유를 둔 조건입니다.',
      },
      {
        name: '순방향 전류',
        symbol: 'IF',
        required: '0.171 A 이상',
        value: '1',
        unit: 'A',
        row: 'Average forward current',
        note: '연속 전류 120 mA에 여유를 둔 조건입니다.',
      },
      {
        name: '서지 전류',
        symbol: 'IFSM',
        required: '2 A 이상',
        value: '30',
        unit: 'A',
        row: 'Peak forward surge current',
        note: '초기 접합온도 25°C, 8.3 ms 단발 반정현파 조건입니다.',
      },
    ],
  },
};

/** 이미지 로드 확인 뒤 표시하며, 비어 있거나 손상된 미디어는 대체 장면을 유지한다. */
function LandingMedia({ src, alt, children }: { src: string; alt: string; children: ReactNode }) {
  const [loaded, setLoaded] = useState('');
  const [failed, setFailed] = useState('');
  const isVideo = /\.(mp4|webm|ogv)(?:[?#]|$)/i.test(src);
  useEffect(() => {
    if (!src || isVideo) return;
    let active = true;
    const image = new Image();
    image.onload = () => {
      if (active) setLoaded(src);
    };
    image.onerror = () => {
      if (active) setFailed(src);
    };
    image.src = src;
    return () => {
      active = false;
      image.onload = null;
      image.onerror = null;
    };
  }, [src, isVideo]);
  if (!src || failed === src) return <>{children}</>;
  if (isVideo)
    return (
      <video
        key={src}
        src={src}
        controls
        playsInline
        preload="metadata"
        aria-label={alt}
        onError={() => setFailed(src)}
      />
    );
  return loaded === src ? (
    <img src={src} alt={alt} onError={() => setFailed(src)} />
  ) : (
    <>{children}</>
  );
}

/** 준비 전이나 로드 실패 시에도 미디어 영역과 설명을 유지한다. */
function MediaPlaceholder() {
  return (
    <div className="landing-media-placeholder">
      <FileText size={36} aria-hidden="true" />
      <p>{LANDING.media.fallback}</p>
    </div>
  );
}

/** 판정 장면을 큰 화면 하나에 두고 단계 버튼으로 넘긴다. 화면만 바꾸며 서버에 요청하지 않는다. */
function EvidenceSteps() {
  const { steps } = LANDING.evidence;
  const [current, setCurrent] = useState(0);
  const step = steps[current];
  const last = current === steps.length - 1;
  return (
    <div className="evidence-stage landing-reveal">
      <div className="evidence-steps" role="group" aria-label={LANDING.evidence.stepsLabel}>
        {steps.map((item, index) => (
          <button
            key={item.label}
            aria-pressed={current === index}
            aria-controls="evidence-screen"
            onClick={() => setCurrent(index)}
          >
            <b>{index + 1}</b>
            <span>{item.label}</span>
          </button>
        ))}
      </div>
      <figure className="evidence-screen" id="evidence-screen">
        {/* [왜] key로 단계마다 미디어를 새로 올려, 앞 단계 화면이 남아 보이지 않게 한다 */}
        <div className="landing-media-frame" key={step.label}>
          <LandingMedia src={step.src} alt={step.alt}>
            <MediaPlaceholder />
          </LandingMedia>
        </div>
        <figcaption aria-live="polite">
          <span>
            {current + 1}. {step.caption}
          </span>
          <button className="evidence-next" onClick={() => setCurrent(last ? 0 : current + 1)}>
            {last ? LANDING.evidence.restart : LANDING.evidence.next}
            <ArrowRight size={18} aria-hidden="true" />
          </button>
        </figcaption>
      </figure>
    </div>
  );
}

/** 기록된 조건의 선택만 바꾸며 서버에 판정을 요청하지 않는다. */
function ReviewScene() {
  const [selected, setSelected] = useState(0);
  const sample = LANDING.example;
  const condition = sample.conditions[selected];
  return (
    <div className="review-scene" data-ui>
      <div className="circuit-scene">
        <div className="circuit-caption">
          <span>{sample.circuit}</span>
          <ArrowUpRight size={20} aria-hidden="true" />
        </div>
        <div className="circuit-part">
          <span>{sample.ref}</span>
          <strong>{sample.original}</strong>
        </div>
        <svg
          className="circuit-drawing"
          viewBox="0 0 420 180"
          role="img"
          aria-label={`${sample.inputLabel} ${sample.input}, ${sample.ref}, ${sample.loadLabel} ${sample.load} ${sample.diagramLabel}`}
        >
          <g fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M24 90h138m90 0h144" className="circuit-wire" />
            {/* [왜] 특정 부품 기호 대신 이름표가 붙은 상자를 그린다. 이 장면이 한 부품 종류만 다루는 것처럼 보이지 않게 한다 */}
            <rect x="162" y="60" width="90" height="60" rx="6" strokeWidth="3" />
            <circle cx="24" cy="90" r="5" fill="currentColor" />
            <circle cx="396" cy="90" r="5" fill="currentColor" />
            <path d="M326 90v30m-16 0h32m-32 8h32m-16 0v24m-12 0h24m-19 6h14m-10 6h6" />
          </g>
          <circle className="circuit-signal" cx="24" cy="90" r="5" />
          <text className="circuit-part-label" x="207" y="95" textAnchor="middle">
            {sample.partLabel}
          </text>
          <text x="24" y="35">
            {sample.input}
          </text>
          <text x="396" y="35" textAnchor="end">
            {sample.load}
          </text>
        </svg>
        <div className="circuit-terminals">
          <span>{sample.inputLabel}</span>
          <span>{sample.loadLabel}</span>
        </div>
        <p className="circuit-role">
          <span className="signal-dot" />
          {sample.role}
        </p>
        <p className="circuit-question">{sample.question}</p>
      </div>
      <div className="review-result">
        <div className="review-result-title">
          <span>{sample.resultLabel}</span>
          <Badge verdict={sample.verdict} />
        </div>
        <strong className="candidate-name">{sample.candidate}</strong>
        <p>{sample.result}</p>
        <div className="condition-labels">
          <span>{sample.conditionLabel}</span>
          <span>{sample.valueLabel}</span>
        </div>
        <div className="condition-buttons" aria-label={sample.conditionLabel}>
          {sample.conditions.map((item, index) => (
            <button
              key={item.symbol}
              aria-pressed={selected === index}
              aria-controls="hero-evidence"
              onClick={() => setSelected(index)}
            >
              <span>
                <b>{item.name}</b>
                <small>{item.required}</small>
              </span>
              <strong>
                {item.value} <small>{item.unit}</small>
              </strong>
              <Check size={18} aria-hidden="true" />
            </button>
          ))}
        </div>
        <p className="review-hint">{sample.sourceHint}</p>
      </div>
      <div className="evidence-scene" id="hero-evidence" aria-live="polite" aria-atomic="true">
        <div className="evidence-title">
          <FileText size={20} aria-hidden="true" />
          <span>{sample.sourceLabel}</span>
        </div>
        <div className="evidence-content" key={condition.symbol}>
          <p className="evidence-maker">{sample.manufacturer}</p>
          <p className="evidence-location">{sample.location}</p>
          <div className="evidence-extract">
            <span>{condition.symbol}</span>
            <p>{condition.row}</p>
            <strong>
              {condition.value}
              <small>{condition.unit}</small>
            </strong>
          </div>
          <p className="evidence-temperature">{sample.temperature}</p>
          <p className="evidence-note">{condition.note}</p>
        </div>
        <span className="evidence-file">{sample.document}</span>
      </div>
    </div>
  );
}

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
    document.querySelectorAll('.landing .landing-reveal').forEach((e) => {
      e.classList.add('reveal');
      observer.observe(e);
    });
    return () => observer.disconnect();
  }, []);
  const [legalPath, setLegalPath] = useState<string | null>(null);
  return (
    <div className="landing" id="top">
      <header className="landing-nav">
        <Brand />
        <nav aria-label={LANDING.navigationLabel}>
          {LANDING.navigation.map((item) => (
            <a key={item.href} href={item.href}>
              {item.label}
            </a>
          ))}
          <a className="landing-login" href={LANDING.actionHref}>
            {LANDING.login}
            <ArrowUpRight size={17} aria-hidden="true" />
          </a>
        </nav>
      </header>
      <main>
        <section className="hero">
          <div className="hero-intro">
            <h1>
              {LANDING.title.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h1>
            <div className="hero-action">
              <p>{LANDING.description}</p>
              <a className="hero-cta" href={LANDING.actionHref}>
                {LANDING.action}
                <ArrowUpRight size={22} aria-hidden="true" />
              </a>
            </div>
          </div>
          <div className="hero-stage">
            <div className="hero-stage-caption">
              <span>{LANDING.example.label}</span>
              <span>{LANDING.example.recorded}</span>
            </div>
            <ReviewScene />
            <div className="hero-footnote">
              <p>{LANDING.example.notice}</p>
              <p className="disclaimer">{LANDING.disclaimer}</p>
            </div>
          </div>
        </section>
        <section className="landing-overview" id="overview" aria-labelledby="overview-title">
          <div className="landing-section-heading landing-reveal">
            <h2 id="overview-title">
              {LANDING.overview.title.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h2>
            <p>{LANDING.overview.description}</p>
          </div>
          <figure className="landing-film landing-reveal">
            <LandingMedia {...LANDING.media.hero}>
              <div className="film-preview" data-ui>
                <div className="film-preview-input">
                  <div className="film-file">
                    <FileText size={32} aria-hidden="true" />
                    <span>
                      <strong>{LANDING.overview.file}</strong>
                      <small>{LANDING.overview.fileType}</small>
                    </span>
                  </div>
                  <p>{LANDING.overview.question}</p>
                  <span className="film-preview-label">{LANDING.overview.preview}</span>
                </div>
                <div className="film-preview-output">
                  <ol>
                    {LANDING.overview.stages.map((stage) => (
                      <li key={stage}>
                        <Check size={18} aria-hidden="true" />
                        {stage}
                      </li>
                    ))}
                  </ol>
                  <p>{LANDING.overview.answer}</p>
                  <strong>{LANDING.overview.output}</strong>
                </div>
              </div>
            </LandingMedia>
            <figcaption>{LANDING.media.hero.caption}</figcaption>
          </figure>
        </section>
        <section className="landing-workflow" id="workflow" aria-labelledby="workflow-title">
          <div className="workflow-copy">
            <h2 className="landing-reveal" id="workflow-title">
              {LANDING.workflow.title.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h2>
            <p className="landing-section-copy landing-reveal">{LANDING.workflow.description}</p>
            <ol className="workflow-steps">
              {LANDING.workflow.steps.map((step) => (
                <li className="landing-reveal" key={step.title}>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
          <figure className="workflow-media landing-reveal">
            <LandingMedia {...LANDING.media.circuit}>
              <div className="connection-preview" data-ui>
                <p>{LANDING.workflow.previewTitle}</p>
                <div className="connection-source">
                  <FileText size={42} aria-hidden="true" />
                  <strong>{LANDING.workflow.previewInput}</strong>
                </div>
                <ArrowDown size={32} aria-hidden="true" />
                <div className="connection-target">{LANDING.workflow.previewTarget}</div>
                <ArrowDown size={32} aria-hidden="true" />
                <div className="connection-result">{LANDING.workflow.previewOutput}</div>
              </div>
            </LandingMedia>
            <figcaption>{LANDING.media.circuit.caption}</figcaption>
          </figure>
        </section>
        <section className="landing-evidence" id="evidence" aria-labelledby="evidence-title">
          <div className="landing-section-heading landing-reveal">
            <h2 id="evidence-title">
              {LANDING.evidence.title.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h2>
            <p>{LANDING.evidence.description}</p>
          </div>
          <EvidenceSteps />
          <p className="evidence-boundary landing-reveal">{LANDING.evidence.note}</p>
        </section>
        <section className="landing-approval" id="approval" aria-labelledby="approval-title">
          <figure className="approval-media landing-reveal">
            <LandingMedia {...LANDING.media.report}>
              <div className="report-preview" data-ui>
                <div className="report-preview-heading">
                  <FileText size={28} aria-hidden="true" />
                  <span>{LANDING.approval.previewStatus}</span>
                </div>
                <p className="report-preview-title">{LANDING.approval.previewTitle}</p>
                <dl>
                  {LANDING.approval.previewFields.map((field) => (
                    <div key={field.label}>
                      <dt>{field.label}</dt>
                      <dd>{field.value}</dd>
                    </div>
                  ))}
                </dl>
                <small>{LANDING.approval.previewNote}</small>
              </div>
            </LandingMedia>
            <figcaption>{LANDING.media.report.caption}</figcaption>
          </figure>
          <div className="approval-copy">
            <h2 className="landing-reveal" id="approval-title">
              {LANDING.approval.title.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h2>
            <p className="landing-section-copy landing-reveal">{LANDING.approval.description}</p>
            <a className="hero-cta landing-reveal" href={LANDING.actionHref}>
              {LANDING.action}
              <ArrowUpRight size={22} aria-hidden="true" />
            </a>
          </div>
        </section>
      </main>
      <footer className="landing-footer">
        <div className="landing-footer-top">
          <p>{LANDING.footer.description}</p>
          <a href="#top">
            {LANDING.footer.top}
            <ArrowUpRight size={18} aria-hidden="true" />
          </a>
        </div>
        <a className="landing-wordmark" href="#top" aria-label={LANDING.footer.top}>
          {LANDING.footer.wordmark}
        </a>
        <div className="landing-footer-bottom">
          <nav aria-label={LANDING.footer.legalLabel}>
            {LANDING.footer.links.map(([path, title]) => (
              <a
                key={path}
                href={path}
                onClick={(event) => {
                  if (!plainClick(event)) return;
                  event.preventDefault();
                  setLegalPath(path);
                }}
              >
                {path === '/privacy' ? <strong>{title}</strong> : title}
              </a>
            ))}
            <a href={LANDING.footer.contactHref}>{LANDING.footer.contact}</a>
          </nav>
          <small>{LANDING.footer.copyright}</small>
        </div>
      </footer>
      {legalPath && <LegalModal path={legalPath} close={() => setLegalPath(null)} />}
    </div>
  );
}
