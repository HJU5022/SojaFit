import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, PointerEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Maximize2 } from 'lucide-react'
import { findSchematic } from '../api/externalCircuits'
import type { SchematicContext } from '../api/externalCircuits'
import { errorMessage, requestIdProps } from '../api/client'
import type { ApiError } from '../api/client'
import type { DemoSchematic } from '../api/projects'

// 이미지 주소가 바뀌면 대기 상태도 초기화해 이전 회로의 오류를 남기지 않는다. reload가 있으면 같은 주소 대신 그 동작으로 다시 받는다(서명 주소 만료).
type SchematicEvidence = Pick<DemoSchematic, 'image_url' | 'original_url' | 'attribution' | 'license'> & {
  evidence_grade?: 2 | 3 | null
  source_type?: 'manufacturer_official' | 'community' | 'public_web'
  source_page_url?: string | null
  manufacturer?: string | null
  model?: string | null
  revision?: string | null
}

export function SchematicImage({ schematic, name, reload }: { schematic: SchematicEvidence; name: string; reload?: () => void }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  const [zoom, setZoom] = useState(100)
  const viewport = useRef<HTMLDivElement>(null)
  const image = useRef<HTMLImageElement>(null)
  const drag = useRef<{ id: number; x: number; y: number; start: { x: number; y: number } } | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const bound = useCallback((point: { x: number; y: number }) => {
    const box = viewport.current, img = image.current
    if (!box || !img?.naturalWidth || !img.naturalHeight) return { x: 0, y: 0 }
    const fit = Math.min(box.clientWidth / img.naturalWidth, box.clientHeight / img.naturalHeight) * zoom / 100
    const x = Math.abs(img.naturalWidth * fit - box.clientWidth) / 2
    const y = Math.abs(img.naturalHeight * fit - box.clientHeight) / 2
    return { x: Math.max(-x, Math.min(x, point.x)), y: Math.max(-y, Math.min(y, point.y)) }
  }, [zoom])
  useEffect(() => {
    const adjust = () => setPan(point => bound(point))
    adjust()
    if (!viewport.current || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(adjust)
    observer.observe(viewport.current)
    return () => observer.disconnect()
  }, [bound])
  useEffect(() => {
    const box = viewport.current
    if (!box || status !== 'ready') return
    // React의 기본 passive 휠 대신 이미지 안에서만 스크롤/브라우저 확대를 막는다.
    const wheel = (event: WheelEvent) => {
      if (!event.deltaY) return
      event.preventDefault()
      if (!drag.current) setZoom(value => Math.max(50, Math.min(400, value + (event.deltaY < 0 ? 25 : -25))))
    }
    box.addEventListener('wheel', wheel, { passive: false })
    return () => box.removeEventListener('wheel', wheel)
  }, [status])
  function fit() {
    if (drag.current && viewport.current?.hasPointerCapture(drag.current.id)) viewport.current.releasePointerCapture(drag.current.id)
    drag.current = null
    setDragging(false)
    setPan({ x: 0, y: 0 })
    setZoom(100)
  }
  function stopDrag(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.id !== event.pointerId) return
    drag.current = null
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  return <figure aria-label="원본 회로도 보기">
    <div ref={viewport} className="schematic-viewport" data-ready={status === 'ready'} data-dragging={dragging}
      role="region" aria-label="회로도 이미지 이동" tabIndex={0}
      aria-description="휠 또는 +, - 키로 확대·축소하고 드래그나 방향키로 이동합니다. Home 키로 이미지에 맞춥니다."
      onPointerDown={event => {
        if (status !== 'ready' || event.button !== 0 || event.isPrimary === false || drag.current) return
        event.preventDefault()
        event.currentTarget.focus({ preventScroll: true })
        event.currentTarget.setPointerCapture(event.pointerId)
        drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, start: pan }
        setDragging(true)
      }} onPointerMove={event => {
        const current = drag.current
        if (current?.id === event.pointerId) setPan(bound({ x: current.start.x + event.clientX - current.x, y: current.start.y + event.clientY - current.y }))
      }} onPointerUp={stopDrag} onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}
      onKeyDown={event => {
        if (status !== 'ready' || event.target !== event.currentTarget) return
        if (event.key === '+' || event.key === '=' || event.key === '-') {
          event.preventDefault()
          setZoom(value => Math.max(50, Math.min(400, value + (event.key === '-' ? -25 : 25))))
          return
        }
        const directions: Record<string, { x: number; y: number }> = { ArrowLeft: { x: 40, y: 0 }, ArrowRight: { x: -40, y: 0 }, ArrowUp: { x: 0, y: 40 }, ArrowDown: { x: 0, y: -40 } }
        const delta = directions[event.key]
        if (!delta && event.key !== 'Home') return
        event.preventDefault()
        if (delta) setPan(point => bound({ x: point.x + delta.x, y: point.y + delta.y }))
        else fit()
      }}>
    {status === 'loading' && <div className="skeleton sheet-status" role="status"><span className="sr-only">원본 회로도를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
    {status === 'error' && <div className="notice sheet-status" role="alert"><p>원본 회로도를 불러오지 못했습니다.</p><button className="btn" onClick={() => { if (reload) return reload(); setStatus('loading'); setAttempt(value => value + 1) }}>{reload ? '다시 검색하기' : '회로도 다시 불러오기'}</button></div>}
    <img ref={image} key={attempt} src={schematic.image_url} alt={`${name} 원본 회로도`} draggable={false} hidden={status !== 'ready'} onLoad={() => setStatus('ready')} onError={() => setStatus('error')} style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})` }} />
    {status === 'ready' && <button type="button" className="icon-btn schematic-fit" aria-label="회로도 맞춤" title="이미지 맞춤 (Home)" onPointerDown={event => event.stopPropagation()} onClick={fit}><Maximize2 aria-hidden="true" /></button>}
    </div>
    <figcaption className="meta-fields">
      {schematic.evidence_grade === 2 && <span>제조사 공식 원본 · 2등급</span>}
      {schematic.evidence_grade === 3 && <span>커뮤니티 참고 · 3등급</span>}
      {schematic.source_type === 'public_web' && <span>공개 웹 자료 · 출처 확인 필요</span>}
      {[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).length > 0 &&
        <span>{[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).join(' · ')}</span>}
      <span>출처: {schematic.attribution}</span><span>라이선스: {schematic.license}</span>
      <a href={schematic.original_url} target="_blank" rel="noreferrer">원본 자료<span className="sr-only"> (새 탭)</span></a>
      {schematic.source_page_url && schematic.source_page_url !== schematic.original_url && <a href={schematic.source_page_url} target="_blank" rel="noreferrer">게시 페이지<span className="sr-only"> (새 탭)</span></a>}
    </figcaption>
  </figure>
}

function waitText(seconds: number) { return seconds >= 60 ? `${Math.ceil(seconds / 60)}분` : `${seconds}초` }
// 503이면서 Retry-After가 없으면 기능 꺼짐(키 없는 데모·설정 누락)이라 다시 시도를 권하지 않는다.
const disabled = (error: unknown) => (error as ApiError | null)?.code === 'UNAVAILABLE' && !(error as ApiError).retryAfter
function searchMessage(error: ApiError) {
  if (error.code === 'SCHEMATIC_NOT_FOUND' && /검색 결과가 없습니다|후보를 찾았지만|업로드한 회로와/.test(error.message)) return errorMessage(error)
  if (error.code === 'SCHEMATIC_NOT_FOUND') return '공개된 원본 회로도를 찾지 못했습니다. 검색어를 바꿔 다시 찾아 보세요. 창을 닫으면 연결 개념도는 계속 볼 수 있습니다.'
  if (error.code === 'UPSTREAM_ERROR') return '외부 회로도를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
  if (error.code === 'UNAVAILABLE') return error.retryAfter ? `외부 회로도 조회 한도에 닿았습니다. ${waitText(error.retryAfter)} 뒤에 다시 시도해 주세요.` : '이 환경에서는 외부 원본 회로도를 사용할 수 없습니다. 창을 닫고 연결 개념도를 확인해 주세요.'
  return errorMessage(error)
}

// 검색은 누를 때만 보낸다(검색마다 외부 호출이 든다). 같은 검색어는 5분 동안 다시 보내지 않는다.
export function ExternalSchematic({ name, context }: { name: string; context?: SchematicContext }) {
  const [text, setText] = useState(name)
  const [searched, setSearched] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const term = text.trim()
  const valid = term.length >= 2 && term.length <= 200
  const result = useQuery({ queryKey: context ? ['external-schematic', context.projectId, context.circuitVersion, context.threadId ?? '', searched, selectedSource] : ['external-schematic', searched, selectedSource], queryFn: ({ signal }) => findSchematic(searched, signal, selectedSource, context), enabled: searched !== '', retry: false, staleTime: 5 * 60_000,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: false })
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!valid || result.isFetching) return
    if (term !== searched || selectedSource) { setSelectedSource(''); setSearched(term) }
    else if (result.isError || result.isStale) void result.refetch()
  }
  const received = searched ? result.data : undefined
  const data = received && (!context || received.circuit_version === context.circuitVersion) ? received : undefined
  return <div className="sheets">
    {!disabled(result.error) && <form onSubmit={search}>
      <label className="field"><span>검색어 (올린 넷리스트의 프로젝트 이름과 다를 수 있습니다)</span><input className="input" value={text} onChange={event => setText(event.target.value)} maxLength={200} autoComplete="off" aria-describedby="schematic-rule" /></label>
      <p className="field-hint" id="schematic-rule">2자 이상 200자 이하로 입력해 주세요.</p>
      <div className="dialog-foot"><button className="btn btn-primary" disabled={!valid || result.isFetching}>{result.isFetching ? '찾는 중' : '원본 회로도 찾기'}</button></div>
    </form>}
    {result.isFetching && <div className="skeleton inset" role="status"><span className="sr-only">원본 회로도를 찾는 중입니다. 몇 초 걸릴 수 있습니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
    {result.error && !result.isFetching && <p className="notice inset" role="alert" {...requestIdProps(result.error)}>{searchMessage(result.error as unknown as ApiError)}</p>}
    {received && !data && <p className="notice inset" role="alert">현재 회로 버전과의 일치를 확인하지 못해 도면을 표시하지 않습니다.</p>}
    {data && context && <p className="inset">업로드 회로 v{context.circuitVersion} · 부품·핀 연결 일치</p>}
    {data && context && <p className="field-hint inset">도면의 참조 번호는 업로드 파일과 다를 수 있습니다. 부품 정보와 전체 핀 연결을 대조한 결과입니다.</p>}
    {data && data.choices.length > 1 && <div className="inset" aria-label="검색된 회로도 후보">
      <p>검색된 회로도 후보를 확인해 선택하세요.</p>
      {data.choices.map(choice => <button className="btn" key={choice.source_url}
        aria-pressed={choice.source_url === data.source_url}
        onClick={() => setSelectedSource(choice.source_url)}
        disabled={result.isFetching}>
        {choice.title} · {choice.source_type === 'manufacturer_official' ? '제조사 공식' : '출처 확인 필요'}
      </button>)}
    </div>}
    {data && data.images.map(image => <SchematicImage key={image.url} schematic={{ image_url: image.url, original_url: data.source_url, attribution: data.attribution, license: data.license,
      evidence_grade: data.evidence_grade, source_type: data.source_type,
      manufacturer: data.manufacturer, model: data.model, revision: data.revision,
      source_page_url: data.repository_url }}
      name={`${data.model || data.project || searched} 시트 ${image.sheet + 1}`} reload={() => void result.refetch()} />)}
  </div>
}
