/** 대화가 먼저인 입구: 사이드바의 대화 목록·프로젝트 폴더와 "새 대화" 빈 화면. 프로젝트 하나는 회로 하나다. 출처: SPEC 2절, 4절, 8.8. */
import { useEffect, useState } from 'react';
import { ChevronRight, CornerDownLeft, Paperclip, Pencil, Plus, Trash2, X } from 'lucide-react';
import { api, ApiError } from './api';
import { projectNameFromQuestion } from './circuit';
import { isSendKey } from './display';
import { ErrorBox, Loading, Modal, navigate, RowMenu, useResource } from './ui';
import { NewProject, refreshNavigation } from './Projects';
import { openWithQuestion } from './Workbench';
import type { Demo, Project, ThreadListItem } from './types';
/** 펼친 프로젝트 번호를 이 브라우저에 남기는 키(사이드바 나무, #31). */
const EXPANDED = 'sojafit.sidebar.expanded';
/**
 * 사이드바 나무(Claude Code처럼, #31 #36): "프로젝트" 아래 프로젝트마다 펼치면 그 대화가 들여 달리고 "이 회로로 새 대화"가 있다.
 * 회로가 없는 프로젝트(has_circuit=false)의 대화와 대화도 없는 빈 프로젝트는 나무 밖 "대화"에 한 줄씩 둔다. 대화는 어느 쪽이든 한 번만 나온다.
 */
export function ConversationNav({
  projectId,
  threadId,
}: {
  projectId: string | null;
  threadId: string | null;
}) {
  const threads = useResource<ThreadListItem[]>('/threads'),
    projects = useResource<Project[]>('/projects');
  const [renaming, setRenaming] = useState<string | null>(null), // 't<대화 id>' · 'p<프로젝트 id>'
    [remove, setRemove] = useState<
      { thread: ThreadListItem; project?: never } | { project: Project; thread?: never } | null
    >(null),
    [expanded, setExpanded] = useState<number[]>(() => {
      try {
        const saved = JSON.parse(localStorage.getItem(EXPANDED) ?? '[]');
        return Array.isArray(saved) ? saved.filter(Number.isInteger) : [];
      } catch {
        return [];
      }
    }),
    [create, setCreate] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    // [왜] 작업대가 실행·첨부·삭제 뒤 refreshNavigation()으로 알린다. 새 질문이 대화 이름·순서를, 첨부가 회로 유무를 바꾼다
    const fn = () => {
      threads.reload();
      projects.reload();
    };
    window.addEventListener('projects-changed', fn);
    return () => window.removeEventListener('projects-changed', fn);
  }, []);
  useEffect(() => {
    // [왜] 작업대는 첫 질문의 분석이 끝나야 알린다. 새 대화·새 프로젝트로 옮겨 오면 분석 전에도 목록에 보이게 한 번 다시 읽는다
    if (threadId && threads.data && !threads.data.some((t) => t.id === threadId)) threads.reload();
    if (projectId && projects.data && !projects.data.some((p) => String(p.id) === projectId))
      projects.reload();
    // [왜] 사이드바(Shell)는 화면을 옮겨도 다시 만들어지지 않는다. 처음 값이 아니라 주소가 바뀔 때마다 열린 대화의 프로젝트를 펼친다
    if (projectId)
      setExpanded((x) => (x.includes(Number(projectId)) ? x : [...x, Number(projectId)]));
  }, [threadId, projectId]);
  useEffect(() => {
    try {
      localStorage.setItem(EXPANDED, JSON.stringify(expanded));
    } catch {
      // 저장소를 못 써도(사생활 보호 창 등) 이번 화면에서는 펼친 상태가 유지된다
    }
  }, [expanded]);
  async function rename(key: string, value: string, before: string) {
    setRenaming(null);
    if (!value.trim() || value.trim() === before) return;
    try {
      if (key.startsWith('t')) {
        const saved = await api<ThreadListItem>('/threads/' + key.slice(1), 'PATCH', {
          title: value,
        });
        threads.reload();
        // [왜] 열린 작업대 제목도 새로고침 없이 바뀌게 서버가 정리한 이름을 알린다(Workbench가 받는다)
        window.dispatchEvent(new CustomEvent('thread-renamed', { detail: saved }));
      } else {
        const saved = await api<Project>('/projects/' + key.slice(1), 'PATCH', { name: value });
        refreshNavigation();
        window.dispatchEvent(new CustomEvent('project-renamed', { detail: saved }));
      }
    } catch (e) {
      setError(e as Error);
    }
  }
  async function confirmRemove() {
    if (!remove) return;
    setBusy(true);
    setError(null);
    try {
      if (remove.thread) {
        await api('/threads/' + remove.thread.id, 'DELETE');
        // 보고 있던 대화를 지우면 같은 회로의 새 대화 화면으로 간다
        if (remove.thread.id === threadId) navigate('/app?project=' + remove.thread.project_id);
      } else {
        await api('/projects/' + remove.project.id, 'DELETE');
        if (String(remove.project.id) === projectId) navigate('/app');
      }
      setRemove(null);
      refreshNavigation();
    } catch (e) {
      setError(e as Error); // 분석 중이면 409. 창을 닫지 않고 서버 문구를 보인다
    } finally {
      setBusy(false);
    }
  }
  const menu = (key: string, label: string, onDelete: () => void) => (
    <RowMenu
      label={label}
      items={[
        { label: '이름 변경', icon: <Pencil size={14} />, onSelect: () => setRenaming(key) },
        {
          label: '삭제',
          icon: <Trash2 size={14} />,
          danger: true,
          onSelect: () => {
            setError(null);
            onDelete();
          },
        },
      ]}
    />
  );
  // 그 자리에서 이름 고치기: Enter·다른 곳 클릭이면 저장, Esc면 그대로
  const renameForm = (key: string, label: string, value: string) => (
    <form
      key={key}
      className="thread-row"
      onSubmit={(e) => {
        e.preventDefault();
        // [왜] 저장은 blur 한 곳에서만 한다(Enter와 blur가 두 번 저장하지 않게)
        (e.currentTarget.elements.namedItem('title') as HTMLInputElement).blur();
      }}
    >
      <input
        name="title"
        aria-label={label}
        defaultValue={value}
        maxLength={200}
        autoFocus
        onBlur={(e) => void rename(key, e.currentTarget.value, value)}
        onKeyDown={(e) => {
          if (e.key !== 'Escape') return;
          e.currentTarget.value = value; // 원래 이름으로 돌려 blur 저장이 아무것도 하지 않게 한다
          e.currentTarget.blur();
        }}
      />
    </form>
  );
  const row = (t: ThreadListItem) =>
    renaming === 't' + t.id ? (
      renameForm('t' + t.id, '대화 이름', t.title)
    ) : (
      <div key={t.id} className={'thread-row' + (t.id === threadId ? ' selected' : '')}>
        <a href={`/app?project=${t.project_id}&thread=${t.id}`} title={t.title}>
          {t.title}
        </a>
        {menu('t' + t.id, '대화 메뉴', () => setRemove({ thread: t }))}
      </div>
    );
  const all = threads.data ?? [],
    tree = projects.data?.filter((p) => p.has_circuit) ?? [],
    loose = new Set(projects.data?.filter((p) => !p.has_circuit).map((p) => p.id)),
    // [왜] 대화도 회로도 없는 프로젝트("나중에 첨부"로 만든 것)는 나무에 없으므로 "대화"에 한 줄로 남겨 열 수 있게 한다
    empty = projects.data?.filter(
      (p) => loose.has(p.id) && !all.some((t) => t.project_id === p.id),
    ),
    looseThreads = all.filter((t) => loose.has(t.project_id));
  // 프로젝트 줄: 나무에서는 펼치기 버튼(toggle), "대화"의 빈 프로젝트는 그 작업대 링크. 둘 다 ⋯ 메뉴가 옆에 있다
  const projectRow = (p: Project, toggle?: React.ReactNode) =>
    renaming === 'p' + p.id ? (
      renameForm('p' + p.id, '프로젝트 이름', p.name)
    ) : (
      <div
        key={p.id}
        className={
          'thread-row' + (!toggle && String(p.id) === projectId && !threadId ? ' selected' : '')
        }
      >
        {toggle ?? (
          <a href={'/app?project=' + p.id} title={p.name}>
            {p.name}
          </a>
        )}
        {menu('p' + p.id, p.name + ' 메뉴', () => setRemove({ project: p }))}
      </div>
    );
  return (
    <div className="sidebar-projects">
      {threads.loading || projects.loading ? (
        <Loading />
      ) : threads.error || projects.error ? (
        <ErrorBox
          error={threads.error ?? projects.error}
          retry={() => {
            threads.reload();
            projects.reload();
          }}
        />
      ) : (
        <>
          {!!(looseThreads.length || empty?.length) && (
            <>
              <p>대화</p>
              {looseThreads.map(row)}
              {empty?.map((p) => projectRow(p))}
            </>
          )}
          <div className="nav-section">
            <p>프로젝트</p>
            <button
              className="icon-button"
              aria-label="새 프로젝트"
              title="새 프로젝트"
              onClick={() => setCreate(true)}
            >
              <Plus size={15} />
            </button>
          </div>
          {tree.length ? (
            tree.map((p) => {
              const open = expanded.includes(p.id);
              return (
                <div key={p.id}>
                  {projectRow(
                    p,
                    <button
                      className="folder-toggle"
                      aria-expanded={open}
                      title={p.name}
                      onClick={() =>
                        setExpanded((x) => (open ? x.filter((id) => id !== p.id) : [...x, p.id]))
                      }
                    >
                      <ChevronRight size={14} />
                      <span>{p.name}</span>
                    </button>,
                  )}
                  {open && (
                    <div className="folder-items">
                      {all.filter((t) => t.project_id === p.id).map(row)}
                      <a
                        className={String(p.id) === projectId && !threadId ? 'selected' : ''}
                        href={'/app?project=' + p.id}
                      >
                        <Plus size={13} />이 회로로 새 대화
                      </a>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <p className="muted">아직 프로젝트가 없습니다.</p>
          )}
        </>
      )}
      {!remove && <ErrorBox error={error} />}
      {remove && (
        <Modal
          title={remove.thread ? '대화를 삭제할까요?' : '프로젝트를 삭제할까요?'}
          close={() => !busy && setRemove(null)}
        >
          <p>
            {remove.thread
              ? `“${remove.thread.title}” 대화와 분석 기록이 삭제됩니다.`
              : `“${remove.project.name}” 프로젝트의 회로, 대화, 승인, 견적이 함께 삭제됩니다.`}{' '}
            복구할 수 없습니다.
          </p>
          <ErrorBox error={error} />
          <div className="dialog-actions">
            <button disabled={busy} onClick={() => setRemove(null)}>
              취소
            </button>
            <button className="primary" disabled={busy} onClick={confirmRemove}>
              {busy ? '삭제하는 중…' : '삭제'}
            </button>
          </div>
        </Modal>
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
/** "새 대화" 화면: 질문 입력창 하나(#30). 넷리스트는 입력창 안에서 첨부한다(클립 · 끌어 놓기). 회로가 필요한 질문이면 에이전트가 대화 안에서 넷리스트나 기존 회로를 고르게 한다(SPEC 2절, 8.9). */
export function NewConversation() {
  const [question, setQuestion] = useState(''),
    [attachment, setAttachment] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null);
  async function start(allowDuplicate = false) {
    setBusy(true);
    setError(null);
    try {
      let project: Project;
      if (attachment) {
        if (attachment.size > 5 * 1024 * 1024) throw new Error('넷리스트는 5 MiB 이하여야 합니다.');
        const body = new FormData();
        // [왜] 이름을 먼저 묻지 않는다. 파일 이름(확장자 뺌)으로 만들고 프로젝트 목록에서 바꿀 수 있다
        body.set(
          'name',
          attachment.name
            .replace(/\.[^.]*$/, '')
            .trim()
            .slice(0, 200) || '새 회로',
        );
        body.set('file', attachment);
        project = await api(
          '/projects/upload' + (allowDuplicate ? '?allow_duplicate=true' : ''),
          'POST',
          body,
        );
      } else
        // [왜] 회로 없는 대화도 프로젝트 하나에 담는다(대화는 프로젝트에 속한다). 질문에서 지은 이름은 겹쳐도 되니 409를 묻지 않는다
        project = await api('/projects?allow_duplicate=true', 'POST', {
          name: projectNameFromQuestion(question),
        });
      refreshNavigation();
      await openWithQuestion(project.id, question);
    } catch (e) {
      setError(e as Error);
      setBusy(false);
    }
  }
  const disabled = busy || (!question.trim() && !attachment);
  // 409: 같은 이름이나 같은 회로의 프로젝트가 있다(넷리스트 첨부). 그 회로로 이어 갈지, 그래도 새로 만들지 고르게 한다
  const duplicates: { id: number; name: string }[] =
    error instanceof ApiError && error.status === 409 ? (error.details?.duplicates ?? []) : [];
  return (
    <div className="page-content new-chat">
      <h1>새 대화</h1>
      <p className="page-intro">
        궁금한 부품이나 바꿀 부품을 물어보세요. 회로 검토가 필요하면 KiCad 넷리스트(.net)를
        첨부하세요.
      </p>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          if (!disabled) void start();
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const file = e.dataTransfer.files[0];
          if (file) setAttachment(file);
        }}
      >
        {attachment && (
          <div className="attachment">
            <Paperclip size={14} />
            {attachment.name}
            <button
              type="button"
              aria-label="첨부 제거"
              title="첨부 제거"
              onClick={() => setAttachment(null)}
            >
              <X size={14} />
            </button>
            <small>보내면 파일 이름으로 프로젝트를 만들고 이 회로로 대화를 시작합니다.</small>
          </div>
        )}
        <label className="sr-only" htmlFor="new-question">
          새 대화 질문
        </label>
        <textarea
          id="new-question"
          value={question}
          autoFocus
          maxLength={4000}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (!isSendKey(e.nativeEvent)) return; // Shift+Enter · 한글 조합 중 Enter는 그대로(#38)
            e.preventDefault();
            if (!disabled) void start();
          }}
          placeholder="예: 1N4148 역전압은 몇 V야? · D1을 1N5819로 바꿔도 될까?"
        />
        <div className="composer-controls">
          <label className="attach-button">
            <Paperclip size={17} />
            <span>넷리스트</span>
            <input
              type="file"
              accept=".net"
              onChange={(e) => {
                setAttachment(e.target.files?.[0] ?? null);
                e.target.value = ''; // 같은 파일을 다시 고를 수 있게
              }}
            />
          </label>
          <a className="composer-hint" href="/assets/samples/attiny85-time-switch.net" download>
            샘플 넷리스트 받기
          </a>
          <button
            className="primary send"
            disabled={disabled}
            aria-label="질문 보내기"
            title="질문 보내기"
          >
            <CornerDownLeft size={17} />
          </button>
        </div>
      </form>
      {busy && <Loading label="대화를 준비하는 중" />}
      <ErrorBox error={duplicates.length ? null : error} />
      {duplicates.length > 0 && (
        <div className="notice" role="alert">
          <p>같은 이름이나 같은 회로의 프로젝트가 있습니다.</p>
          <div className="duplicate-actions">
            {duplicates.map((d) => (
              <button
                key={d.id}
                type="button"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  openWithQuestion(d.id, question).catch((e) => {
                    setError(e as Error);
                    setBusy(false);
                  });
                }}
              >
                {d.name} 프로젝트로 계속
              </button>
            ))}
            <button type="button" disabled={busy} onClick={() => start(true)}>
              새 프로젝트로 만들기
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
