/** 대화가 먼저인 입구: 사이드바의 대화 목록·프로젝트 폴더와 "새 대화" 빈 화면. 프로젝트 하나는 회로 하나다. 출처: SPEC 2절, 4절, 8.8. */
import { useEffect, useState } from 'react';
import { ChevronRight, CornerDownLeft, Paperclip, Pencil, Plus, Trash2, X } from 'lucide-react';
import { api, ApiError } from './api';
import { projectNameFromQuestion } from './circuit';
import { ErrorBox, Loading, Modal, navigate, RowMenu, useResource } from './ui';
import { refreshNavigation } from './Projects';
import { openWithQuestion } from './Workbench';
import type { Project, ThreadListItem } from './types';
/** 사이드바 "대화"(모든 프로젝트, 최근 활동 순)와 "프로젝트"(펼치면 그 대화). 대화 목록은 한 번 받아 프로젝트별로 나눈다. */
export function ConversationNav({
  projectId,
  threadId,
}: {
  projectId: string | null;
  threadId: string | null;
}) {
  const threads = useResource<ThreadListItem[]>('/threads'),
    projects = useResource<Project[]>('/projects');
  const [renaming, setRenaming] = useState<string | null>(null),
    [remove, setRemove] = useState<ThreadListItem | null>(null),
    [expanded, setExpanded] = useState<number[]>(projectId ? [Number(projectId)] : []),
    [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    // [왜] 작업대가 실행·첨부·삭제 뒤 refreshNavigation()으로 알린다. 새 질문이 대화 이름·순서를 바꾼다
    const fn = () => {
      threads.reload();
      projects.reload();
    };
    window.addEventListener('projects-changed', fn);
    return () => window.removeEventListener('projects-changed', fn);
  }, []);
  useEffect(() => {
    // [왜] 작업대는 첫 질문의 분석이 끝나야 알린다. 새 대화로 옮겨 오면 분석 전에도 목록에 보이게 한 번 다시 읽는다
    if (threadId && threads.data && !threads.data.some((t) => t.id === threadId)) threads.reload();
  }, [threadId]);
  async function rename(t: ThreadListItem, title: string) {
    setRenaming(null);
    if (!title.trim() || title.trim() === t.title) return;
    try {
      const saved = await api<ThreadListItem>('/threads/' + t.id, 'PATCH', { title });
      threads.reload();
      // [왜] 열린 작업대 제목도 새로고침 없이 바뀌게 서버가 정리한 이름을 알린다(Workbench가 받는다)
      window.dispatchEvent(new CustomEvent('thread-renamed', { detail: saved }));
    } catch (e) {
      setError(e as Error);
    }
  }
  const row = (t: ThreadListItem) =>
    renaming === t.id ? (
      <form
        key={t.id}
        className="thread-row"
        onSubmit={(e) => {
          e.preventDefault();
          // [왜] 저장은 blur 한 곳에서만 한다(Enter와 blur가 두 번 저장하지 않게)
          (e.currentTarget.elements.namedItem('title') as HTMLInputElement).blur();
        }}
      >
        <input
          name="title"
          aria-label="대화 이름"
          defaultValue={t.title}
          maxLength={200}
          autoFocus
          onBlur={(e) => void rename(t, e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key !== 'Escape') return;
            e.currentTarget.value = t.title; // 원래 이름으로 돌려 blur 저장이 아무것도 하지 않게 한다
            e.currentTarget.blur();
          }}
        />
      </form>
    ) : (
      <div key={t.id} className={'thread-row' + (t.id === threadId ? ' selected' : '')}>
        <a href={`/app?project=${t.project_id}&thread=${t.id}`} title={t.project_name}>
          {t.title}
        </a>
        <RowMenu
          label="대화 메뉴"
          items={[
            { label: '이름 변경', icon: <Pencil size={14} />, onSelect: () => setRenaming(t.id) },
            {
              label: '삭제',
              icon: <Trash2 size={14} />,
              danger: true,
              onSelect: () => {
                setError(null);
                setRemove(t);
              },
            },
          ]}
        />
      </div>
    );
  return (
    <div className="sidebar-projects">
      <p>대화</p>
      {threads.loading ? (
        <Loading />
      ) : threads.error ? (
        <ErrorBox error={threads.error} retry={threads.reload} />
      ) : threads.data?.length ? (
        threads.data.map(row)
      ) : (
        <p className="muted">아직 대화가 없습니다.</p>
      )}
      {!remove && <ErrorBox error={error} />}
      <p>프로젝트</p>
      {projects.loading ? (
        <Loading />
      ) : projects.error ? (
        <ErrorBox error={projects.error} retry={projects.reload} />
      ) : projects.data?.length ? (
        projects.data.map((p) => {
          const open = expanded.includes(p.id);
          return (
            <div key={p.id}>
              <button
                className="folder-toggle"
                aria-expanded={open}
                onClick={() =>
                  setExpanded((x) => (open ? x.filter((id) => id !== p.id) : [...x, p.id]))
                }
              >
                <ChevronRight size={14} />
                <span>{p.name}</span>
              </button>
              {open && (
                <div className="folder-items">
                  {threads.data
                    ?.filter((t) => t.project_id === p.id)
                    .map((t) => (
                      <a
                        key={t.id}
                        className={t.id === threadId ? 'selected' : ''}
                        href={`/app?project=${p.id}&thread=${t.id}`}
                      >
                        {t.title}
                      </a>
                    ))}
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
      {remove && (
        <Modal title="대화를 삭제할까요?" close={() => setRemove(null)}>
          <p>“{remove.title}” 대화와 분석 기록이 삭제됩니다. 복구할 수 없습니다.</p>
          <ErrorBox error={error} />
          <button
            className="primary"
            onClick={async () => {
              try {
                await api('/threads/' + remove.id, 'DELETE');
                setRemove(null);
                // 보고 있던 대화를 지우면 같은 회로의 새 대화 화면으로 간다
                if (remove.id === threadId) navigate('/app?project=' + remove.project_id);
                refreshNavigation();
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
