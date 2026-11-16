/** 새 프로젝트 창(사이드바 "프로젝트 +")과 사이드바 목록 새로고침 알림. 프로젝트 목록 페이지는 사이드바 나무로 옮겼다(#34). 출처: SPEC 2·4절, 8.8. */
import { useState } from 'react';
import { ArrowRight, FileUp } from 'lucide-react';
import { api, ApiError } from './api';
import { ErrorBox, Loading, Modal, useResource } from './ui';
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
        <div className="dialog-actions">
          <button type="button" onClick={close}>
            취소
          </button>
          <button className="primary" disabled={busy || (mode === 'demo' && !demo)}>
            {busy ? '만드는 중…' : '프로젝트 만들기'}
            <ArrowRight size={16} />
          </button>
        </div>
      </form>
    </Modal>
  );
}
