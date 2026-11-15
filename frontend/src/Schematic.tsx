/**
 * 원본 회로도 구역: 예제(데모) 프로젝트의 저장된 원본 그림과, 누를 때만 하는 공개 웹 검색(GET /api/external-circuits/schematics).
 * 하지 않는 일: 회로 일치 판단(서버가 부품·핀 연결 대조로 승인한 도면만 돌려준다), 검색 결과 저장, 자동 검색.
 * [왜] 검색은 외부 검색 서비스를 부를 수 있어 버튼을 누를 때만 보낸다. 출처: SPEC 4절(external-circuits), README 외부 공개 회로도.
 */
import { useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { api } from './api';
import { safeLink, sameOriginImage } from './display';
import { ErrorBox, Loading, useResource } from './ui';
import type { Demo, ExternalSchematic, Project } from './types';

const SOURCE = {
  manufacturer_official: '제조사 공식',
  community: '커뮤니티 참고 자료 · 미검증',
  public_web: '공개 웹 자료 · 제조사 공식 여부 미확인',
};

/** 도면 한 장(또는 여러 장)과 출처·라이선스. 이미지를 누르면 새 탭에서 크게 봅니다. */
function Figure({
  name,
  images,
  attribution,
  license,
  originalUrl,
  note,
}: {
  name: string;
  images: string[];
  attribution: string;
  license: string;
  originalUrl?: string | null;
  note?: string;
}) {
  const link = safeLink(originalUrl);
  return (
    <figure className="schematic-figure">
      {images.map((src, i) => (
        <a
          key={src}
          href={src}
          target="_blank"
          rel="noreferrer noopener"
          title="새 탭에서 크게 보기"
        >
          <img src={src} alt={`${name} 원본 회로도${images.length > 1 ? ` ${i + 1}쪽` : ''}`} />
        </a>
      ))}
      <figcaption>
        <span>출처: {attribution || '미제공'}</span>
        <span>
          라이선스: {!license || license === '미확인' ? '이용·재배포 조건 미확인' : license}
        </span>
        {note && <span>{note}</span>}
        {link && (
          <a href={link} target="_blank" rel="noreferrer noopener">
            원본 자료 열기 <ExternalLink size={13} />
          </a>
        )}
      </figcaption>
    </figure>
  );
}

export function SchematicSection({
  project,
  threadId,
}: {
  project: Project;
  threadId: string | null;
}) {
  // [왜] 저장된 그림은 데모 모드의 예제 프로젝트에만 있다. 목록이 404인 운영에서는 오류를 보이지 않고 검색만 둔다.
  const demos = useResource<Demo[]>(project.demo_id ? '/demo-circuits' : null);
  const saved = demos.data?.find((d) => d.id === project.demo_id)?.schematic;
  const savedImage = sameOriginImage(saved?.image_url);
  const [query, setQuery] = useState(project.name);
  const [result, setResult] = useState<ExternalSchematic | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  async function search(sourceUrl?: string) {
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        q: query.trim(),
        project_id: String(project.id),
        circuit_version: String(project.circuit_version),
      });
      if (threadId) params.set('thread_id', threadId);
      if (sourceUrl) params.set('source_url', sourceUrl);
      setResult(await api<ExternalSchematic>('/external-circuits/schematics?' + params));
    } catch (e) {
      setResult(null);
      setError(e as Error);
    } finally {
      setBusy(false);
    }
  }
  const images = result?.images.map((i) => sameOriginImage(i.url)).filter(Boolean) as string[];
  return (
    <details className="schematic-section">
      <summary>원본 회로도</summary>
      {demos.loading && <Loading />}
      {saved && savedImage && (
        <Figure
          name={project.name}
          images={[savedImage]}
          attribution={saved.attribution}
          license={saved.license}
          originalUrl={saved.original_url}
        />
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim().length >= 2) void search();
        }}
      >
        <label>
          웹에서 원본 회로도 찾기
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            minLength={2}
            maxLength={200}
            required
          />
        </label>
        <small>
          누를 때만 검색합니다. 업로드한 회로와 부품·핀 연결이 같다고 확인된 도면만 보입니다.
        </small>
        <button disabled={busy || query.trim().length < 2}>{busy ? '찾는 중…' : '찾기'}</button>
      </form>
      <ErrorBox error={error} />
      {result && images.length > 0 && (
        <Figure
          name={result.model ?? project.name}
          images={images}
          attribution={result.attribution}
          license={result.license}
          originalUrl={result.source_url}
          note={[SOURCE[result.source_type], result.manufacturer, result.model, result.revision]
            .filter(Boolean)
            .join(' · ')}
        />
      )}
      {result && result.choices.length > 0 && (
        <div className="schematic-choices">
          <p>여러 후보가 있습니다. 하나를 고르면 그 자료로 다시 찾습니다.</p>
          {result.choices.map((c) => (
            <button
              key={c.source_url}
              disabled={busy || !safeLink(c.source_url)}
              onClick={() => void search(c.source_url)}
            >
              {c.title} · {SOURCE[c.source_type]}
              {c.revision ? ` · ${c.revision}` : ''}
            </button>
          ))}
        </div>
      )}
    </details>
  );
}
