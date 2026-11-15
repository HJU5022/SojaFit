/** 프로젝트·대화·실행 작업대. 서버의 고정 회로 버전과 결과를 사용한다. 출처: SPEC 4·7·8절. */
import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowRight,
  Check,
  ChevronRight,
  FileUp,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Square,
  Trash2,
  X,
} from 'lucide-react';
import { api, ApiError, fieldNames, statuses, streamRun } from './api';
import {
  Badge,
  Circuit,
  Disclaimer,
  Empty,
  ErrorBox,
  Loading,
  Modal,
  Source,
  navigate,
  partsOf,
  useResource,
} from './ui';
import { CandidateDetails, PriceLookup } from './Candidate';
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
  Thread,
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
export function refreshNavigation() {
  window.dispatchEvent(new Event('projects-changed'));
}
export function NewProject({
  close,
  onCreated,
}: {
  close: () => void;
  onCreated: (p: Project) => void;
}) {
  const demos = useResource<Demo[]>('/demo-circuits');
  const [mode, setMode] = useState<'demo' | 'upload' | 'empty'>('demo'),
    [name, setName] = useState(''),
    [demo, setDemo] = useState(''),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [duplicate, setDuplicate] = useState(false);
  return (
    <Modal title="새 프로젝트" close={close}>
      <p>넷리스트를 올리거나 공개 데모 회로로 시작하세요.</p>
      <div className="segmented">
        <button onClick={() => setMode('demo')} aria-pressed={mode === 'demo'}>
          데모 회로
        </button>
        <button onClick={() => setMode('upload')} aria-pressed={mode === 'upload'}>
          넷리스트 업로드
        </button>
        <button onClick={() => setMode('empty')} aria-pressed={mode === 'empty'}>
          나중에 첨부
        </button>
      </div>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            let result: Project;
            if (mode === 'upload') {
              if (!file) throw new Error('넷리스트를 첨부해 주세요.');
              if (file.size > 5 * 1024 * 1024) throw new Error('넷리스트는 5 MiB 이하여야 합니다.');
              const body = new FormData();
              body.set('name', name);
              body.set('file', file);
              result = await api(
                '/projects/upload' + (duplicate ? '?allow_duplicate=true' : ''),
                'POST',
                body,
              );
            } else
              result = await api('/projects' + (duplicate ? '?allow_duplicate=true' : ''), 'POST', {
                name,
                ...(mode === 'demo' ? { demo_id: demo } : {}),
              });
            refreshNavigation();
            onCreated(result);
            close();
          } catch (e) {
            setError(e as Error);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          프로젝트 이름
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={200}
            placeholder="예: 전원부 다이오드 교체"
          />
        </label>
        {mode === 'demo' &&
          (demos.loading ? (
            <Loading />
          ) : demos.error ? (
            <ErrorBox
              error={
                (demos.error as ApiError).status === 404
                  ? '이 환경에서는 데모 회로를 제공하지 않습니다. 넷리스트를 업로드해 주세요.'
                  : demos.error
              }
              retry={demos.reload}
            />
          ) : (
            <label>
              데모 회로
              <select
                aria-label="데모 회로"
                value={demo}
                required
                onChange={(e) => {
                  setDemo(e.target.value);
                  if (!name) setName(demos.data?.find((d) => d.id === e.target.value)?.name ?? '');
                }}
              >
                <option value="">회로를 선택하세요</option>
                {demos.data?.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
          ))}
        {mode === 'upload' && (
          <label className="file-drop">
            <FileUp />
            KiCad 넷리스트
            <input
              type="file"
              accept=".net"
              required
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <small>.net · UTF-8 · 최대 5 MiB</small>
          </label>
        )}
        {mode === 'empty' && (
          <p>프로젝트를 만든 뒤 검토 입력창에서 .net 또는 .txt 파일을 첨부할 수 있습니다.</p>
        )}
        <ErrorBox error={error} />
        {error instanceof ApiError && error.status === 409 && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={duplicate}
              onChange={(e) => setDuplicate(e.target.checked)}
            />
            같은 회로로 새 프로젝트 만들기
          </label>
        )}
        <button className="primary" disabled={busy || (mode === 'demo' && !demo)}>
          {busy ? '만드는 중…' : '프로젝트 만들기'}
          <ArrowRight size={16} />
        </button>
      </form>
    </Modal>
  );
}
export function ProjectList() {
  const projects = useResource<Project[]>('/projects'),
    [create, setCreate] = useState(false);
  return (
    <div className="page-content">
      <div className="page-heading">
        <div>
          <h1>프로젝트</h1>
          <p>회로 하나에서, 근거 있는 교체까지.</p>
        </div>
        <button className="primary" onClick={() => setCreate(true)}>
          <Plus size={17} />새 프로젝트
        </button>
      </div>
      {projects.loading ? (
        <Loading />
      ) : projects.error ? (
        <ErrorBox error={projects.error} retry={projects.reload} />
      ) : projects.data?.length ? (
        <div className="project-list">
          {projects.data.map((p) => (
            <a key={p.id} href={'/app?project=' + p.id} className="project-row">
              <div className="project-symbol">
                <svg viewBox="0 0 56 56">
                  <path
                    d="M8 28h12m16 0h12M20 17v22l16-11-16-11Zm16 0v22"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  />
                </svg>
              </div>
              <div>
                <h2>{p.name}</h2>
                <p>
                  {p.source_kind === 'demo' ? '데모 회로' : '업로드 회로'} ·{' '}
                  {p.circuit_version
                    ? '부품을 선택하고 검토를 이어가세요.'
                    : '넷리스트를 첨부해 주세요.'}
                </p>
              </div>
              <ChevronRight size={20} />
            </a>
          ))}
        </div>
      ) : (
        <Empty title="첫 회로를 가져오세요.">
          <p>KiCad 넷리스트를 올리거나 데모 회로로 시작할 수 있습니다.</p>
          <button className="primary" onClick={() => setCreate(true)}>
            새 프로젝트
          </button>
        </Empty>
      )}
      {create && (
        <NewProject
          close={() => setCreate(false)}
          onCreated={(p) => navigate('/app?project=' + p.id)}
        />
      )}
    </div>
  );
}
function MissingInput({
  result,
  roles,
  demo,
  busy,
  onResume,
}: {
  result: Result;
  roles: Role[];
  demo?: DemoQuestion;
  busy: boolean;
  onResume: (body: any) => void;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({}),
    [role, setRole] = useState('');
  return (
    <div className="missing-input" data-testid="requires-input">
      <div className="inline-heading">
        <MessageSquare size={20} />
        <h2>조건을 알려주시면 이어서 검토합니다.</h2>
      </div>
      <p>{result.interrupt.question}</p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onResume({
            answers: Object.fromEntries(Object.entries(answers).filter(([, v]) => v.trim())),
            ...(result.interrupt.role_choices?.length ? { role } : {}),
          });
        }}
      >
        {!!result.interrupt.role_choices?.length && (
          <label>
            회로에서 맡은 역할
            <select value={role} onChange={(e) => setRole(e.target.value)} required>
              <option value="">역할을 선택하세요</option>
              {result.interrupt.role_choices.map((code) => (
                <option key={code} value={code}>
                  {roles.find((r) => r.code === code)?.name ?? code}
                </option>
              ))}
            </select>
          </label>
        )}
        {result.interrupt.missing?.map((code) => (
          <label key={code}>
            {fieldNames[code] ?? code}
            <input
              value={answers[code] ?? ''}
              onChange={(e) => setAnswers({ ...answers, [code]: e.target.value })}
              maxLength={200}
              placeholder="값과 단위, 또는 모름"
            />
          </label>
        ))}
        <div className="actions">
          <button className="primary" disabled={busy}>
            이 값으로 계속 검토
          </button>
          <button
            type="button"
            disabled={busy || (!!result.interrupt.role_choices?.length && !role)}
            onClick={() =>
              onResume({ answers: {}, ...(result.interrupt.role_choices?.length ? { role } : {}) })
            }
          >
            모두 모름으로 계속
          </button>
        </div>
        {demo?.resume && (
          <div className="recorded-resume">
            <p>
              이 데모는 기록된 답으로 재개할 수 있습니다.
              {Object.entries(demo.resume.answers)
                .map(([k, v]) => ` ${fieldNames[k] ?? k}: ${v}`)
                .join('')}
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                onResume({
                  answers: demo.resume!.answers,
                  ...(demo.resume!.role ? { role: demo.resume!.role } : {}),
                })
              }
            >
              기록한 답으로 계속하기 <ArrowRight size={15} />
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
function Reply({ run, onCandidate }: { run: Run; onCandidate: (c: Candidate, r: Run) => void }) {
  const r = run.result,
    candidates = [
      ...(r.judgement.results ?? []),
      ...(r.judgement.shown ?? []),
      ...(r.judgement.unverified ?? []),
    ].filter((c, i, all) => all.findIndex((x) => x.part === c.part && x.role === c.role) === i);
  return (
    <div className="assistant-reply">
      <div className="reply-label">
        <span className="mini-mark">↳</span> SojaFit <span>{statuses[r.status] ?? r.stage}</span>
      </div>
      {candidates.length ? (
        <>
          <h2>후보별 검토 결과입니다.</h2>
          <div className="candidate-list">
            {candidates.map((c, i) => (
              <button key={i} className="candidate-card" onClick={() => onCandidate(c, run)}>
                <div>
                  <strong>{c.part}</strong>
                  <Badge verdict={c.verdict} />
                </div>
                <p>
                  {c.board_change === true
                    ? '기판 수정 필요'
                    : c.board_change === false
                      ? '기판 수정 불필요'
                      : '기판 수정 여부 확인 안 됨'}
                </p>
                <span>
                  조건과 근거 보기 <ArrowRight size={16} />
                </span>
              </button>
            ))}
          </div>
          <details className="full-answer">
            <summary>전체 답변 보기</summary>
            <div className="markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
            </div>
          </details>
        </>
      ) : r.answer ? (
        <div className="markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{r.answer}</ReactMarkdown>
        </div>
      ) : null}
      <ErrorBox error={r.error?.message ?? null} />
      {r.evidence.length > 0 && (
        <details className="evidence-list">
          <summary>문서 근거</summary>
          {r.evidence.map((s, i) => (
            <Source cite={s} key={i} />
          ))}
        </details>
      )}
      {r.price_parts.map((p) => (
        <PriceLookup key={p} part={p} />
      ))}
      <Disclaimer />
    </div>
  );
}
export function Workbench({ projectId, threadId }: { projectId: string; threadId: string | null }) {
  const project = useResource<Project>(
      `/projects/${projectId}${threadId ? '?thread_id=' + threadId : ''}`,
    ),
    threads = useResource<Thread[]>(`/projects/${projectId}/threads`),
    roles = useResource<Role[]>('/judge/roles'),
    questions = useResource<DemoQuestion[]>('/demo-questions'),
    quotes = useResource<Quote[]>(`/projects/${projectId}/quotes`);
  const [detail, setDetail] = useState<Detail | null>(null),
    [runs, setRuns] = useState<Record<string, Run>>({}),
    [active, setActive] = useState<Run | null>(null),
    [target, setTarget] = useState(''),
    [question, setQuestion] = useState(''),
    [conditions, setConditions] = useState(''),
    [attachment, setAttachment] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [stopped, setStopped] = useState(false),
    [pendingQuestion, setPendingQuestion] = useState(''),
    [selected, setSelected] = useState<{ c: Candidate; r: Run } | null>(null),
    [showQuotes, setShowQuotes] = useState(false),
    [remove, setRemove] = useState<'project' | 'thread' | null>(null),
    [rename, setRename] = useState(false),
    [reload, setReload] = useState(0);
  const pendingStart = useRef<{
    tid: string;
    question: string;
    conditions: string;
    target: string;
  } | null>(null);
  const controller = useRef<AbortController | null>(null),
    runId = useRef<string | null>(null),
    scope = useRef(0),
    end = useRef<HTMLDivElement>(null);
  const parts = partsOf(project.data),
    diodes = parts.filter((p) => /^D\d/i.test(p.ref));
  useEffect(() => {
    if (!target && diodes.length) setTarget(diodes[0].ref);
  }, [project.data, target]);
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
    setSelected(null);
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
                target_ref: queued.target,
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
  const part = parts.find((p) => p.ref === target),
    availableQuestions =
      questions.data?.filter((q) => q.demo_id === project.data?.demo_id && q.target === target) ??
      [];
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
    threads.reload();
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
          if (event !== 'status') terminal = data;
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
    setError(null);
    if (!demo && !question.trim() && !attachment) return;
    try {
      let tid = threadId;
      if (attachment) {
        if (attachment.size > 5 * 1024 * 1024) throw new Error('넷리스트는 5 MiB 이하여야 합니다.');
        const body = new FormData();
        body.set('file', attachment);
        const imported = await api<{ project: Project; thread_id: string }>(
          `/projects/${projectId}/netlist`,
          'POST',
          body,
        );
        setAttachment(null);
        project.setData(imported.project);
        setTarget('');
        refreshNavigation();
        navigate(`/app?project=${projectId}&thread=${imported.thread_id}`);
        return;
      }
      if (!target) throw new Error('먼저 검토할 다이오드를 선택해 주세요.');
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
        target_ref: target,
        conditions: cond,
      });
    } catch (e) {
      setError(e as Error);
    }
  }
  async function resume(body: any) {
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
    running = busy || active?.result.status === 'running';
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
          <button onClick={() => setShowQuotes(true)}>견적 목록</button>
          <button
            className="icon-button"
            aria-label="프로젝트 이름 변경"
            onClick={() => setRename(true)}
          >
            ···
          </button>
        </div>
      </div>
      {project.loading ? (
        <Loading />
      ) : project.error ? (
        <ErrorBox error={project.error} retry={project.reload} />
      ) : (
        <div className="workbench-grid">
          <aside className="context-panel">
            <div className="part-selector">
              <h2>검토할 부품</h2>
              <label>
                다이오드
                <select
                  aria-label="검토할 다이오드"
                  value={target}
                  disabled={detail?.target_locked || busy}
                  onChange={(e) => setTarget(e.target.value)}
                >
                  <option value="">부품 선택</option>
                  {diodes.map((p) => (
                    <option value={p.ref} key={p.ref}>
                      {p.ref} · {p.value}
                    </option>
                  ))}
                </select>
              </label>
              {!diodes.length && <p>회로에 다이오드가 없습니다. 넷리스트를 첨부해 주세요.</p>}
              <p className="part-status">
                {waiting
                  ? '사용 조건을 기다리고 있습니다.'
                  : active
                    ? statuses[active.result.status]
                    : part
                      ? '선택한 부품으로 검토할 준비가 되었습니다.'
                      : '회로를 먼저 가져오세요.'}
              </p>
            </div>
            <Circuit project={project.data} target={target} />
            <div className="review-nav">
              <div>
                <h2>검토 기록</h2>
                <button
                  className="icon-button"
                  aria-label="새 검토"
                  onClick={newReview}
                  disabled={busy}
                >
                  <Plus size={18} />
                </button>
              </div>
              <a className={!threadId ? 'active' : ''} href={'/app?project=' + projectId}>
                부품 고르기
              </a>
              {threads.loading ? (
                <Loading />
              ) : threads.error ? (
                <ErrorBox error={threads.error} retry={threads.reload} />
              ) : threads.data?.length ? (
                threads.data.map((t) => (
                  <a
                    key={t.id}
                    className={t.id === threadId ? 'active' : ''}
                    href={`/app?project=${projectId}&thread=${t.id}`}
                  >
                    <span>{t.title || '새 검토'}</span>
                    <small>{t.status ? statuses[t.status] : '질문 대기'}</small>
                  </a>
                ))
              ) : (
                <p className="muted">아직 검토 기록이 없습니다.</p>
              )}
            </div>
            <button className="text-button danger-action" onClick={() => setRemove('project')}>
              프로젝트 삭제
            </button>
          </aside>
          <section className="conversation">
            <div className="conversation-heading">
              <h2>{detail?.title || '새 검토'}</h2>
              {threadId && (
                <button
                  className="icon-button"
                  aria-label="이 검토 삭제"
                  disabled={!!running}
                  onClick={() => setRemove('thread')}
                >
                  <Trash2 size={15} />
                </button>
              )}
            </div>
            <div className="conversation-scroll">
              <ErrorBox
                error={error}
                retry={() => (threadId ? setReload((v) => v + 1) : project.reload())}
              />
              {loading ? (
                <Loading label="검토 기록을 불러오는 중" />
              ) : (
                <>
                  {!detail?.messages.length && !pendingQuestion && !active && (
                    <div className="conversation-start">
                      <div className="large-diode">↳</div>
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
                          <span>내 질문</span>
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
                              />
                            ) : (
                              <div key={a.id} className="markdown">
                                <ReactMarkdown>{a.content}</ReactMarkdown>
                              </div>
                            ),
                          )}
                      </div>
                    ))}
                  {pendingQuestion &&
                    !detail?.messages.some((m) => m.content === pendingQuestion) && (
                      <div className="user-message">
                        <span>내 질문</span>
                        <p>{pendingQuestion}</p>
                      </div>
                    )}
                  {active && running && !stopped && (
                    <div className="progress" role="status">
                      <Loading label={active.result.stage || '검토를 시작하는 중'} />
                      <button
                        onClick={() => {
                          controller.current?.abort();
                          setStopped(true);
                        }}
                      >
                        {' '}
                        <Square size={13} />
                        수신 중지
                      </button>
                    </div>
                  )}
                  {stopped && (
                    <div className="notice">
                      <p>실시간 수신을 멈췄습니다. 서버 검토는 계속될 수 있습니다.</p>
                      <button onClick={recover}>저장된 상태 확인</button>
                    </div>
                  )}
                  {waiting && roles.error && <ErrorBox error={roles.error} retry={roles.reload} />}
                  {waiting && active && (
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
                    <Reply run={active} onCandidate={(c, r) => setSelected({ c, r })} />
                  )}
                  {active?.result.status === 'failed' && (
                    <button onClick={newReview}>새 검토로 다시 시작</button>
                  )}
                  <div ref={end} />
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
                          disabled={busy}
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
                  <div className="attachment">
                    <Paperclip size={14} />
                    {attachment.name}
                    <button
                      type="button"
                      aria-label="첨부 제거"
                      onClick={() => setAttachment(null)}
                    >
                      <X size={14} />
                    </button>
                    <small>보내면 새 회로 버전과 새 검토를 만들고 부품을 다시 선택합니다.</small>
                  </div>
                )}
                <label className="sr-only" htmlFor="question">
                  검토 질문
                </label>
                <textarea
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  maxLength={4000}
                  disabled={!!running || !!waiting}
                  placeholder={
                    waiting
                      ? '위의 사용 조건을 입력하면 이어서 검토합니다.'
                      : `${target || '다이오드'}의 교체 후보나 궁금한 점을 입력하세요.`
                  }
                />
                <div className="composer-controls">
                  <label className="attach-button">
                    <Paperclip size={17} />
                    <span>넷리스트</span>
                    <input
                      type="file"
                      accept=".net,.txt"
                      disabled={busy}
                      onChange={(e) => setAttachment(e.target.files?.[0] ?? null)}
                    />
                  </label>
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
                  <button
                    className="primary send"
                    disabled={
                      busy ||
                      (!attachment && (!!waiting || !!running || !target || !question.trim()))
                    }
                    aria-label={attachment ? '넷리스트 보내기' : '질문 보내기'}
                  >
                    <Send size={17} />
                    <span>보내기</span>
                  </button>
                </div>
              </form>
              <Disclaimer />
            </div>
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
                <PriceLookup part={q.part_number} />
              </article>
            ))
          ) : (
            <p>아직 저장한 견적이 없습니다. 후보를 승인한 뒤 수량을 입력해 저장하세요.</p>
          )}
        </Modal>
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
            <button className="primary">이름 저장</button>
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
        </Modal>
      )}
    </div>
  );
}
