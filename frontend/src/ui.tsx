/** 공통 상태·접근성·회로 표시. 서버 값을 시각화하며 판정은 계산하지 않는다. 출처: SPEC 3·4절. */
import { Fragment, useEffect, useRef, useState, type DragEvent, type ReactNode } from 'react';
import {
  AlertCircle,
  ArrowUpRight,
  CircuitBoard,
  Download,
  Ellipsis,
  FileText,
  LoaderCircle,
  Paperclip,
  Plus,
  RotateCw,
  X,
} from 'lucide-react';
import { api, verdicts } from './api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { explainAnswer, markdownUrl, safeLink } from './display';
import { partsOf, pinsOf } from './circuit';
import type { Citation, Project, Verdict } from './types';
export function navigate(url: string, replace = false) {
  history[replace ? 'replaceState' : 'pushState']({}, '', url);
  window.dispatchEvent(new PopStateEvent('popstate'));
}
/** 새 탭·창으로 열려는 클릭(가운데 단추·Ctrl·Cmd·Shift·Alt)이나 이미 처리된 클릭이 아닌 보통 왼쪽 클릭. */
export const plainClick = (e: MouseEvent | React.MouseEvent) =>
  !e.defaultPrevented && e.button === 0 && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey);
/**
 * 문서 전체 클릭 위임(App이 한 번 단다): 같은 출처 링크를 페이지를 새로 받지 않고 화면 안에서 옮긴다(#19).
 * [왜] 사이드바 등 내부 링크가 보통 `<a href>`라 누를 때마다 전체 새로고침·흰 화면이 났다. href는 그대로 둬 새 탭 열기가 된다.
 * 새 탭·다운로드·다른 출처·서버가 직접 주는 경로(/api·/assets·/circuit-schematics)·같은 화면의 #앵커는 브라우저에 맡긴다.
 */
export function followLink(e: MouseEvent) {
  const a = (e.target as Element).closest?.<HTMLAnchorElement>('a[href]');
  if (!a || !plainClick(e) || a.target || a.hasAttribute('download')) return;
  const url = new URL(a.href),
    here = location.pathname + location.search,
    next = url.pathname + url.search;
  if (url.origin !== location.origin || /^\/(api|assets|circuit-schematics)\//.test(url.pathname))
    return;
  if (next === here && url.hash) return;
  e.preventDefault();
  // [왜] 브라우저처럼 같은 주소를 다시 누르면 방문 기록을 늘리지 않고, 새 화면은 맨 위에서 시작한다
  navigate(next + url.hash, next === here);
  scrollTo(0, 0);
}
export function useLocation() {
  const [url, set] = useState(location.pathname + location.search);
  useEffect(() => {
    const fn = () => set(location.pathname + location.search);
    window.addEventListener('popstate', fn);
    return () => window.removeEventListener('popstate', fn);
  }, []);
  return url;
}
export function useResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null),
    [loading, setLoading] = useState(!!path),
    [error, setError] = useState<Error | null>(null),
    [version, setVersion] = useState(0);
  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    setLoading(!!path);
    if (path)
      api<T>(path)
        .then((v) => {
          if (live) setData(v);
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
  }, [path, version]);
  return { data, loading, error, reload: () => setVersion((v) => v + 1), setData };
}
export function Brand() {
  return (
    <a className="brand" href="/" aria-label="SojaFit 홈">
      <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
        <path
          d="M2 14h6m12 0h6M8 6v16l12-8L8 6Zm12 0v16"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinejoin="round"
        />
      </svg>
      <span>SojaFit</span>
    </a>
  );
}
export function Loading({ label = '불러오는 중' }: { label?: string }) {
  return (
    <div className="state" role="status">
      <LoaderCircle size={19} className="spin" />
      {label}
    </div>
  );
}
export function ErrorBox({ error, retry }: { error: Error | string | null; retry?: () => void }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <AlertCircle size={18} />
      <div>
        {typeof error === 'string' ? error : error.message}
        {retry && (
          // [주의] 폼 안에 놓이는 일이 있어 type="button"이 없으면 제출 버튼이 된다
          <button
            type="button"
            className="icon-button"
            aria-label="다시 시도"
            title="다시 시도"
            onClick={retry}
          >
            <RotateCw size={16} />
          </button>
        )}
      </div>
    </div>
  );
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <CircuitBoard size={30} />
      <h2>{title}</h2>
      {children}
    </div>
  );
}
export function Badge({ verdict }: { verdict: Verdict }) {
  return <span className={'badge ' + verdict}>{verdicts[verdict] ?? verdict}</span>;
}
export function Disclaimer() {
  return <p className="disclaimer">같은 동작은 보장하지 않습니다.</p>;
}
export function Modal({
  title,
  close,
  children,
  wide = false,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => {
      ref.current?.close();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={wide ? 'dialog side-dialog' : 'dialog'}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      {wide && (
        <ResizeHandle name="drawer-w" label="창 너비 조절" min={440} max={1100} edge="left" />
      )}
      <div className="dialog-head">
        <h2>{title}</h2>
        <button aria-label="닫기" title="닫기" className="icon-button" onClick={close}>
          <X size={20} />
        </button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
}
/**
 * 옆 패널의 세로 경계선(#35): 끌거나 포커스 뒤 ←/→로 너비를 바꾼다. 너비는 문서 루트의 `--{name}` CSS 변수와 localStorage에 둔다.
 * edge="right"는 패널 오른쪽 경계(사이드바), "left"는 왼쪽 경계(오른쪽 패널·창)라 끄는 방향이 반대다. 760px 이하에서는 CSS가 숨긴다.
 */
export function ResizeHandle({
  name,
  label,
  min,
  max,
  edge,
}: {
  name: string;
  label: string;
  min: number;
  max: number;
  edge: 'left' | 'right';
}) {
  const ref = useRef<HTMLDivElement>(null),
    drag = useRef<{ x: number; w: number } | null>(null),
    key = 'sojafit.' + name;
  // [왜] 사용자가 바꾸기 전에는 null로 두어 CSS 기본 너비(화면 폭마다 다름)를 그대로 쓴다
  const [width, setWidth] = useState<number | null>(() => {
      try {
        const v = Number(localStorage.getItem(key));
        return v >= min && v <= max ? v : null;
      } catch {
        return null;
      }
    }),
    [seen, setSeen] = useState(min);
  useEffect(() => {
    if (width === null) return;
    document.documentElement.style.setProperty('--' + name, width + 'px');
    try {
      localStorage.setItem(key, String(width));
    } catch {
      // 저장소를 못 써도(사생활 보호 창 등) 이번 화면에는 적용된다
    }
  }, [width]);
  const current = () => width ?? ref.current?.parentElement?.offsetWidth ?? min,
    resize = (w: number) => setWidth(Math.round(Math.min(max, Math.max(min, w)))),
    sign = edge === 'right' ? 1 : -1;
  return (
    <div
      ref={ref}
      className={'resize-handle ' + edge}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={width ?? seen}
      tabIndex={0}
      onFocus={() => setSeen(current())}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault(); // 끄는 동안 글자가 선택되지 않게
        // [왜] 포인터를 잡아 두어야 창 바깥(배경)에서 놓아도 그 클릭이 창을 닫지 않는다(Modal의 배경 클릭 닫기)
        e.currentTarget.setPointerCapture(e.pointerId);
        drag.current = { x: e.clientX, w: current() };
      }}
      onPointerMove={(e) => {
        if (drag.current) resize(drag.current.w + sign * (e.clientX - drag.current.x));
      }}
      onPointerUp={() => (drag.current = null)}
      onPointerCancel={() => (drag.current = null)}
      onKeyDown={(e) => {
        const step = e.key === 'ArrowRight' ? 16 : e.key === 'ArrowLeft' ? -16 : 0;
        if (!step) return;
        e.preventDefault();
        resize(current() + sign * step);
      }}
    />
  );
}
/** ⋯ 버튼 아래 작은 메뉴(사이드바 대화·프로젝트 줄 · 작업대 상단 · 입력창 + 단추 · 사이드바 계정 줄이 같이 쓴다). 바깥을 누르거나 Esc면 닫고, danger 항목은 빨간 글자, strong은 굵게, sep은 항목 위에 구분선. up이면 단추 위로 편다. */
export function RowMenu({
  label,
  items,
  icon = <Ellipsis size={16} />,
  up = false,
  className = '',
}: {
  label: string;
  items: {
    label: string;
    icon?: ReactNode;
    danger?: boolean;
    strong?: boolean;
    sep?: boolean;
    onSelect: () => void;
  }[];
  icon?: ReactNode;
  up?: boolean;
  className?: string;
}) {
  const [open, setOpen] = useState(false),
    ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== 'Escape') return;
        ref.current?.querySelector('button')?.focus(); // [왜] 사라질 메뉴 항목에 있던 초점을 ⋯ 버튼으로 돌린다
      } else if (ref.current?.contains(e.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('pointerdown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);
  return (
    <div className={['row-menu', up && 'up', className].filter(Boolean).join(' ')} ref={ref}>
      {/* [왜] type="button": 입력창 form 안에서 눌러도 보내기(submit)가 되지 않게 한다 */}
      <button
        type="button"
        className="icon-button"
        aria-label={label}
        title={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {icon}
      </button>
      {open && (
        <div role="menu" aria-label={label}>
          {items.map((item) => (
            <Fragment key={item.label}>
              {item.sep && <div role="separator" />}
              <button
                type="button"
                role="menuitem"
                className={item.danger ? 'danger' : undefined}
                onClick={() => {
                  setOpen(false);
                  item.onSelect();
                }}
              >
                {item.icon}
                {item.strong ? <strong>{item.label}</strong> : item.label}
              </button>
            </Fragment>
          ))}
        </div>
      )}
    </div>
  );
}
/** 입력창 안 첨부 카드(#49, Claude 입력창처럼 글 줄 위 왼쪽): 파일 아이콘 · 말줄임한 이름 · 종류만 보이고 미리보기는 없다. ×는 올리거나 초점이 갈 때 보인다. 새 대화 · 작업대가 같이 쓴다. */
export function AttachmentCard({ file, onRemove }: { file: File; onRemove: () => void }) {
  return (
    <div className="attachment">
      <FileText size={22} aria-hidden />
      <div>
        <strong title={file.name}>{file.name}</strong>
        <small>KiCad 넷리스트 · {file.name.match(/\.[^.]*$/)?.[0].toLowerCase()}</small>
      </div>
      <button type="button" aria-label="첨부 제거" title="첨부 제거" onClick={onRemove}>
        <X size={12} />
      </button>
    </div>
  );
}
/** 입력창 넷리스트 첨부(#40): + 단추가 위로 여는 메뉴(파일 고르기 · 샘플 넷리스트 받기)와 영역 어디든 끌어 놓기. 새 대화 · 작업대가 같이 쓴다.
 *  accept 밖의 파일은 붙이지 않고 짧게 알린다(서버도 다시 검사한다. 새 대화 업로드는 .net만 받는다). */
export function useNetlistAttach(accept: string, onFile: (file: File) => void) {
  const input = useRef<HTMLInputElement>(null),
    [over, setOver] = useState(false),
    [rejected, setRejected] = useState(false);
  function pick(file: File | undefined) {
    if (!file) return;
    const ok = accept.split(',').some((ext) => file.name.toLowerCase().endsWith(ext));
    setRejected(!ok);
    if (ok) onFile(file);
  }
  const hasFiles = (e: DragEvent) => e.dataTransfer.types.includes('Files');
  return {
    input,
    dropZone: {
      onDragEnter: (e: DragEvent) => {
        if (hasFiles(e)) setOver(true);
      },
      onDragOver: (e: DragEvent) => {
        if (hasFiles(e)) e.preventDefault();
      },
      onDrop: (e: DragEvent) => {
        if (!hasFiles(e)) return;
        e.preventDefault();
        setOver(false);
        pick(e.dataTransfer.files[0]);
      },
    },
    // [왜] 덮개가 영역 전체를 덮고 끌기 이벤트를 혼자 받는다. 자식 요소 사이를 지날 때 깜빡이지 않고, 덮개를 벗어날 때만 닫힌다
    overlay: over && (
      <div className="drop-overlay" onDragLeave={() => setOver(false)}>
        여기에 놓으면 넷리스트를 첨부해요
      </div>
    ),
    button: (
      <div className="attach-button">
        {/* 파일 입력은 메뉴 밖에 두어 메뉴가 닫혀도 남는다(작업대 넷리스트 요청 카드가 ref로 연다) */}
        <input
          ref={input}
          type="file"
          accept={accept}
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            pick(e.target.files?.[0]);
            e.target.value = ''; // 같은 파일을 다시 고를 수 있게
          }}
        />
        <RowMenu
          label="첨부 메뉴"
          icon={<Plus size={18} />}
          up
          items={[
            {
              label: '넷리스트 첨부 (.net)',
              icon: <Paperclip size={14} />,
              onSelect: () => input.current?.click(),
            },
            {
              label: '샘플 넷리스트 받기',
              icon: <Download size={14} />,
              onSelect: () => {
                // [왜] 문서에 붙인 링크를 눌러 내려받는다. 메뉴가 닫히며 지워질 링크에 기대지 않는다
                const a = Object.assign(document.createElement('a'), {
                  href: '/assets/samples/attiny85-time-switch.net',
                  download: '',
                });
                document.body.append(a);
                a.click();
                a.remove();
              },
            },
          ]}
        />
        {rejected && (
          <small className="composer-hint" role="alert">
            {accept.replaceAll(',', ' · ')} 파일만 첨부할 수 있어요.
          </small>
        )}
      </div>
    ),
  };
}
export function Source({ cite }: { cite: Citation }) {
  return (
    <div className="citation">
      <strong>{cite.document || '문서명 미제공'}</strong>
      <span>
        {[cite.page != null ? `${cite.page}쪽` : null, cite.table, cite.row, cite.section]
          .filter(Boolean)
          .join(' · ') || '상세 위치 미제공'}
      </span>
      {safeLink(cite.source_url) ? (
        <a target="_blank" rel="noreferrer" href={safeLink(cite.source_url)}>
          원문 보기 <ArrowUpRight size={14} />
        </a>
      ) : (
        <span className="muted">원문 링크 미제공</span>
      )}
      {cite.evidence_grade === 3 && <span>미검증 참고 정보</span>}
    </div>
  );
}
/** 선택 부품의 핀·네트 연결 개념도. zoomable이면 그림을 눌러 큰 창으로 본다(작업대 왼쪽 "회로" 구역). */
export function Circuit({
  project,
  target,
  zoomable = false,
}: {
  project: Project | null;
  target: string;
  zoomable?: boolean;
}) {
  const part = partsOf(project).find((p) => p.ref === target),
    pins = pinsOf(project, target);
  const [open, setOpen] = useState(false);
  const drawing = part && (
    <svg viewBox="0 0 420 122" role="img" aria-label={`${target} ${part.value} 연결 개념도`}>
      <path
        d="M32 61H177m66 0h145M177 39v44l66-22-66-22Zm66 0v44"
        stroke="currentColor"
        strokeWidth="2"
        fill="none"
      />
      <circle cx="32" cy="61" r="4" fill="currentColor" />
      <circle cx="388" cy="61" r="4" fill="currentColor" />
      <text x="210" y="22" textAnchor="middle">
        {target} · {part.value}
      </text>
      {pins.slice(0, 2).map((p, i) => (
        <g key={p.pin}>
          <text x={i ? 365 : 55} y="48" textAnchor="middle">
            핀 {p.pin}
          </text>
          <text x={i ? 365 : 55} y="98" textAnchor="middle">
            {String(p.net).length > 19 ? String(p.net).slice(0, 16) + '…' : p.net}
          </text>
        </g>
      ))}
    </svg>
  );
  return (
    <div className="circuit" aria-label="선택 부품 연결도">
      <div className="circuit-label">핀과 네트 연결</div>
      {part ? (
        <>
          {zoomable ? (
            <button
              type="button"
              className="zoom-button"
              aria-label="연결 개념도 크게 보기"
              onClick={() => setOpen(true)}
            >
              {drawing}
            </button>
          ) : (
            drawing
          )}
          {open && (
            <Modal title="연결 개념도" close={() => setOpen(false)} wide>
              <Circuit project={project} target={target} />
            </Modal>
          )}
          <div className="pin-list">
            {pins.map((p) => (
              <span key={p.pin}>
                핀 {p.pin}
                {p.name && ` (${p.name})`} <b>{p.net}</b>
              </span>
            ))}
          </div>
          <small>연결 개념도 · 실제 기판 배치와 다릅니다.</small>
        </>
      ) : (
        <p>다이오드를 선택하면 연결을 표시합니다.</p>
      )}
    </div>
  );
}

/**
 * 서버 답(마크다운)을 그린다. 그림은 그리지 않고(모델 글이 브라우저에 임의 주소를 받게 하지 않는다),
 * http(s)가 아닌 링크(javascript: · mailto: · 상대 주소)는 링크 없이 글자로만 보인다. HTML은 react-markdown이 글자로 처리한다.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      urlTransform={markdownUrl}
      disallowedElements={['img']}
      components={{
        a: ({ href, children: label }) =>
          href ? (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {label}
            </a>
          ) : (
            <span>{label}</span>
          ),
      }}
    >
      {explainAnswer(children)}
    </ReactMarkdown>
  );
}
