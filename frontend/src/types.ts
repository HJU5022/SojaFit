/** 공개 API 자료형. 내부 모델과 비공개 값은 포함하지 않는다. 출처: backend/api, conversations/dto.py. */
export type Verdict =
  'IDENTICAL' | 'SPEC_EQUIVALENT' | 'ROLE_SUFFICIENT' | 'NOT_SUFFICIENT' | 'NOT_VERIFIED';
export type Citation = {
  document: string;
  page?: number | string | null;
  table?: string;
  row?: string;
  section?: string;
  source_url?: string;
  evidence_grade?: number;
  citation_number?: string;
};
type Check = {
  code: string;
  tier?: string;
  op?: string;
  basis?: string;
  threshold?: number | number[] | null;
  value?: number | number[] | null;
  unit?: string | null;
  condition?: string | null;
  result: string;
  why?: string;
  citation?: Citation;
};
export type Candidate = {
  part: string;
  role: string;
  verdict: Verdict;
  checks: Check[];
  missing: string[];
  uncertain: string[];
  cautions: string[];
  board_change: boolean | null;
  package_citation?: Citation;
};
export type Result = {
  answer: string;
  status: string;
  stage: string;
  evidence: Citation[];
  judgement: {
    results?: Candidate[];
    shown?: Candidate[];
    unverified?: Candidate[];
    roles?: string[];
    role_evidence?: string[];
    input_conditions?: { code: string; value: string }[];
    capped?: boolean;
  };
  price_parts: string[];
  interrupt: {
    missing?: string[];
    role_choices?: string[];
    question?: string;
    /** 대상 부품을 물을 때만(SPEC 8.9). 고른 ref를 재개 본문의 target으로 보낸다 */
    target_choices?: { ref: string; value: string }[];
  };
  error?: { code: string; message: string } | null;
  /** 이 실행에서 웹 검색(Exa)이 실패해 등록된 자료로만 답했는지(#28) */
  web_search_unavailable?: boolean;
};
export type Run = { id: string; thread_id: string; message_id: number | null; result: Result };
export type Project = {
  id: number;
  name: string;
  source_kind: string;
  demo_id: string | null;
  circuit_version: number;
  /** 회로가 있는지(circuit_version > 0). 사이드바가 회로 없는 대화를 프로젝트 나무 밖에 모은다(#31) */
  has_circuit: boolean;
  connections: { components?: Component[]; nets?: any[]; [key: string]: any };
  /** 이 회로 버전에 올린 회로도(.kicad_sch) 파일 이름. 있으면 원본 회로도 창이 웹 검색 대신 이 그림을 보인다(#52) */
  schematic_file?: string | null;
};
type Component = {
  value?: string;
  footprint?: string;
  pins?: Record<string, any>;
  [key: string]: any;
};
/** GET /api/threads 한 줄: 모든 프로젝트의 대화(사이드바 "대화"). title은 고친 이름, 없으면 첫 질문으로 만든 이름. */
export type ThreadListItem = {
  id: string;
  project_id: number;
  project_name: string;
  title: string;
  created_at: string;
  last_activity_at: string;
};
type Message = {
  id: number;
  run_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};
export type Detail = {
  id: string;
  project_id: number;
  title: string;
  target_ref: string | null;
  target_locked: boolean;
  messages: Message[];
  latest_run: { id: string; status: string; message_id: number | null } | null;
  next_before_message_id: number | null;
};
export type Demo = {
  id: string;
  name: string;
  schematic?: {
    image_url: string;
    original_url: string;
    attribution: string;
    license: string;
  } | null;
};
export type DemoQuestion = {
  id: string;
  demo_id: string | null;
  target: string;
  question: string;
  conditions: string;
  resume: { answers: Record<string, string>; role: string } | null;
};
export type Role = { code: string; name: string };
export type Quote = {
  id: number;
  part_number: string;
  quantity: number;
  created_at: string;
  thread_id?: string;
};
export type Approval = { id: number; candidate_part: string; verdict: Verdict; quotes?: Quote[] };
/** GET /api/approved-cases/{id}: 승인 사례 하나의 기록. 후보·근거는 승인 때 저장한 값이다(다시 판정하지 않음). */
export type ApprovedCaseDetail = {
  id: number;
  candidate_part: string;
  verdict: Verdict;
  created_at: string;
  project_id: number;
  project_name: string;
  thread_id: string;
  thread_title: string;
  question: string;
  target_ref: string | null;
  target_value: string | null;
  circuit_version: number | null;
  answer: string;
  candidate: Candidate | null;
  evidence: Citation[];
  quotes: Quote[];
};
/** GET /api/prices?quantity= 의 부품별 예상 금액. 품번·가격 구간·통화를 못 맞추면 서버가 null을 준다. */
export type PriceEstimate = {
  quantity: number;
  break_quantity: number;
  unit_price: string;
  total: string;
  currency: string;
};
export type Fact = { kind: string; value: string; text: string };
export type User = { user_id: number; role: 'admin' | 'user'; email: string };
/** GET /api/admin/users 한 줄. email은 서버가 가린 값이다. */
export type Account = { id: number; email: string; role: 'admin' | 'user'; is_active: boolean };
/** GET /api/admin/audit 한 줄: 관리자 작업 이력. 이메일은 모두 가린 값이다. */
export type AuditEntry = {
  id: number;
  actor_id: number;
  actor_email: string;
  target_id: number;
  target_email: string;
  action: 'unmask' | 'deactivate' | 'activate' | 'delete';
  fields: string[];
  reason: string | null;
  created_at: string;
};
type SchematicChoice = {
  title: string;
  source_url: string;
  source_type: 'manufacturer_official' | 'public_web' | 'community';
  revision: string | null;
};
/** GET /api/external-circuits/schematics 응답. 이미지는 images[].url을 <img>가 같은 세션 쿠키로 받는다. */
export type ExternalSchematic = {
  license: string;
  attribution: string;
  source_url: string;
  source_type: 'manufacturer_official' | 'community' | 'public_web';
  evidence_grade: 2 | 3 | null;
  manufacturer: string | null;
  model: string | null;
  revision: string | null;
  license_evidence_url: string | null;
  images: { sheet: number; url: string }[];
  choices: SchematicChoice[];
  circuit_version: number | null;
};
/** GET /api/projects/{id}/parts?circuit_version= 의 한 줄(#68). 종류 · 판정 지원 · 데이터시트는 서버가 에이전트와 같은 규칙으로 정한다. */
export type PartCheck = {
  ref: string;
  value: string;
  footprint: string;
  symbol: string;
  kind: string;
  kind_name: string;
  judge_supported: boolean;
  /** 판정이 받지 않는 이유 구절("LED라서" · "다이오드가 아니라서"). 받으면 null */
  judge_reason: string | null;
  /** 코퍼스에 데이터시트가 있는 품번. 없으면 null */
  datasheet: string | null;
};
export type PartsCheck = {
  circuit_version: number;
  parts: PartCheck[];
  counts: { kind: string; name: string; count: number }[];
};
/** GET /api/datasheets 한 줄: 서재(폐기 제외 코퍼스)의 데이터시트 하나. parts는 표지에 적힌 품번(#67). */
export type Datasheet = {
  id: number;
  title: string;
  publisher: string;
  revision: string | null;
  category: string | null;
  source_url: string;
  collected_at: string;
  parts: string[];
};
/** GET /api/datasheets 응답. categories는 검색과 상관없는 서재 전체의 분류별 수(많은 순). */
export type DatasheetPage = {
  items: Datasheet[];
  total: number;
  page: number;
  page_size: number;
  categories: { category: string; count: number }[];
};
