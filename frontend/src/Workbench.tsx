/** 프로젝트·대화·실행 작업대. 서버의 고정 회로 버전과 결과를 사용한다. 출처: SPEC 4·7·8절. */
import { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  Check,
  CornerDownLeft,
  ListChecks,
  LoaderCircle,
  PanelRight,
  Paperclip,
  Pencil,
  Square,
  Trash2,
  X,
} from 'lucide-react';
import { api, ApiError, statuses, streamRun } from './api';
import {
  Circuit,
  AttachmentCard,
  Disclaimer,
  ErrorBox,
  Loading,
  Markdown,
  Modal,
  navigate,
  ResizeHandle,
  RowMenu,
  useNetlistAttach,
  useResource,
} from './ui';
import { CandidateDetails, PriceLookup } from './Candidate';
import { NEEDS_CIRCUIT, partsOf, unsupportedPartNote, unsupportedPartReason } from './circuit';
import { addStep, isSendKey, seconds, stepMs, type Step } from './display';
import { refreshNavigation } from './Projects';
import { MissingInput, Reply, TargetChoice } from './Reply';
import { PartsDialog } from './Parts';
import { SchematicSection } from './Schematic';
import type {
  Candidate,
  Demo,
  DemoQuestion,
  Detail,
  Project,
  Quote,
  Result,
  Role,
  Run,
} from './types';
const freshResult = (): Result => ({
  answer: '',
  status: 'running',
  stage: '',
  evidence: [],
  judgement: {},
  price_parts: [],
  interrupt: {},
});
// [왜] 첫 질문은 새 대화를 열고 나서 보낸다(이전 대화의 비동기 결과가 새 화면을 덮지 않게). 작업대는 프로젝트마다 새로 그려지므로(App의 key)
//      새 대화 화면 · 회로 고르기 카드도 넘길 수 있게 모듈에 둔다
const pendingStart: {
  current: { tid: string; question: string; conditions: string; target: string } | null;
} = { current: null };
// [왜] 새 대화 화면은 옮기면 사라지므로 작업대가 열릴 때 한 번 보일 한 줄 안내(#48 이미 있는 회로로 이어 가기)도 모듈에 둔다
const startNotice: { current: { project: string; text: string } | null } = { current: null };
/** 프로젝트에 새 대화를 만들어 질문을 첫 질문으로 보낸다. 질문이 비면 그 회로의 작업대만 연다(빈 대화 화면이 무엇을 검토할지 묻는다). notice는 처음 열린 대화 위에만 보인다. */
export async function openWithQuestion(projectId: number | string, question: string, notice = '') {
  const tid = question.trim()
    ? (await api<{ id: string }>(`/projects/${projectId}/threads`, 'POST')).id
    : '';
  // [왜] 대화 만들기가 실패하면 안내를 남기지 않는다(다음에 이 프로젝트를 열 때 엉뚱하게 뜨지 않게)
  startNotice.current = notice ? { project: String(projectId), text: notice } : null;
  if (!tid) return navigate('/app?project=' + projectId);
  pendingStart.current = { tid, question, conditions: '', target: '' };
  navigate(`/app?project=${projectId}&thread=${tid}`);
}
/** 검토할 부품(읽기 전용). 대상은 서버가 질문 · 회로로 정하거나 대화에서 묻는다(SPEC 8.9, #30). status는 작업대가 정한 진행 안내. */
export function TargetInfo({
  project,
  target,
  status,
  alert = false,
}: {
  project: Project | null;
  target: string;
  status: string;
  alert?: boolean;
}) {
  const parts = partsOf(project),
    diodes = parts.filter((p) => /^D\d/i.test(p.ref)),
    usable = diodes.filter((p) => !unsupportedPartReason(p)),
    part = parts.find((p) => p.ref === target);
  return (
    <div className="part-selector">
      <h2>검토할 부품</h2>
      <p className="target-value" aria-label="검토할 부품">
        {part ? `${part.ref} · ${part.value}` : target || '아직 정하지 않음'}
      </p>
      {usable.length ? (
        <p className="muted" aria-label="회로의 다이오드">
          회로의 다이오드: {usable.map((p) => `${p.ref} · ${p.value}`).join(', ')}
        </p>
      ) : (
        <p>회로에 판정할 수 있는 다이오드가 없습니다. 넷리스트를 첨부해 주세요.</p>
      )}
      {/* [왜] LED·표시기는 대체 판정을 지원하지 않는다(서버가 422). 대상이 정해지기 전에만 사실 한 줄로 알린다(#50) */}
      {!target &&
        diodes
          .filter((p) => unsupportedPartNote(p))
          .map((p) => (
            <p className="muted" key={p.ref}>
              {unsupportedPartNote(p)}
            </p>
          ))}
      <p className="part-status" role={alert ? 'alert' : undefined}>
        {status}
      </p>
    </div>
  );
}
type Progress = { start: number; end: number | null; steps: Step[] };
/**
 * 검토 진행(#42): 단계마다 한 줄(✓ 끝 · 도는 표시 지금)과 그 단계 시간, 맨 아래 총 시간. status가 오면 끝난 실행의 접힌 요약 한 줄(누르면 펼침).
 * 시간은 status 프레임이 도착한 시각(performance.now())으로 화면에서 잰다. 단계는 저장하지 않아 새로고침 뒤에는 시간 없이 서버의 지금 단계 한 줄만 보인다.
 */
function RunProgress({
  progress,
  stage,
  status,
  onStop,
}: {
  progress: Progress | null;
  stage: string;
  status?: string;
  onStop?: () => void;
}) {
  const ticking = !status && progress?.end === null;
  const [, tick] = useState(0);
  useEffect(() => {
    if (!ticking) return;
    const timer = setInterval(() => tick((n) => n + 1), 200);
    return () => clearInterval(timer);
  }, [ticking]);
  const steps = progress?.steps ?? [],
    now = progress?.end ?? performance.now(),
    // [왜] 수신을 멈췄다가 복구한 실행은 끝난 시각이 없다. 틀린 초를 보이지 않고 단계만 보인다
    timed = !status || progress?.end != null;
  const list = (
    <ol className="progress-steps" aria-label="검토 진행 단계">
      {steps.length ? (
        steps.map((s, i) => {
          const current = ticking && i === steps.length - 1;
          return (
            <li key={s.stage} className={current ? 'current' : 'done'}>
              {current ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />}
              {s.stage}
              {timed && <span className="step-time">{seconds(stepMs(steps, i, now))}</span>}
            </li>
          );
        })
      ) : (
        <li className="current">
          <LoaderCircle size={14} className="spin" />
          {stage || '검토를 시작하는 중'}
        </li>
      )}
    </ol>
  );
  const total = progress && timed && (
    <p className="progress-total">총 {seconds(now - progress.start)}</p>
  );
  // 새로고침한 끝난 실행: 단계 · 시간 기록이 없어 상태만 한 줄로 보인다
  if (status && !steps.length)
    return (
      <div className="progress progress-summary">
        <Check size={14} />
        {status}
      </div>
    );
  if (status)
    return (
      <details className="progress progress-summary">
        <summary>
          <Check size={14} />
          {[
            status,
            steps.length + '단계',
            ...(timed && progress ? [seconds(now - progress.start)] : []),
          ].join(' · ')}
        </summary>
        {list}
        {total}
      </details>
    );
  return (
    <div className="progress">
      <div className="progress-head">
        <span>검토 진행</span>
        {/* [왜] 멈춤은 통용되는 ■ 모양으로 보인다(#14). 이름은 aria-label로 남긴다 */}
        <button aria-label="수신 중지" title="수신 중지" onClick={onStop}>
          <Square size={16} fill="currentColor" />
        </button>
      </div>
      {/* [왜] 초는 0.2초마다 바뀌어 읽기 영역에 두지 않는다. 바뀐 단계 이름만 알린다 */}
      <p className="sr-only" role="status">
        {steps.at(-1)?.stage ?? (stage || '검토를 시작하는 중')}
      </p>
      {list}
      {total}
    </div>
  );
}
/** 회로 구역: 연결 개념도와 원본 회로도를 한 구역에 펼쳐 넷리스트를 올리면 둘을 바로 같이 본다. 누르면 큰 창. */
export function CircuitSection({
  project,
  target,
  threadId,
}: {
  project: Project | null;
  target: string;
  threadId: string | null;
}) {
  const usable = partsOf(project).filter((p) => /^D\d/i.test(p.ref) && !unsupportedPartReason(p));
  return (
    <section className="circuit-section" id="circuit-section">
      <h2>회로</h2>
      {/* [왜] 대상을 아직 안 정했으면(#16 서버가 정하거나 묻는다) 판정 가능한 다이오드마다 개념도를 보인다(#11) */}
      {(target ? [target] : usable.length ? usable.slice(0, 6).map((p) => p.ref) : ['']).map(
        (ref) => (
          <Circuit key={ref} project={project} target={ref} zoomable />
        ),
      )}
      {project && <SchematicSection project={project} threadId={threadId} />}
    </section>
  );
}
/** 회로가 필요한 질문에 서버가 넷리스트를 달라고 답했을 때 그 답 아래 카드(#30): 넷리스트 첨부, 또는 기존 회로(최근 5개, 데모 모드면 데모 회로)로 계속. */
function CircuitRequest({
  projectId,
  question,
  replay,
  onAttach,
}: {
  projectId: string;
  question: string;
  replay: boolean;
  onAttach: () => void;
}) {
  const projects = useResource<Project[]>('/projects'),
    demos = useResource<Demo[]>('/demo-circuits'); // [주의] 운영(DEMO_MODE=0)은 404라 데모 회로만 빠진다
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  const circuits = (projects.data ?? [])
    .filter((p) => p.circuit_version > 0 && String(p.id) !== projectId)
    .slice(0, 5);
  async function pick(project: () => Promise<number>) {
    setBusy(true);
    setError(null);
    try {
      const id = await project();
      refreshNavigation();
      // [왜] 키 없는 데모는 기록한 질문만 재생한다. 질문을 다시 보내지 않고 그 회로의 기록 질문 버튼을 보인다
      await openWithQuestion(id, replay ? '' : question);
    } catch (e) {
      setError(e as Error);
      setBusy(false);
    }
  }
  return (
    <div className="missing-input" data-testid="circuit-request">
      <div className="actions">
        <button type="button" className="primary" onClick={onAttach}>
          <Paperclip size={15} />
          넷리스트 첨부
        </button>
      </div>
      {(circuits.length > 0 || !!demos.data?.length) && (
        <>
          <p>기존 회로로 계속</p>
          <div className="actions">
            {circuits.map((p) => (
              <button
                key={p.id}
                type="button"
                disabled={busy}
                onClick={() => pick(async () => p.id)}
              >
                {p.name}
              </button>
            ))}
            {demos.data?.map((d) => (
              <button
                key={d.id}
                type="button"
                disabled={busy}
                onClick={() =>
                  pick(
                    async () =>
                      (
                        await api<Project>('/projects?allow_duplicate=true', 'POST', {
                          name: d.name,
                          demo_id: d.id,
                        })
                      ).id,
                  )
                }
              >
                {d.name}
              </button>
            ))}
          </div>
        </>
      )}
      <ErrorBox error={error} />
    </div>
  );
}
/** 사용자가 회로 패널을 닫았으면 이 브라우저에 남겨 프로젝트를 열 때 다시 저절로 열지 않는다(#47, 첫 회로 첨부 때는 연다). 다시 열면 지운다 */
const PANEL_CLOSED = 'sojafit.panel.closed';
export function Workbench({ projectId, threadId }: { projectId: string; threadId: string | null }) {
  const project = useResource<Project>(
      `/projects/${projectId}${threadId ? '?thread_id=' + threadId : ''}`,
    ),
    roles = useResource<Role[]>('/judge/roles'),
    questions = useResource<DemoQuestion[]>('/demo-questions'),
    quotes = useResource<Quote[]>(`/projects/${projectId}/quotes`);
  const [detail, setDetail] = useState<Detail | null>(null),
    [runs, setRuns] = useState<Record<string, Run>>({}),
    [active, setActive] = useState<Run | null>(null),
    // 비어 있으면 서버가 질문 · 회로로 정하거나 사용자에게 묻는다(SPEC 8.9). 첫 다이오드를 미리 고르지 않는다
    [target, setTarget] = useState(''),
    [question, setQuestion] = useState(''),
    [conditions, setConditions] = useState(''),
    [attachment, setAttachment] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [stopped, setStopped] = useState(false),
    [pendingQuestion, setPendingQuestion] = useState(''),
    // 이번 실행에서 받은 진행 단계(SSE status의 stage)와 도착 시각(#42). 마지막이 지금 단계다
    [progress, setProgress] = useState<Progress | null>(null),
    [selected, setSelected] = useState<{ c: Candidate; r: Run } | null>(null),
    [showQuotes, setShowQuotes] = useState(false),
    [showParts, setShowParts] = useState(false),
    [remove, setRemove] = useState<'project' | 'thread' | null>(null),
    [rename, setRename] = useState(false),
    [reload, setReload] = useState(0),
    [notice, setNotice] = useState<{ text: string; thread: string | null } | null>(null);
  const controller = useRef<AbortController | null>(null),
    runId = useRef<string | null>(null),
    scope = useRef(0);
  const attach = useNetlistAttach('.net,.txt,.kicad_sch', setAttachment);
  const parts = partsOf(project.data),
    usable = parts.filter((p) => /^D\d/i.test(p.ref) && !unsupportedPartReason(p)),
    // [왜] 과거 LED 대화처럼 지원하지 않는 부품이 대상이면 보내기 전에 이유를 보인다(서버도 422)
    targetReason = (() => {
      const chosen = parts.find((p) => p.ref === target);
      return chosen ? unsupportedPartReason(chosen) : '';
    })();
  useEffect(() => {
    if (startNotice.current?.project !== projectId) return;
    // [왜] 작업대는 프로젝트마다 한 번 그려져 같은 프로젝트의 다른 대화로 옮겨도 남는다. 처음 연 대화에서만 보인다
    setNotice({ text: startNotice.current.text, thread: threadId });
    startNotice.current = null;
  }, [projectId]);
  useEffect(() => {
    let live = true;
    scope.current++;
    controller.current?.abort();
    setDetail(null);
    setRuns({});
    setActive(null);
    setError(null);
    setBusy(false);
    setStopped(false);
    setPendingQuestion('');
    setProgress(null);
    setSelected(null);
    // [왜] 작업대는 프로젝트마다 한 번 그려져(App의 key) 대화를 옮겨도 남는다. 대상은 대화의 것이라 비우고, 대화가 있으면 불러온 target_ref로 다시 정한다(#53)
    setTarget('');
    setLoading(!!threadId);
    runId.current = null;
    if (threadId)
      api<Detail>('/threads/' + threadId)
        .then(async (d) => {
          if (!live) return;
          setDetail(d);
          setTarget(d.target_ref ?? '');
          const ids = [
            ...new Set([
              ...d.messages.map((m) => m.run_id),
              ...(d.latest_run ? [d.latest_run.id] : []),
            ]),
          ];
          const all = await Promise.all(ids.map((id) => api<Run>('/runs/' + id)));
          if (live) {
            setRuns(Object.fromEntries(all.map((r) => [r.id, r])));
            const latest = all.find((r) => r.id === d.latest_run?.id);
            setActive(latest ?? null);
            runId.current = latest?.id ?? null;
            const queued = pendingStart.current;
            if (queued?.tid === threadId) {
              pendingStart.current = null;
              setLoading(false);
              setTarget(queued.target);
              setPendingQuestion(queued.question);
              void execute(threadId, `/threads/${threadId}/runs`, {
                question: queued.question,
                conditions: queued.conditions,
                ...(queued.target ? { target_ref: queued.target } : {}),
              });
            }
          }
        })
        .catch((e) => {
          if (live) setError(e);
        })
        .finally(() => {
          if (live) setLoading(false);
        });
    return () => {
      live = false;
    };
  }, [threadId, projectId, reload]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    // [왜] 사이드바에서 대화 이름을 바꾸면 제목만 고친다. 다시 읽으면 불러온 이전 메시지와 실행 중 수신이 끊긴다
    const fn = (e: Event) => {
      const t = (e as CustomEvent<{ id: string; title: string }>).detail;
      setDetail((d) => (d && d.id === t.id ? { ...d, title: t.title } : d));
    };
    window.addEventListener('thread-renamed', fn);
    return () => window.removeEventListener('thread-renamed', fn);
  }, []);
  useEffect(() => {
    // [왜] 사이드바에서 프로젝트 이름을 바꾸면 제목만 고친다. 다시 읽으면 작업대 전체가 불러오는 중으로 바뀐다
    const fn = (e: Event) => {
      const p = (e as CustomEvent<Project>).detail;
      project.setData((d) => (d && d.id === p.id ? { ...d, name: p.name } : d));
    };
    window.addEventListener('project-renamed', fn);
    return () => window.removeEventListener('project-renamed', fn);
  }, []);
  // 오른쪽 회로 패널(#39 #47): "회로 보기"로 열고 닫는다. 회로가 처음 생기면(첨부 v0 → v1) 열고,
  // 회로가 있는 프로젝트를 열 때도 한 번 연다. 단 사용자가 닫아 둔 브라우저면 프로젝트를 열 때는 열지 않고, 좁은 화면은 둘 다 열지 않는다
  const [panel, setPanel] = useState(false),
    hadCircuit = useRef<boolean | null>(null),
    version = project.data?.circuit_version;
  useEffect(() => {
    if (version === undefined) return; // [왜] 첨부 뒤 다시 읽는 동안은 값이 없다. 이전 값을 지우지 않는다
    let closed = false;
    try {
      closed = localStorage.getItem(PANEL_CLOSED) === '1';
    } catch {
      // 저장소를 못 쓰면 처음 보는 사람처럼 연다
    }
    // [왜] 760px 이하에서는 패널이 화면 전체를 덮는 시트라 저절로 열면 대화가 가려진다(#51). "회로 보기"로만 연다
    const narrow = matchMedia('(max-width: 760px)').matches;
    if (
      !narrow &&
      version > 0 &&
      (hadCircuit.current === false || (hadCircuit.current === null && !closed))
    )
      setPanel(true);
    hadCircuit.current = version > 0;
  }, [version]);
  function choosePanel(open: boolean) {
    setPanel(open);
    try {
      if (open) localStorage.removeItem(PANEL_CLOSED);
      else localStorage.setItem(PANEL_CLOSED, '1');
    } catch {
      // 저장소를 못 쓰면 이번 화면에서만 따른다
    }
  }
  // 답 머리의 "회로 보기"(#47): 패널을 열고, 패널이 그려진 뒤 회로 구역으로 내린다
  function showCircuit() {
    choosePanel(true);
    requestAnimationFrame(() =>
      document.getElementById('circuit-section')?.scrollIntoView({ block: 'start' }),
    );
  }
  const part = parts.find((p) => p.ref === target),
    availableQuestions =
      questions.data?.filter(
        (q) => q.demo_id === project.data?.demo_id && (!target || q.target === target),
      ) ?? [];
  const currentDemo =
    questions.data?.find(
      (q) =>
        q.question ===
          (pendingQuestion || detail?.messages.find((m) => m.role === 'user')?.content) &&
        q.demo_id === project.data?.demo_id,
    ) ?? questions.data?.find((q) => detail?.title === q.question);
  async function refreshDetail(tid: string) {
    const d = await api<Detail>('/threads/' + tid);
    setDetail(d);
    if (d.target_ref) setTarget(d.target_ref); // 서버가 정했거나 사용자가 고른 대상
    refreshNavigation();
    return d;
  }
  async function recover() {
    if (!runId.current) return;
    setError(null);
    try {
      const r = await api<Run>(`/runs/${runId.current}/recover`, 'POST');
      setActive(r);
      setRuns((x) => ({ ...x, [r.id]: r }));
      await refreshDetail(r.thread_id);
      setStopped(r.result.status === 'running');
    } catch (e) {
      setError(e as Error);
    }
  }
  async function execute(tid: string, path: string, body: any) {
    const localScope = scope.current;
    setBusy(true);
    setError(null);
    setStopped(false);
    setProgress({ start: performance.now(), end: null, steps: [] });
    const abort = new AbortController();
    controller.current = abort;
    let liveRun = runId.current;
    let terminal: Result | null = null;
    try {
      await streamRun(path, body, abort.signal, (event, data) => {
        if (localScope !== scope.current) return;
        if (event === 'run_started') {
          liveRun = data.run_id;
          runId.current = data.run_id;
          setActive({ id: data.run_id, thread_id: tid, message_id: null, result: freshResult() });
        } else {
          // [왜] 재계획이면 같은 단계가 다시 온다. 앞의 것을 지우고 끝에 붙여 마지막이 늘 지금 단계가 되게 한다(addStep)
          const now = performance.now();
          if (event === 'status')
            setProgress((p) => p && { ...p, steps: addStep(p.steps, data.stage, now) });
          else {
            terminal = data;
            setProgress((p) => p && { ...p, end: now });
          }
          setActive({ id: liveRun ?? '', thread_id: tid, message_id: null, result: data });
        }
      });
      if (localScope !== scope.current) return;
      if (liveRun) {
        const saved = await api<Run>('/runs/' + liveRun);
        if (terminal) saved.result = terminal;
        setActive(saved);
        setRuns((x) => ({ ...x, [saved.id]: saved }));
      }
      await refreshDetail(tid);
      setPendingQuestion('');
    } catch (e) {
      if (localScope !== scope.current) return;
      setStopped(true);
      if ((e as Error).name !== 'AbortError') setError(e as Error);
    } finally {
      if (localScope === scope.current) setBusy(false);
    }
  }
  async function send(demo?: DemoQuestion) {
    // [왜] 실행 중에도 질문은 미리 쓸 수 있다. 보내기는 막는다(같은 대화의 두 번째 run은 서버가 409)
    if (busy) return;
    setError(null);
    if (!demo && !question.trim() && !attachment) return;
    try {
      let tid = threadId;
      if (attachment) {
        if (attachment.size > 5 * 1024 * 1024)
          throw new Error('넷리스트·회로도는 5 MiB 이하여야 합니다.');
        const body = new FormData();
        body.set('file', attachment);
        // [왜] 회로 없이 시작한 대화면 같은 대화에 회로를 붙인다(서버가 조건을 다시 본다, SPEC 4절). 아니면 새 버전 · 새 대화
        const same = tid && !project.data?.circuit_version ? '?thread_id=' + tid : '';
        const imported = await api<{ project: Project; thread_id: string }>(
          `/projects/${projectId}/netlist${same}`,
          'POST',
          body,
        );
        setAttachment(null);
        project.setData(imported.project);
        setTarget('');
        refreshNavigation();
        if (imported.thread_id !== tid)
          return navigate(`/app?project=${projectId}&thread=${imported.thread_id}`);
        if (!question.trim()) return; // 같은 대화에 붙였고 함께 쓴 질문이 있으면 이어서 보낸다
      }
      if (targetReason) throw new Error(targetReason);
      if (demo || !tid) {
        const created = await api<{ id: string }>(`/projects/${projectId}/threads`, 'POST');
        tid = created.id;
        // [왜] 새 대화 이동과 첫 실행을 분리해 이전 대화의 비동기 결과가 새 화면을 덮지 않게 한다.
        pendingStart.current = {
          tid,
          question: demo?.question ?? question,
          conditions: demo?.conditions ?? conditions,
          target: demo?.target ?? target,
        };
        setQuestion('');
        navigate(`/app?project=${projectId}&thread=${tid}`);
        return;
      }
      const text = question,
        cond = conditions;
      setPendingQuestion(text);
      setQuestion('');
      runId.current = null;
      await execute(tid!, `/threads/${tid}/runs`, {
        question: text,
        ...(target ? { target_ref: target } : {}),
        conditions: cond,
      });
    } catch (e) {
      setError(e as Error);
    }
  }
  async function resume(body: any) {
    if (body.target) setTarget(body.target); // 고른 부품을 오른쪽 회로 패널의 연결 개념도 · 후보 상세에 바로 보인다
    if (active) await execute(active.thread_id, `/runs/${active.id}/resume`, body);
  }
  async function older() {
    if (!detail?.next_before_message_id || !threadId) return;
    setError(null);
    try {
      const older = await api<Detail>(
        `/threads/${threadId}?before_message_id=${detail.next_before_message_id}`,
      );
      const loaded = await Promise.all(
        [...new Set(older.messages.map((m) => m.run_id))].map((id) => api<Run>('/runs/' + id)),
      );
      setRuns((x) => ({ ...x, ...Object.fromEntries(loaded.map((r) => [r.id, r])) }));
      setDetail((d) =>
        d
          ? {
              ...d,
              messages: [...older.messages, ...d.messages],
              next_before_message_id: older.next_before_message_id,
            }
          : d,
      );
    } catch (e) {
      setError(e as Error);
    }
  }
  async function newReview() {
    try {
      const t = await api<{ id: string }>(`/projects/${projectId}/threads`, 'POST');
      refreshNavigation();
      navigate(`/app?project=${projectId}&thread=${t.id}`);
    } catch (e) {
      setError(e as Error);
    }
  }
  const waiting = active?.result.status === 'requires_input',
    // 조건이 아니라 대상 부품을 묻는 중(SPEC 8.9)
    choosing = waiting && !!active?.result.interrupt.target_choices?.length,
    running = busy || active?.result.status === 'running',
    sendDisabled =
      busy || (!attachment && (!!waiting || !!running || !!targetReason || !question.trim())),
    // 회로 없는 대화에서 회로가 필요한 질문의 답(SPEC 8.9). 회로를 붙이면 카드가 사라진다
    needsCircuit =
      !running &&
      active?.result.status === 'refused' &&
      active.result.answer === NEEDS_CIRCUIT &&
      !project.data?.circuit_version,
    // 회로가 있고 바꿀 부품이 정해진 대화의 답에만 "회로 보기"를 붙인다(#47). 판정 · 역할 답은 대상이 정해진 뒤에 나온다
    circuitLink = project.data?.circuit_version && target ? showCircuit : undefined,
    lastQuestion =
      detail?.messages.filter((m) => m.role === 'user').slice(-1)[0]?.content ?? pendingQuestion;
  const previous =
    detail?.messages.filter((m) => m.role === 'assistant' && m.run_id !== active?.id) ?? [];
  return (
    <div className="workbench">
      <div className="workbench-header">
        <div>
          <span className="breadcrumb">프로젝트 / {threadId ? '검토' : '부품 선택'}</span>
          <h1>{project.data?.name ?? '회로 불러오기'}</h1>
        </div>
        <div className="header-actions">
          <button
            aria-label="회로 보기"
            title="회로 보기"
            aria-expanded={panel}
            onClick={() => choosePanel(!panel)}
          >
            <PanelRight size={16} />
            <span className="desktop-only">회로 보기</span>
          </button>
          <button onClick={() => setShowQuotes(true)}>견적 목록</button>
          <button aria-label="부품 점검표" title="부품 점검표" onClick={() => setShowParts(true)}>
            <ListChecks size={16} />
            <span className="desktop-only">부품 점검표</span>
          </button>
          <RowMenu
            label="프로젝트 메뉴"
            items={[
              { label: '이름 변경', icon: <Pencil size={14} />, onSelect: () => setRename(true) },
              {
                label: '삭제',
                icon: <Trash2 size={14} />,
                danger: true,
                onSelect: () => setRemove('project'),
              },
            ]}
          />
        </div>
      </div>
      {project.loading ? (
        <Loading />
      ) : project.error ? (
        <ErrorBox error={project.error} retry={project.reload} />
      ) : (
        <div className={'workbench-grid' + (panel ? ' panel-open' : '')}>
          {/* [왜] 패널 머리(닫기 · 너비 조절)는 aside 밖 형제로 두고 CSS가 같은 오른쪽 칸에 겹친다(aside 내용과 따로 고친다) */}
          {panel && (
            <div className="panel-bar">
              <ResizeHandle
                name="panel-w"
                label="회로 패널 너비 조절"
                min={280}
                max={640}
                edge="left"
              />
              <button
                className="icon-button"
                aria-label="회로 패널 닫기"
                title="회로 패널 닫기"
                onClick={() => choosePanel(false)}
              >
                <X size={18} />
              </button>
            </div>
          )}
          <aside className="context-panel">
            <TargetInfo
              project={project.data}
              target={target}
              alert={!!targetReason}
              status={
                // [왜] 패널에는 고르는 칸이 없어 422 문구("골라 주세요") 대신 사실 한 줄을 보인다(#50)
                targetReason && part
                  ? unsupportedPartNote(part)
                  : waiting
                    ? choosing
                      ? '바꿀 부품을 고르면 이어서 검토합니다.'
                      : '사용 조건을 기다리고 있습니다.'
                    : active
                      ? statuses[active.result.status]
                      : part
                        ? '이 부품으로 검토합니다.'
                        : usable.length
                          ? '질문에 적은 부품으로 정하고, 여럿이면 대화에서 물어봅니다.'
                          : '넷리스트를 대화에 첨부해 주세요.'
              }
            />
            <CircuitSection project={project.data} target={target} threadId={threadId} />
          </aside>
          <section className="conversation" {...attach.dropZone}>
            <div className="conversation-heading">
              <h2>{detail?.title || '새 검토'}</h2>
              {threadId && (
                <button
                  className="icon-button"
                  aria-label="이 검토 삭제"
                  title="이 검토 삭제"
                  disabled={!!running}
                  onClick={() => setRemove('thread')}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
            <div className="conversation-scroll">
              {notice?.thread === threadId && (
                <div className="notice" role="status">
                  <p>{notice.text}</p>
                </div>
              )}
              <ErrorBox
                error={error}
                retry={() => (threadId ? setReload((v) => v + 1) : project.reload())}
              />
              {loading ? (
                <Loading label="검토 기록을 불러오는 중" />
              ) : (
                <>
                  {!detail?.messages.length && !pendingQuestion && !active && (
                    // 새 대화 화면 안내와 같은 모양(가운데 맞춤 제목 + 흐린 짧은 글, #41)
                    <div className="conversation-start">
                      <h2>어떤 부품으로 바꾸고 싶으세요?</h2>
                      <p>
                        후보 품번과 사용 조건을 알려주세요.
                        <br />
                        회로 역할에 필요한 조건부터 확인합니다.
                      </p>
                    </div>
                  )}
                  {detail?.next_before_message_id && (
                    <button onClick={older}>이전 대화 불러오기</button>
                  )}
                  {detail?.messages
                    .filter((m) => m.role === 'user')
                    .map((m) => (
                      <div key={m.id}>
                        <div className="user-message">
                          <span className="sr-only">내 질문</span>
                          <p>{m.content}</p>
                        </div>
                        {previous
                          .filter((a) => a.run_id === m.run_id)
                          .map((a) =>
                            runs[a.run_id] ? (
                              <Reply
                                key={a.id}
                                run={runs[a.run_id]}
                                onCandidate={(c, r) => setSelected({ c, r })}
                                onCircuit={circuitLink}
                              />
                            ) : (
                              // 실행 기록을 받지 못했을 때 보이는 저장된 답. 면책 문구는 답마다 한 번(#46)
                              <div key={a.id} className="assistant-reply">
                                <div className="markdown">
                                  <Markdown>{a.content}</Markdown>
                                </div>
                                <Disclaimer />
                              </div>
                            ),
                          )}
                      </div>
                    ))}
                  {pendingQuestion &&
                    !detail?.messages.some((m) => m.content === pendingQuestion) && (
                      <div className="user-message">
                        <span className="sr-only">내 질문</span>
                        <p>{pendingQuestion}</p>
                      </div>
                    )}
                  {active && running && !stopped && (
                    <RunProgress
                      progress={progress}
                      stage={active.result.stage}
                      onStop={() => {
                        controller.current?.abort();
                        setStopped(true);
                      }}
                    />
                  )}
                  {active && !running && !stopped && (
                    <RunProgress
                      progress={progress}
                      stage=""
                      status={statuses[active.result.status] ?? active.result.status}
                    />
                  )}
                  {stopped && (
                    <div className="notice">
                      <p>실시간 수신을 멈췄습니다. 서버 검토는 계속될 수 있습니다.</p>
                      <button onClick={recover}>저장된 상태 확인</button>
                    </div>
                  )}
                  {waiting && roles.error && <ErrorBox error={roles.error} retry={roles.reload} />}
                  {choosing && active && (
                    <TargetChoice
                      result={active.result}
                      busy={busy}
                      onResume={resume}
                      onCircuit={showCircuit}
                    />
                  )}
                  {waiting && !choosing && active && (
                    <MissingInput
                      key={active.id}
                      result={active.result}
                      roles={roles.data ?? []}
                      demo={currentDemo}
                      busy={busy}
                      onResume={resume}
                    />
                  )}
                  {active && !waiting && !running && (
                    <Reply
                      run={active}
                      onCandidate={(c, r) => setSelected({ c, r })}
                      onCircuit={circuitLink}
                    />
                  )}
                  {needsCircuit && (
                    <CircuitRequest
                      projectId={projectId}
                      question={lastQuestion}
                      replay={!!questions.data}
                      onAttach={() => {
                        // 첨부하고 보내면 같은 질문을 이어서 다시 묻도록 비어 있는 입력창에 앞 질문을 둔다
                        if (!question.trim()) setQuestion(lastQuestion);
                        attach.input.current?.click();
                      }}
                    />
                  )}
                  {active?.result.status === 'failed' && (
                    <button onClick={newReview}>새 검토로 다시 시작</button>
                  )}
                </>
              )}
            </div>
            <div className="composer-area">
              {questions.data && (
                <details className="demo-questions" open={!active && !detail?.messages.length}>
                  <summary>기록된 데모 질문</summary>
                  {availableQuestions.length ? (
                    <div>
                      {availableQuestions.map((q) => (
                        <button
                          key={q.id}
                          disabled={busy || !!targetReason}
                          onClick={() => send(q)}
                          data-demo-id={q.id}
                        >
                          {q.question}
                          <ArrowRight size={15} />
                        </button>
                      ))}
                    </div>
                  ) : (
                    <p>
                      이 부품에는 기록된 질문이 없습니다. 데모 질문이 있는 회로와 부품을 선택해
                      주세요.
                    </p>
                  )}
                </details>
              )}
              {questions.error && (questions.error as ApiError).status !== 404 && (
                <ErrorBox error={questions.error} retry={questions.reload} />
              )}
              <form
                className="composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send();
                }}
              >
                {attachment && (
                  <AttachmentCard file={attachment} onRemove={() => setAttachment(null)} />
                )}
                <label className="sr-only" htmlFor="question">
                  검토 질문
                </label>
                <textarea
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (!isSendKey(e.nativeEvent)) return; // Shift+Enter · 한글 조합 중 Enter는 그대로(#38)
                    e.preventDefault();
                    if (!sendDisabled) void send();
                  }}
                  maxLength={4000}
                  // [왜] 실행 중에도 다음 질문을 쓸 수 있게 막지 않는다. 조건 입력을 기다릴 때만 막는다
                  disabled={!!waiting}
                  placeholder={
                    choosing
                      ? '위에서 바꿀 부품을 고르면 이어서 검토합니다.'
                      : waiting
                        ? '위의 사용 조건을 입력하면 이어서 검토합니다.'
                        : // [왜] 특정 부품 번호를 예로 들지 않는다. 회로가 없으면 새 대화와 같은 안내(#45)
                          project.data?.circuit_version
                          ? '이 회로에서 궁금한 점이나 바꿀 부품을 물어보세요'
                          : '+로 넷리스트를 첨부해 회로를 읽히거나, 궁금한 부품을 물어보세요'
                  }
                />
                <div className="composer-controls">
                  {/* 실행 중에도 파일은 고를 수 있다. 보내기는 아래 버튼이 막는다 */}
                  {attach.button}
                  <details className="conditions-editor">
                    <summary>사용 조건</summary>
                    <label>
                      전압·전류·온도 등
                      <textarea
                        value={conditions}
                        maxLength={2000}
                        onChange={(e) => setConditions(e.target.value)}
                        placeholder="알고 있는 조건을 입력하세요."
                      />
                    </label>
                  </details>
                  {running && (
                    <small className="composer-hint">답변이 끝나면 보낼 수 있습니다.</small>
                  )}
                  <button
                    className="primary send"
                    disabled={sendDisabled}
                    aria-label={attachment ? '넷리스트 보내기' : '질문 보내기'}
                    title={attachment ? '넷리스트 보내기' : '질문 보내기'}
                  >
                    <CornerDownLeft size={17} />
                  </button>
                </div>
              </form>
            </div>
            {attach.overlay}
          </section>
        </div>
      )}
      {selected && (
        <CandidateDetails
          candidate={selected.c}
          result={selected.r.result}
          project={project.data}
          target={target}
          messageId={
            runs[selected.r.id]?.message_id ??
            (active?.id === selected.r.id ? active.message_id : null) ??
            selected.r.message_id
          }
          roles={roles.data ?? []}
          close={() => {
            setSelected(null);
            quotes.reload();
          }}
        />
      )}
      {showQuotes && (
        <Modal title="저장된 견적" close={() => setShowQuotes(false)}>
          {quotes.loading ? (
            <Loading />
          ) : quotes.error ? (
            <ErrorBox error={quotes.error} retry={quotes.reload} />
          ) : quotes.data?.length ? (
            quotes.data.map((q) => (
              <article className="quote-item" key={q.id}>
                <h3>{q.part_number}</h3>
                <p>
                  {q.quantity.toLocaleString()}개 · {new Date(q.created_at).toLocaleString('ko-KR')}
                </p>
                <a href={`/app?project=${projectId}&thread=${q.thread_id}`}>검토로 돌아가기</a>
                <PriceLookup part={q.part_number} quantity={q.quantity} />
              </article>
            ))
          ) : (
            <p>아직 저장한 견적이 없습니다. 후보를 승인한 뒤 수량을 입력해 저장하세요.</p>
          )}
        </Modal>
      )}
      {showParts && project.data && (
        <PartsDialog
          projectId={projectId}
          version={project.data.circuit_version}
          close={() => setShowParts(false)}
          onReview={(text) => {
            // [왜] openWithQuestion은 새 대화를 만들고 바로 보낸다. 새 대화 화면 입력창에 써 두기만 하고 보내기는 사용자가 누른다(#68).
            //      작업대는 프로젝트마다 한 번 그려져(App의 key) 대화를 옮겨도 입력 글이 남는다
            setShowParts(false);
            setQuestion(text);
            if (threadId) navigate('/app?project=' + projectId);
            requestAnimationFrame(() => document.getElementById('question')?.focus());
          }}
          onAttach={() => {
            setShowParts(false);
            // [왜] 모달 창이 열려 있으면 바깥 파일 입력이 inert라 창이 닫힌 다음 프레임에 연다
            requestAnimationFrame(() => attach.input.current?.click());
          }}
        />
      )}
      {rename && (
        <Modal title="프로젝트 이름 변경" close={() => setRename(false)}>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const name = new FormData(e.currentTarget).get('name');
              try {
                await api('/projects/' + projectId, 'PATCH', { name });
                project.reload();
                refreshNavigation();
                setRename(false);
              } catch (e) {
                setError(e as Error);
              }
            }}
          >
            <label>
              프로젝트 이름
              <input name="name" defaultValue={project.data?.name} maxLength={200} required />
            </label>
            <div className="dialog-actions">
              {/* [왜] form 안이라 type="button"이 없으면 취소가 이름 저장을 보낸다 */}
              <button type="button" onClick={() => setRename(false)}>
                취소
              </button>
              <button className="primary">이름 저장</button>
            </div>
          </form>
          <ErrorBox error={error} />
        </Modal>
      )}
      {remove && (
        <Modal
          title={remove === 'project' ? '프로젝트를 삭제할까요?' : '검토를 삭제할까요?'}
          close={() => setRemove(null)}
        >
          <p>
            {remove === 'project'
              ? '이 프로젝트의 회로, 대화, 승인, 견적이 함께 삭제됩니다.'
              : '이 대화와 분석 기록이 삭제됩니다.'}{' '}
            복구할 수 없습니다.
          </p>
          <ErrorBox error={error} />
          <div className="dialog-actions">
            <button onClick={() => setRemove(null)}>취소</button>
            <button
              className="primary"
              onClick={async () => {
                try {
                  await api(
                    remove === 'project' ? '/projects/' + projectId : '/threads/' + threadId,
                    'DELETE',
                  );
                  setRemove(null);
                  refreshNavigation();
                  navigate(remove === 'project' ? '/app' : '/app?project=' + projectId);
                } catch (e) {
                  setError(e as Error);
                }
              }}
            >
              삭제
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
