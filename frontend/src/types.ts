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
  interrupt: { missing?: string[]; role_choices?: string[]; question?: string };
  error?: { code: string; message: string } | null;
};
export type Run = { id: string; thread_id: string; message_id: number | null; result: Result };
export type Project = {
  id: number;
  name: string;
  source_kind: string;
  demo_id: string | null;
  circuit_version: number;
  connections: { components?: Component[]; nets?: any[]; [key: string]: any };
};
type Component = {
  value?: string;
  footprint?: string;
  pins?: Record<string, any>;
  [key: string]: any;
};
export type Thread = {
  id: string;
  title: string;
  project_id: number;
  status: string | null;
  latest_run_id: string | null;
  circuit_version: number;
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
