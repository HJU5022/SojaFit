import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent, PointerEvent } from 'react'
import { useQuery } from '@tanstack/react-query'
import { findSchematic } from '../api/externalCircuits'
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

export function SchematicImage({ schematic, name, zoom, viewReset = 0, reload }: { schematic: SchematicEvidence; name: string; zoom: number; viewReset?: number; reload?: () => void }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
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
    if (drag.current && viewport.current?.hasPointerCapture(drag.current.id)) viewport.current.releasePointerCapture(drag.current.id)
    drag.current = null
    setDragging(false)
    setPan({ x: 0, y: 0 })
  }, [viewReset])
  function stopDrag(event: PointerEvent<HTMLDivElement>) {
    if (drag.current?.id !== event.pointerId) return
    drag.current = null
    setDragging(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  return <figure aria-label="원본 회로도 보기">
    <figcaption className="schematic-source">
      <div className="meta-fields"><span>출처: {schematic.attribution}</span><a href={schematic.original_url} target="_blank" rel="noreferrer">원본 자료 열기<span className="sr-only"> (새 탭)</span></a>{schematic.source_page_url && schematic.source_page_url !== schematic.original_url && <a href={schematic.source_page_url} target="_blank" rel="noreferrer">게시 페이지<span className="sr-only"> (새 탭)</span></a>}</div>
      {[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).length > 0 && <p>{[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).join(' · ')}</p>}
      <div className="meta-fields">{schematic.source_type === 'public_web' && <span>공개 웹 자료</span>}{schematic.evidence_grade === 3 && <span>커뮤니티 참고 자료 · 3등급</span>}<span>{schematic.evidence_grade === 2 ? '제조사 공식 여부: 확인됨 · 2등급' : '제조사 공식 여부: 미확인'}</span></div>
      <p>라이선스: {schematic.license === '미확인' || !schematic.license ? '이용·재배포 조건 미확인' : schematic.license}</p>
    </figcaption>
    <div ref={viewport} className="schematic-viewport" data-ready={status === 'ready'} data-dragging={dragging}
      role="region" aria-label="회로도 이미지 이동" tabIndex={0}
      aria-description="이미지를 드래그하거나 방향키로 이동합니다. Home 키로 가운데로 돌아갑니다."
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
        const directions: Record<string, { x: number; y: number }> = { ArrowLeft: { x: 40, y: 0 }, ArrowRight: { x: -40, y: 0 }, ArrowUp: { x: 0, y: 40 }, ArrowDown: { x: 0, y: -40 } }
        const delta = directions[event.key]
        if (!delta && event.key !== 'Home') return
        event.preventDefault()
        setPan(point => delta ? bound({ x: point.x + delta.x, y: point.y + delta.y }) : { x: 0, y: 0 })
      }}>
    {status === 'loading' && <div className="skeleton sheet-status" role="status"><span className="sr-only">원본 회로도를 불러오는 중입니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
    {status === 'error' && <div className="notice sheet-status" role="alert"><p>원본 회로도를 불러오지 못했습니다.</p><button className="btn" onClick={() => { if (reload) return reload(); setStatus('loading'); setAttempt(value => value + 1) }}>{reload ? '다시 검색하기' : '회로도 다시 불러오기'}</button></div>}
    <img ref={image} key={attempt} src={schematic.image_url} alt={`${name} 원본 회로도`} draggable={false} hidden={status !== 'ready'} onLoad={() => setStatus('ready')} onError={() => setStatus('error')} style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom / 100})` }} />
    </div>
  </figure>
}

function waitText(seconds: number) { return seconds >= 60 ? `${Math.ceil(seconds / 60)}분` : `${seconds}초` }
// 503이면서 Retry-After가 없으면 기능 꺼짐(키 없는 데모·설정 누락)이라 다시 시도를 권하지 않는다.
const disabled = (error: unknown) => (error as ApiError | null)?.code === 'UNAVAILABLE' && !(error as ApiError).retryAfter
function sourceLabel(sourceType: 'manufacturer_official' | 'community' | 'public_web') {
  if (sourceType === 'manufacturer_official') return '제조사 공식'
  if (sourceType === 'community') return '커뮤니티 참고 자료'
  return '제조사 공식 여부 미확인'
}
function searchMessage(error: ApiError, componentType: '' | 'diode') {
  if (error.code === 'SCHEMATIC_NOT_FOUND' && componentType === 'diode') return '입력한 다이오드 품번과 관련된 회로 자료를 확인하지 못했습니다. 제조사와 품번을 보완해 다시 찾아 주세요. 창을 닫으면 연결 개념도는 계속 볼 수 있습니다.'
  if (error.code === 'SCHEMATIC_NOT_FOUND' && /검색 결과가 없습니다|후보를 찾았지만/.test(error.message)) return errorMessage(error)
  if (error.code === 'SCHEMATIC_NOT_FOUND') return '공개된 원본 회로도를 찾지 못했습니다. 검색어를 바꿔 다시 찾아 보세요. 창을 닫으면 연결 개념도는 계속 볼 수 있습니다.'
  if (error.code === 'UPSTREAM_ERROR') return '외부 회로도를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
  if (error.code === 'UNAVAILABLE') return error.retryAfter ? `외부 회로도 조회 한도에 닿았습니다. ${waitText(error.retryAfter)} 뒤에 다시 시도해 주세요.` : '이 환경에서는 외부 원본 회로도를 사용할 수 없습니다. 창을 닫고 연결 개념도를 확인해 주세요.'
  return errorMessage(error)
}

// 검색은 누를 때만 보낸다(검색마다 외부 호출이 든다). 같은 검색어는 5분 동안 다시 보내지 않는다.
export function ExternalSchematic({ name, zoom, viewReset = 0, defaultComponentType = '' }: { name: string; zoom: number; viewReset?: number; defaultComponentType?: '' | 'diode' }) {
  const [text, setText] = useState(name)
  const [componentType, setComponentType] = useState(defaultComponentType)
  const [searched, setSearched] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const term = text.trim()
  const valid = term.length >= 2 && term.length <= 200
  const result = useQuery({ queryKey: ['external-schematic', searched, selectedSource, ...(componentType ? [componentType] : [])], queryFn: ({ signal }) => findSchematic(searched, signal, selectedSource, componentType || undefined), enabled: searched !== '', retry: false, staleTime: 5 * 60_000,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: false })
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!valid || result.isFetching) return
    if (term !== searched || selectedSource) { setSelectedSource(''); setSearched(term) }
    else if (result.isError || result.isStale) void result.refetch()
  }
  const data = searched ? result.data : undefined
  return <div className="sheets">
    {!disabled(result.error) && <form onSubmit={search}>
      <label className="field"><span>검색 대상</span><select className="input" value={componentType} onChange={event => { setComponentType(event.target.value as '' | 'diode'); setSearched(''); setSelectedSource('') }}><option value="">제품·보드 회로도</option><option value="diode">다이오드 사용 회로</option></select></label>
      {componentType === 'diode' && <p className="field-hint">다이오드 품번을 입력하세요. 해당 부품과 관련된 회로 자료만 찾으며, 같은 이름의 다른 제품은 제외합니다.</p>}
      <label className="field"><span>검색어 (올린 넷리스트의 프로젝트 이름과 다를 수 있습니다)</span><input className="input" value={text} onChange={event => { setText(event.target.value); setSearched(''); setSelectedSource('') }} maxLength={200} autoComplete="off" aria-describedby="schematic-rule" /></label>
      <p className="field-hint" id="schematic-rule">2자 이상 200자 이하로 입력해 주세요.</p>
      <div className="dialog-foot"><button className="btn btn-primary" disabled={!valid || result.isFetching}>{result.isFetching ? '찾는 중' : '원본 회로도 찾기'}</button></div>
    </form>}
    {result.isFetching && <div className="skeleton inset" role="status"><span className="sr-only">원본 회로도를 찾는 중입니다. 몇 초 걸릴 수 있습니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
    {result.error && !result.isFetching && <p className="notice inset" role="alert" {...requestIdProps(result.error)}>{searchMessage(result.error as unknown as ApiError, componentType)}</p>}
    {data && data.choices.length > 1 && <div className="inset" aria-label="검색된 회로도 후보">
      <p>보기 원하는 회로도 자료를 선택하세요. 선택하면 아래 회로도와 출처가 바뀝니다.</p>
      {data.choices.map(choice => <button className="btn" key={choice.source_url}
        aria-pressed={choice.source_url === data.source_url}
        onClick={() => setSelectedSource(choice.source_url)}
        disabled={result.isFetching}>
        {choice.source_url === data.source_url ? '현재 보는 자료: ' : '이 자료 보기: '}{choice.title} · {sourceLabel(choice.source_type)}
      </button>)}
    </div>}
    {data && data.images.map(image => <SchematicImage key={image.url} schematic={{ image_url: image.url, original_url: data.source_url, attribution: data.attribution, license: data.license,
      evidence_grade: data.evidence_grade, source_type: data.source_type,
      manufacturer: data.manufacturer, model: data.model, revision: data.revision,
      source_page_url: data.repository_url }}
      name={`${data.model || data.project || searched} 시트 ${image.sheet + 1}`} zoom={zoom} viewReset={viewReset} reload={() => void result.refetch()} />)}
  </div>
}
