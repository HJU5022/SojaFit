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

export function SchematicImage({ schematic, name, zoom: requestedZoom, viewReset = 0, reload }: { schematic: SchematicEvidence; name: string; zoom?: number; viewReset?: number; reload?: () => void }) {
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attempt, setAttempt] = useState(0)
  const [zoom, setZoom] = useState(100)
  const viewport = useRef<HTMLDivElement>(null)
  const image = useRef<HTMLImageElement>(null)
  const drag = useRef<{ id: number; x: number; y: number; start: { x: number; y: number } } | null>(null)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  useEffect(() => { if (requestedZoom !== undefined) setZoom(requestedZoom) }, [requestedZoom])
  useEffect(() => {
    drag.current = null
    setDragging(false)
    setPan({ x: 0, y: 0 })
  }, [viewReset])
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
    <figcaption className="schematic-source">
      <div className="meta-fields"><span>출처: {schematic.attribution}</span><a href={schematic.original_url} target="_blank" rel="noreferrer">원본 자료 열기<span className="sr-only"> (새 탭)</span></a>{schematic.source_page_url && schematic.source_page_url !== schematic.original_url && <a href={schematic.source_page_url} target="_blank" rel="noreferrer">게시 페이지<span className="sr-only"> (새 탭)</span></a>}</div>
      {[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).length > 0 && <p>{[schematic.manufacturer, schematic.model, schematic.revision].filter(Boolean).join(' · ')}</p>}
      <div className="meta-fields">{schematic.source_type === 'public_web' && <span>공개 웹 자료</span>}{schematic.evidence_grade === 3 && <span>커뮤니티 참고 자료 · 3등급</span>}<span>{schematic.evidence_grade === 2 ? '제조사 공식 여부: 확인됨 · 2등급' : '제조사 공식 여부: 미확인'}</span></div>
      <p>라이선스: {schematic.license === '미확인' || !schematic.license ? '이용·재배포 조건 미확인' : schematic.license}</p>
    </figcaption>
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
  </figure>
}

function waitText(seconds: number) { return seconds >= 60 ? `${Math.ceil(seconds / 60)}분` : `${seconds}초` }
// 503이면서 Retry-After가 없으면 기능 꺼짐(키 없는 데모·설정 누락)이라 다시 시도를 권하지 않는다.
const disabled = (error: unknown) => (error as ApiError | null)?.code === 'UNAVAILABLE' && !(error as ApiError).retryAfter
function sourceLabel(sourceType: 'manufacturer_official' | 'community' | 'public_web') {
  return sourceType === 'manufacturer_official' ? '제조사 공식' : sourceType === 'community' ? '커뮤니티 참고 자료' : '제조사 공식 여부 미확인'
}
function searchMessage(error: ApiError, componentType: string) {
  if (error.code === 'SCHEMATIC_NOT_FOUND' && componentType === 'diode') return '입력한 다이오드 품번과 관련된 회로 자료를 확인하지 못했습니다. 제조사와 품번을 보완해 다시 찾아 주세요.'
  if (error.code === 'SCHEMATIC_NOT_FOUND' && /검색 결과가 없습니다|후보를 찾았지만|업로드한 회로와/.test(error.message)) return errorMessage(error)
  if (error.code === 'SCHEMATIC_NOT_FOUND') return '공개된 원본 회로도를 찾지 못했습니다. 검색어를 바꿔 다시 찾아 보세요. 창을 닫으면 연결 개념도는 계속 볼 수 있습니다.'
  if (error.code === 'UPSTREAM_ERROR') return '외부 회로도를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.'
  if (error.code === 'UNAVAILABLE') return error.retryAfter ? `외부 회로도 조회 한도에 닿았습니다. ${waitText(error.retryAfter)} 뒤에 다시 시도해 주세요.` : '이 환경에서는 외부 원본 회로도를 사용할 수 없습니다. 창을 닫고 연결 개념도를 확인해 주세요.'
  return errorMessage(error)
}

// 검색은 누를 때만 보낸다(검색마다 외부 호출이 든다). 같은 검색어는 5분 동안 다시 보내지 않는다.
export function ExternalSchematic({ name, context, zoom, viewReset = 0, defaultComponentType = '' }: { name: string; context?: SchematicContext; zoom?: number; viewReset?: number; defaultComponentType?: '' | 'diode' }) {
  const [text, setText] = useState(name)
  const [componentType, setComponentType] = useState<'' | 'reference' | 'diode'>(context ? '' : defaultComponentType)
  const [searched, setSearched] = useState('')
  const [selectedSource, setSelectedSource] = useState('')
  const [showImage, setShowImage] = useState(false)
  const term = text.trim()
  const maxLength = componentType === 'diode' ? 194 : 200
  const valid = term.length >= 2 && term.length <= maxLength
  const effectiveContext = componentType === '' ? context : undefined
  const guidance = componentType === 'diode' ? {
    description: '입력한 다이오드가 사용된 회로를 참고용으로 찾습니다. 업로드 회로와 동일한 회로라는 뜻이 아닙니다.',
    rule: '다이오드 품번의 일부나 용도로 검색하고 후보를 선택하세요. D1은 회로 안의 참조 번호여서 품번 대신 쓸 수 없습니다.',
    examples: '1N414 · schottky', placeholder: '예: 1N414',
  } : effectiveContext ? {
    description: '올린 넷리스트와 부품 정보·전체 핀 연결이 일치하는 공개 원본을 찾습니다. 참조 번호만 달라도 같은 회로면 표시합니다.',
    rule: '보드·프로젝트명이나 실제 포함 부품명의 키워드로 검색하세요. 전체 연결이 일치한 후보만 선택할 수 있습니다.',
    examples: 'ATtiny85 · ATtiny85 dev board AMS111', placeholder: '예: ATtiny85 또는 AMS111',
  } : {
    description: '제품·보드의 회로도를 참고용으로 찾습니다. 업로드 회로와 동일한 회로라는 뜻이 아닙니다.',
    rule: '제조사·제품군·모델명의 키워드로 찾고 후보의 정확한 제품·버전을 확인하세요. Pico와 Pico W, Teensy 4.0과 4.1은 다른 제품입니다.',
    examples: 'Raspberry Pi Pico · SparkFun Pro Micro v13', placeholder: '예: Raspberry Pi Pico',
  }
  const result = useQuery({ queryKey: ['external-schematic', effectiveContext?.projectId ?? 'reference', effectiveContext?.circuitVersion ?? '', effectiveContext?.threadId ?? '', searched, selectedSource, componentType], queryFn: ({ signal }) => findSchematic(searched, signal, selectedSource, effectiveContext, componentType === 'diode' ? 'diode' : undefined), enabled: searched !== '', retry: false, staleTime: 5 * 60_000,
    refetchOnWindowFocus: false, refetchOnReconnect: false, refetchOnMount: false })
  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!valid || result.isFetching) return
    if (term !== searched || selectedSource) { setShowImage(false); setSelectedSource(''); setSearched(term) }
    else if (result.isError || result.isStale) { setShowImage(false); void result.refetch() }
  }
  const received = searched ? result.data : undefined
  const data = received && (!effectiveContext || received.circuit_version === effectiveContext.circuitVersion) ? received : undefined
  const choices = data ? data.choices.length ? data.choices : [{ title: [data.model, data.source_file].filter(Boolean).join(' · '), source_url: data.source_url, source_type: data.source_type, revision: data.revision }] : []
  return <div className="sheets">
    {!disabled(result.error) && <form onSubmit={search}>
      <div className="field">
        <label className="field"><span>검색 대상</span><select className="input" value={componentType} aria-describedby="schematic-target-description" onChange={event => { setComponentType(event.target.value as '' | 'reference' | 'diode'); setSearched(''); setSelectedSource(''); setShowImage(false) }}><option value="">{context ? '업로드 회로 원본' : '제품·보드 회로도'}</option>{context && <option value="reference">제품·보드 참고 회로도</option>}<option value="diode">다이오드 사용 회로 (참고)</option></select></label>
        <details className="schematic-help">
          <summary>검색 대상 안내</summary>
          <p className="field-hint" id="schematic-target-description">{guidance.description}</p>
        </details>
      </div>
      <div className="field">
        <label className="field"><span>검색어</span><input className="input" value={text} onChange={event => { setText(event.target.value); setSearched(''); setSelectedSource(''); setShowImage(false) }} maxLength={maxLength} placeholder={guidance.placeholder} autoComplete="off" aria-describedby="schematic-query-rule schematic-query-examples schematic-query-accuracy schematic-rule" /></label>
        <details className="schematic-help">
          <summary>검색어 입력 안내·예시</summary>
          <div className="field">
            <p className="field-hint" id="schematic-query-rule">{guidance.rule}</p>
            <p className="field-hint" id="schematic-query-examples">예: {guidance.examples}</p>
            <p className="field-hint" id="schematic-query-accuracy">3자 이상 키워드는 앞부분으로도 검색합니다. 후보의 정확한 모델·품번을 확인하세요. 오타 자동 보정은 보장하지 않습니다.</p>
            <p className="field-hint" id="schematic-rule">2자 이상 {maxLength}자 이하 · URL 대신 이름·품번을 입력하세요.</p>
          </div>
        </details>
      </div>
      <div className="dialog-foot"><button className="btn btn-primary" disabled={!valid || result.isFetching}>{result.isFetching ? '찾는 중' : context && !effectiveContext ? '참고 회로도 찾기' : '원본 회로도 찾기'}</button></div>
    </form>}
    {result.isFetching && <div className="skeleton inset" role="status"><span className="sr-only">원본 회로도를 찾는 중입니다. 몇 초 걸릴 수 있습니다.</span><span className="skeleton-row" aria-hidden="true" /><span className="skeleton-row" aria-hidden="true" /></div>}
    {result.error && !result.isFetching && <p className="notice inset" role="alert" {...requestIdProps(result.error)}>{searchMessage(result.error as unknown as ApiError, componentType)}</p>}
    {received && !data && <p className="notice inset" role="alert">현재 회로 버전과의 일치를 확인하지 못해 도면을 표시하지 않습니다.</p>}
    {data && showImage && effectiveContext && <p className="inset">업로드 회로 v{effectiveContext.circuitVersion} · 부품·핀 연결 일치</p>}
    {data && showImage && effectiveContext && <p className="field-hint inset">도면의 참조 번호는 업로드 파일과 다를 수 있습니다. 부품 정보와 전체 핀 연결을 대조한 결과입니다.</p>}
    {data && <div className="inset schematic-choices" aria-label="검색된 회로도 후보">
      <p>검증된 회로도 후보 {choices.length}개 · 자료를 선택하면 도면과 출처를 표시합니다.</p>
      {choices.map(choice => <button className="btn" key={choice.source_url}
        aria-pressed={showImage && choice.source_url === data.source_url}
        onClick={() => { setShowImage(true); if (choice.source_url !== data.source_url) setSelectedSource(choice.source_url) }}
        disabled={result.isFetching}>
        {showImage && choice.source_url === data.source_url ? '현재 보는 자료: ' : '이 자료 보기: '}{choice.title} · {sourceLabel(choice.source_type)}
      </button>)}
    </div>}
    {data && showImage && data.images.map(image => <SchematicImage key={image.url} schematic={{ image_url: image.url, original_url: data.source_url, attribution: data.attribution, license: data.license,
      evidence_grade: data.evidence_grade, source_type: data.source_type,
      manufacturer: data.manufacturer, model: data.model, revision: data.revision,
      source_page_url: data.repository_url }}
      name={`${data.model || data.project || searched} 시트 ${image.sheet + 1}`} zoom={zoom} viewReset={viewReset} reload={() => void result.refetch()} />)}
  </div>
}
