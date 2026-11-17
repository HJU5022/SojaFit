/**
 * 원본 회로도 구역(작업대 오른쪽 회로 패널의 "회로" 구역, 연결 개념도 아래): 회로도(.kicad_sch)를 올린 회로 버전은 그 그림(GET /api/projects/{id}/schematic, #52)을,
 * 예제(데모) 프로젝트는 저장된 원본 그림을, 넷리스트가 있는 그 밖의 프로젝트는
 * 열 때 한 번 공개 웹 검색(GET /api/external-circuits/schematics)한 결과를 바로 보인다. 그림을 누르면 큰 창으로 본다.
 * 하지 않는 일: 검색 범위·회로 일치 판단(서버가 원본/참고를 구분하고 원본의 부품·핀 연결을 대조한다), 검색 결과를 서버·브라우저 저장소에 저장.
 * [왜] 검색은 유료 외부 검색과 3~20초 렌더를 거치므로 같은 (프로젝트, 회로 버전)은 다시 보내지 않는다(`schematicSearch.ts`).
 * 출처: SPEC 4절(external-circuits), README 외부 공개 회로도.
 */
import { useEffect, useRef, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { api, ApiError } from './api';
import { partsOf } from './circuit';
import { safeLink, sameOriginImage } from './display';
import { schematicLabel, schematicSearchParams, searchOnce } from './schematicSearch';
import { ErrorBox, Loading, Modal, useResource } from './ui';
import type { Demo, ExternalSchematic, Project } from './types';

const SOURCE = {
  manufacturer_official: '제조사 공식',
  community: '커뮤니티 참고 자료 · 미검증',
  public_web: '공개 웹 자료 · 제조사 공식 여부 미확인',
};

type FigureProps = {
  name: string;
  images: string[];
  attribution: string;
  kind?: string;
  /** 없으면(올린 회로도) 라이선스 줄을 두지 않는다 */
  license?: string;
  originalUrl?: string | null;
  note?: string;
};

/**
 * 도면과 출처·라이선스. onOpen이 있으면(회로 패널) 첫 장만 작게 보이고 누르면 큰 창을 연다.
 * 없으면(큰 창) 모든 장을 보이고 각 장을 누르면 새 탭에서 원래 크기로 연다.
 */
function Figure({
  name,
  images,
  attribution,
  kind = '원본 회로도',
  license,
  originalUrl,
  note,
  onOpen,
}: FigureProps & { onOpen?: () => void }) {
  const link = safeLink(originalUrl);
  const alt = (i: number) => `${name} ${kind}${images.length > 1 ? ` ${i + 1}쪽` : ''}`;
  return (
    <figure className="schematic-figure">
      {onOpen ? (
        <button
          type="button"
          className="zoom-button"
          aria-label={`${kind} 크게 보기`}
          onClick={onOpen}
        >
          <img src={images[0]} alt={alt(0)} />
        </button>
      ) : (
        images.map((src, i) => (
          <a
            key={src}
            href={src}
            target="_blank"
            rel="noreferrer noopener"
            title="새 탭에서 원래 크기로 보기"
          >
            <img src={src} alt={alt(i)} />
          </a>
        ))
      )}
      <figcaption>
        {onOpen && images.length > 1 && <span>전체 {images.length}쪽 · 누르면 모두 봅니다</span>}
        <span>출처: {attribution || '미제공'}</span>
        {license !== undefined && (
          <span>
            라이선스: {!license || license === '미확인' ? '이용·재배포 조건 미확인' : license}
          </span>
        )}
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
  onAttach,
}: {
  project: Project;
  threadId: string | null;
  /** 회로도 파일 첨부 창을 연다(작업대 입력창의 첨부와 같은 길). 없으면 단추를 보이지 않는다 */
  onAttach?: () => void;
}) {
  // [왜] 저장된 그림은 데모 모드의 예제 프로젝트에만 있다. 목록이 404인 운영에서는 오류를 보이지 않고 웹 검색으로 넘어간다.
  const demos = useResource<Demo[]>(project.demo_id ? '/demo-circuits' : null);
  const saved = demos.data?.find((d) => d.id === project.demo_id)?.schematic;
  const savedImage = sameOriginImage(saved?.image_url);
  const hasNetlist = partsOf(project).length > 0;
  // [왜] 회로도를 올린 버전은 그 그림이 원본이다. 유료 웹 검색을 자동으로 부르지 않는다(#52)
  const uploaded = project.schematic_file
    ? sameOriginImage(
        `/api/projects/${project.id}/schematic?circuit_version=${project.circuit_version}`,
      )
    : undefined;
  const key = `auto:${project.id}:${project.circuit_version}`;
  // [주의] 늦게 끝난 검색이 회로 버전이 바뀐 뒤의 화면을 덮지 않도록 지금 보이는 키를 둔다.
  const shown = useRef(key);
  shown.current = key;
  const [query, setQuery] = useState(project.name);
  const [result, setResult] = useState<ExternalSchematic | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  function search(q: string, fresh: boolean, sourceUrl?: string) {
    const params = schematicSearchParams(
      q,
      project.id,
      project.circuit_version,
      threadId,
      sourceUrl,
    );
    setBusy(true);
    setError(null);
    searchOnce(key, () => api<ExternalSchematic>('/external-circuits/schematics?' + params), fresh)
      .then((r) => {
        if (shown.current === key) setResult(r);
      })
      .catch((e) => {
        if (shown.current !== key) return;
        setResult(null);
        setError(e as Error);
      })
      .finally(() => {
        if (shown.current === key) setBusy(false);
      });
  }
  // [왜] 데모 목록을 다 받은 뒤에 판단해야 저장된 그림이 있는 예제 프로젝트가 유료 검색을 부르지 않는다.
  // 프로젝트 이름이 2자 미만이면 서버가 422로 거절하므로 자동으로 보내지 않고 검색 칸만 보인다.
  const auto =
    !uploaded && !demos.loading && !savedImage && hasNetlist && project.name.trim().length >= 2;
  useEffect(() => {
    setResult(null);
    setError(null);
    setBusy(false);
    if (auto) search(project.name, false);
    // [주의] threadId는 넣지 않는다. 같은 회로 버전이면 대화를 옮겨도 같은 결과를 쓴다.
  }, [key, auto]);
  const images = (result?.images.map((i) => sameOriginImage(i.url)).filter(Boolean) ??
    []) as string[];
  const figure: FigureProps | null = uploaded
    ? {
        name: project.name,
        images: [uploaded],
        attribution: '업로드한 회로도',
        note: project.schematic_file ?? undefined,
      }
    : saved && savedImage
      ? {
          name: project.name,
          images: [savedImage],
          attribution: saved.attribution,
          license: saved.license,
          originalUrl: saved.original_url,
        }
      : result && images.length
        ? {
            name: result.model ?? project.name,
            images,
            attribution: result.attribution,
            kind: schematicLabel(result),
            license: result.license,
            originalUrl: result.source_url,
            note: [SOURCE[result.source_type], result.manufacturer, result.model, result.revision]
              .filter(Boolean)
              .join(' · '),
          }
        : null;
  const missing = error instanceof ApiError && error.code === 'SCHEMATIC_NOT_FOUND';
  return (
    <div className="schematic-section">
      <div className="circuit-label">{figure?.kind ?? '원본 회로도'}</div>
      {figure && <Figure {...figure} onOpen={() => setOpen(true)} />}
      {demos.loading || busy ? (
        <Loading label={busy ? '회로도를 찾는 중' : undefined} />
      ) : figure ? (
        result &&
        result.choices.length > 0 && (
          <details className="schematic-choices">
            <summary>다른 후보 {result.choices.length}개</summary>
            <p>하나를 고르면 그 자료로 다시 찾습니다.</p>
            {result.choices.map((c) => (
              <button
                type="button"
                key={c.source_url}
                disabled={!safeLink(c.source_url)}
                onClick={() => search(query, true, c.source_url)}
              >
                {c.title} · {SOURCE[c.source_type]}
                {c.revision ? ` · ${c.revision}` : ''}
              </button>
            ))}
          </details>
        )
      ) : !hasNetlist ? (
        <p className="muted">넷리스트를 올리면 원본 회로도를 찾습니다.</p>
      ) : error instanceof ApiError && error.status === 503 ? (
        // [왜] 데모 모드·검색 키 없음·외부 요청 한도에서는 다시 찾아도 같으므로 검색 칸 없이 안내만 둔다
        <p className="muted">{error.message}</p>
      ) : (
        <>
          {missing ? (
            // [왜] 넷리스트에는 부품 위치 · 배선이 없어 회로도를 만들 수 없다. 공개 원본도 찾지 못하면 그 한계를 그대로 알리고
            //      회로도 파일(.kicad_sch)을 올리는 길을 바로 준다(11-17 조장 결정: 자동 생성은 하지 않고 한계로 적는다)
            <div className="schematic-missing">
              <strong>원본 회로도를 보여 드릴 수 없어요</strong>
              <span>
                넷리스트(.net)에는 부품 위치와 배선이 없어 SojaFit이 회로도 그림을 만들 수 없고,
                연결이 같은 공개 원본도 찾지 못했어요. 회로도 파일(.kicad_sch)을 첨부하면 그 그림을
                보여 드려요.
              </span>
              {onAttach && (
                <button type="button" className="primary" onClick={onAttach}>
                  회로도 파일(.kicad_sch) 첨부
                </button>
              )}
            </div>
          ) : (
            <ErrorBox error={error} retry={() => search(query, true)} />
          )}
        </>
      )}
      {hasNetlist &&
        !uploaded &&
        !savedImage &&
        !busy &&
        !demos.loading &&
        !(error instanceof ApiError && error.status === 503) && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (query.trim().length >= 2) search(query, true);
            }}
          >
            <label>
              다른 이름으로 찾기
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                minLength={2}
                maxLength={200}
                required
              />
            </label>
            <small>품번은 참고 회로로, 프로젝트 원본은 연결이 일치할 때만 표시합니다.</small>
            <button disabled={query.trim().length < 2}>찾기</button>
          </form>
        )}
      {open && figure && (
        <Modal title={figure.kind ?? '원본 회로도'} close={() => setOpen(false)} wide>
          <Figure {...figure} />
        </Modal>
      )}
    </div>
  );
}
