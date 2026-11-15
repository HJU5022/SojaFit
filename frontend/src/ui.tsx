/** 공통 상태·접근성·회로 표시. 서버 값을 시각화하며 판정은 계산하지 않는다. 출처: SPEC 3·4절. */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, CircuitBoard, LoaderCircle, X } from 'lucide-react';
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
          <button type="button" className="text-button" onClick={retry}>
            다시 시도
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
      <div className="dialog-head">
        <h2>{title}</h2>
        <button aria-label="닫기" className="icon-button" onClick={close}>
          <X size={20} />
        </button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
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
export function Circuit({ project, target }: { project: Project | null; target: string }) {
  const part = partsOf(project).find((p) => p.ref === target),
    pins = pinsOf(project, target);
  return (
    <div className="circuit" aria-label="선택 부품 연결도">
      <div className="circuit-label">핀과 네트 연결</div>
      {part ? (
        <>
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
