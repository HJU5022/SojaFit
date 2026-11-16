/** 프로젝트 목록(이름 변경·삭제·일괄 삭제)과 새 프로젝트 창. 서버가 만든 프로젝트·데모 회로를 그대로 쓴다. 출처: SPEC 2·4절, 8.8. */
import { useState } from 'react';
import { ArrowRight, ChevronRight, FileUp, Pencil, Plus, Trash2 } from 'lucide-react';
import { api, ApiError } from './api';
import { Empty, ErrorBox, Loading, Modal, navigate, useResource } from './ui';
import type { Demo, Project } from './types';
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
  // [왜] 운영(DEMO_MODE=0)은 /demo-circuits가 404다. 그때는 데모 탭을 숨기고 업로드로 시작한다
  const noDemo = demos.error instanceof ApiError && demos.error.status === 404;
  const [chosen, setMode] = useState<'demo' | 'upload' | 'empty'>('demo'),
    [name, setName] = useState(''),
    [demo, setDemo] = useState(''),
    [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | null>(null),
    [duplicate, setDuplicate] = useState(false);
  const mode = noDemo && chosen === 'demo' ? 'upload' : chosen;
  return (
    <Modal title="새 프로젝트" close={close}>
      <p>
        {noDemo
          ? '넷리스트를 올려 시작하세요.'
          : '넷리스트를 올리거나 공개 데모 회로로 시작하세요.'}
      </p>
      <div className="segmented">
        {!noDemo && (
          <button onClick={() => setMode('demo')} aria-pressed={mode === 'demo'}>
            데모 회로
          </button>
        )}
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
            <ErrorBox error={demos.error} retry={demos.reload} />
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
        {mode === 'upload' && (
          <small>
            넷리스트가 없다면{' '}
            <a href="/assets/samples/attiny85-time-switch.net" download>
              샘플 넷리스트 받기
            </a>{' '}
            (ATtiny85 Time Switch · UCSIG · MIT)
          </small>
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
/** 프로젝트 목록(/projects): 줄마다 이름 변경·삭제 버튼, 여러 개를 골라 한 번에 삭제. */
export function ProjectList() {
  const projects = useResource<Project[]>('/projects'),
    [create, setCreate] = useState(false),
    [selected, setSelected] = useState<number[]>([]),
    [renaming, setRenaming] = useState<number | null>(null),
    [remove, setRemove] = useState<Project[] | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<Error | string | null>(null);
  const list = projects.data ?? [];
  async function rename(p: Project, name: string) {
    setRenaming(null);
    if (!name.trim() || name.trim() === p.name) return;
    try {
      await api('/projects/' + p.id, 'PATCH', { name });
      projects.reload();
      refreshNavigation();
    } catch (e) {
      setError(e as Error);
    }
  }
  async function deleteAll(items: Project[]) {
    setBusy(true);
    setError(null);
    const failed: { project: Project; message: string }[] = [];
    // [왜] 일괄 삭제 API는 없다. 기존 DELETE를 하나씩 부르고, 실패(분석 중이면 409)한 것만 모아 보이며 선택에 남긴다
    for (const p of items)
      try {
        await api('/projects/' + p.id, 'DELETE');
      } catch (e) {
        failed.push({ project: p, message: (e as Error).message });
      }
    setSelected(failed.map((f) => f.project.id));
    if (failed.length)
      setError(
        `${items.length}개 중 ${failed.length}개를 삭제하지 못했습니다. ` +
          failed.map((f) => `${f.project.name}: ${f.message}`).join(' · '),
      );
    setRemove(null);
    setBusy(false);
    projects.reload();
    refreshNavigation();
  }
  return (
    <div className="page-content">
      <div className="page-heading">
        <h1>프로젝트</h1>
        <button className="primary" onClick={() => setCreate(true)}>
          <Plus size={17} />새 프로젝트
        </button>
      </div>
      {projects.loading ? (
        <Loading />
      ) : projects.error ? (
        <ErrorBox error={projects.error} retry={projects.reload} />
      ) : list.length ? (
        <div className="project-list">
          <div className="list-toolbar">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={selected.length === list.length}
                onChange={(e) => setSelected(e.target.checked ? list.map((p) => p.id) : [])}
              />
              전체 선택
            </label>
            {selected.length > 0 && (
              <>
                <span>{selected.length}개 선택</span>
                <button
                  className="icon-button"
                  aria-label="선택 삭제"
                  title="선택 삭제"
                  onClick={() => {
                    setError(null);
                    setRemove(list.filter((p) => selected.includes(p.id)));
                  }}
                >
                  <Trash2 size={17} />
                </button>
              </>
            )}
          </div>
          <ErrorBox error={error} />
          {list.map((p) => (
            <div key={p.id} className="project-row">
              <input
                type="checkbox"
                aria-label={p.name + ' 선택'}
                checked={selected.includes(p.id)}
                onChange={(e) =>
                  setSelected((x) =>
                    e.target.checked ? [...x, p.id] : x.filter((id) => id !== p.id),
                  )
                }
              />
              {renaming === p.id ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    // [왜] 저장은 blur 한 곳에서만 한다(Enter와 blur가 두 번 저장하지 않게)
                    (e.currentTarget.elements.namedItem('name') as HTMLInputElement).blur();
                  }}
                >
                  <input
                    name="name"
                    aria-label="프로젝트 이름"
                    defaultValue={p.name}
                    maxLength={200}
                    autoFocus
                    onBlur={(e) => void rename(p, e.currentTarget.value)}
                    onKeyDown={(e) => {
                      if (e.key !== 'Escape') return;
                      e.currentTarget.value = p.name; // 원래 이름으로 돌려 blur 저장이 아무것도 하지 않게 한다
                      e.currentTarget.blur();
                    }}
                  />
                </form>
              ) : (
                <a href={'/app?project=' + p.id} className="project-open">
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
              )}
              <button
                className="icon-button"
                aria-label={p.name + ' 이름 변경'}
                title={p.name + ' 이름 변경'}
                onClick={() => setRenaming(p.id)}
              >
                <Pencil size={17} />
              </button>
              <button
                className="icon-button"
                aria-label={p.name + ' 삭제'}
                title={p.name + ' 삭제'}
                onClick={() => {
                  setError(null);
                  setRemove([p]);
                }}
              >
                <Trash2 size={17} />
              </button>
            </div>
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
      {remove && (
        <Modal
          title={
            remove.length > 1
              ? `프로젝트 ${remove.length}개를 삭제할까요?`
              : '프로젝트를 삭제할까요?'
          }
          close={() => !busy && setRemove(null)}
        >
          <ul>
            {remove.map((p) => (
              <li key={p.id}>{p.name}</li>
            ))}
          </ul>
          <p>회로, 대화, 승인, 견적이 함께 삭제됩니다. 복구할 수 없습니다.</p>
          <button className="primary" disabled={busy} onClick={() => deleteAll(remove)}>
            {busy ? '삭제하는 중…' : '삭제'}
          </button>
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
