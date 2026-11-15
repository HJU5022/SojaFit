/**
 * 서버가 준 숫자·기준식·링크를 화면 표기로 바꾸는 순수 함수.
 * 하지 않는 일: 값 비교·판정(backend/judge가 한다), 받은 값의 변경(보이는 글만 만든다), 네트워크.
 * 출처: SPEC.md 3절(화면 표기), backend/judge/conditions.py(기준식 문법).
 */
import { inputLabel, INPUT_LABELS } from './inputLabels.ts';

/** 기준식의 kV · kI 여유 계수. backend/judge/conditions.py의 MARGINS와 같은 값이다. */
const MARGIN_LABELS: Record<string, string> = {
  kV: '전압 여유 1.25배',
  kI: '전류 여유 1.43배',
};
/** 데이터시트 항목 코드(backend/judge/conditions.py의 CODES). `orig.<코드>`와 "A 또는 B" 묶음의 왼쪽에 나온다. */
const SPEC_CODES = new Set([
  'VRRM',
  'IF_AV',
  'IFSM',
  'VF',
  'IR',
  'TRR',
  'VZ',
  'PD',
  'CJ',
  'TJ_MAX',
  'VR',
  'VRWM',
  'VBR',
  'VC',
  'IPP',
  'PPPM',
  'VESD',
]);
const OPERATORS: Record<string, string> = {
  '>=': '≥',
  '<=': '≤',
  within: '범위 안',
  '*': '×',
  '/': '÷',
  '-': '−',
};

/** 화면용 숫자. 정수와 짧은 소수(유효숫자 4자리 이하)는 그대로, 긴 소수는 유효숫자 3자리로 줄인다. */
export function formatNumber(n: number): string {
  if (!Number.isFinite(n) || Number.isInteger(n)) return String(n);
  // [왜] 가장 짧은 표기의 유효숫자 수: 18.75는 4자리라 그대로 두고 0.17142857142857143은 줄인다
  const digits = n.toExponential().split('e')[0].replace(/[-.]/g, '').length;
  if (digits <= 4) return String(n);
  // [주의] toPrecision(3)은 12345.6을 '1.23e+4'로 쓴다. 1000 이상은 정수로 반올림한다
  return Math.abs(n) >= 1000 ? String(Math.round(n)) : String(Number(n.toPrecision(3)));
}

/** 요구값·후보값 표기. 서버가 숫자 하나나 범위(둘)를 보낸다. 값이 없으면 "확인 안 됨". 단위는 서버가 준 그대로. */
export function formatAmount(
  value: number | number[] | string | null | undefined,
  unit?: string | null,
): string {
  if (value == null) return '확인 안 됨';
  const one = (v: number | string) => (typeof v === 'number' ? formatNumber(v) : v);
  const text = Array.isArray(value) ? value.map(one).join(' ~ ') : one(value);
  return text + (unit ? ' ' + unit : '');
}

/** 문장 속 긴 소수(소수점 아래 6자리 이상)만 줄인다. 답변·설명 글에 섞인 계산 결과용이다. */
export function roundLongDecimals(text: string): string {
  return text.replace(/(?<![\w.])\d+\.\d{6,}(?![\w.])/g, (m) => formatNumber(Number(m)));
}

/** 판정 기준식을 한국어로 푼다. 모르는 이름이 하나라도 있으면 known=false이고 text는 원문 그대로다. */
export function basisLabel(basis: string): { text: string; known: boolean } {
  if (!/[A-Za-z_]/.test(basis)) return { text: basis, known: true }; // 한국어 안내문('같은 기본 품번…') 등
  let known = true;
  const text = basis.replace(
    /orig\.(\w+)|[A-Za-z_]\w*|\d+(?:\.\d+)?(?:e[+-]?\d+)?|>=|<=|[*/-]/g,
    (token, origCode?: string) => {
      if (origCode !== undefined) {
        if (SPEC_CODES.has(origCode)) return `원래 부품 ${origCode}`;
      } else if (Object.hasOwn(OPERATORS, token)) return OPERATORS[token];
      else if (Object.hasOwn(MARGIN_LABELS, token)) return MARGIN_LABELS[token];
      else if (SPEC_CODES.has(token)) return token;
      else if (/^\d/.test(token)) return token.includes('e') ? token : formatNumber(Number(token));
      else if (Object.hasOwn(INPUT_LABELS, token) && /^[a-z]/.test(token)) {
        // [왜] 괄호 설명은 길어서 기준식 안에서는 뺀다. 전체 이름은 입력 조건 칸에 있다
        return inputLabel(token).replace(/\s*\(.*\)\s*$/, '');
      }
      known = false;
      return token;
    },
  );
  return known ? { text, known } : { text: basis, known };
}

/** 서버 답변(마크다운) 속 긴 소수를 줄이고 `(v_in_max * kV)` 같은 괄호 기준식을 한국어로 푼다. 알아볼 수 있는 식만 바꾼다. */
export function explainAnswer(text: string): string {
  return roundLongDecimals(text).replace(
    /\(([A-Za-z_][\w.]*(?: [*/+-] [\w.]+)*)\)/g,
    (match, inner: string) => {
      if (!/_|^k[VI]\b|orig\./.test(inner)) return match;
      const b = basisLabel(inner);
      return b.known ? `(${b.text})` : match;
    },
  );
}

/** 비교 연산자 표기. 서버는 `>=` · `<=` · `within` · `=`를 보낸다. 모르는 값은 그대로 보인다. */
export function opLabel(op: string): string {
  return Object.hasOwn(OPERATORS, op) ? OPERATORS[op] : op;
}

/** 서버 문장 속 회로 값 이름(밑줄이 든 영문 소문자 이름, 예: `v_drop_allowed`)을 화면 이름으로 바꾼다. */
export function explainNames(text: string): string {
  return text.replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (t) =>
    Object.hasOwn(INPUT_LABELS, t) ? inputLabel(t) : t,
  );
}

/** http(s) 주소만 링크로 쓴다. 그 밖(javascript: · data: · mailto: · 상대 주소)은 undefined. */
export function safeLink(url?: string | null): string | undefined {
  if (!url) return undefined;
  try {
    const u = new URL(url);
    return u.protocol === 'http:' || u.protocol === 'https:' ? u.href : undefined;
  } catch {
    return undefined;
  }
}

/** react-markdown의 urlTransform용: http(s)가 아닌 주소는 빈 문자열(링크 없음)로 바꾼다. */
export function markdownUrl(url: string): string {
  return safeLink(url) ?? '';
}

/** 같은 출처의 이미지 주소만 쓴다(`/circuit-schematics/…` · `/api/external-circuits/…`). 외부·프로토콜 상대(`//host`) 주소는 undefined. */
export function sameOriginImage(url?: string | null): string | undefined {
  return url && /^\/(?![/\\])/.test(url) ? url : undefined;
}

/**
 * 답변 속 `[79]` 같은 말뭉치 인용 번호 중 이 답변의 근거(evidence)에 등록된 번호만 숨긴다. 코드·수치·미등록 괄호·링크 `[글](주소)`는 둔다.
 * [왜] 번호는 서버 내부 말뭉치 번호라 사용자에게 뜻이 없다. 근거는 "문서 근거" 목록에서 쪽·표·행으로 보인다.
 */
export function withoutCorpusCitations(
  text: string,
  evidence: { citation_number?: string }[] = [],
): string {
  const numbers = new Set(
    evidence.map((e) => e.citation_number).filter((n) => /^\d+$/.test(n ?? '')),
  );
  return text.replace(/[ \t]*\[([^[\]\n]+)\](?!\()/g, (match, group: string) => {
    const ids = group.split(',').map((id) => id.trim());
    const remaining = ids.filter((id) => !numbers.has(id));
    if (remaining.length === ids.length) return match;
    return remaining.length ? `${match.match(/^[ \t]*/)?.[0] ?? ''}[${remaining.join(', ')}]` : '';
  });
}
