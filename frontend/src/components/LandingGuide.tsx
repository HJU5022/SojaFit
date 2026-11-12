import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import AccessibleDialog from './AccessibleDialog'

type Crop = [number, number, number, number]
type Scene = { title: string; description: string; crop?: Crop }
type Step = { title: string; phase: string; x: number; y: number; path: number[]; description: string; image?: 'project' | 'question' | 'evidence'; crop?: Crop; scenes: Scene[] }
const steps: Step[] = [
  { title: '프로젝트 만들기', phase: '회로 준비', x: 2, y: 64, path: [], image: 'project', crop: [375, 140, 690, 270], description: '회로를 담을 프로젝트를 준비합니다.', scenes: [
    { title: '생성 창 열기', description: '현재 프로젝트 옆 +에서 새 프로젝트를 시작합니다.' },
    { title: '이름 작성', description: '회로나 검토 목적을 알아볼 수 있는 이름을 적습니다.', crop: [395, 300, 650, 110] },
  ] },
  { title: '넷리스트 첨부', phase: '회로 준비', x: 19, y: 64, path: [0], image: 'project', crop: [385, 600, 670, 250], description: 'KiCad 넷리스트를 선택해 회로 프로젝트를 만듭니다.', scenes: [
    { title: '파일 선택', description: 'KiCad에서 내보낸 .net 파일을 선택하세요.' },
    { title: '프로젝트 생성', description: '파일로 만들기를 누르세요. 업로드한 회로가 프로젝트에 연결됩니다.', crop: [385, 650, 670, 200] },
  ] },
  { title: '분석할 부품 선택', phase: '회로 준비', x: 19, y: 144, path: [0, 1], image: 'question', crop: [1080, 230, 360, 225], description: '교체를 검토할 부품과 주변 연결을 확인합니다.', scenes: [
    { title: '대상 선택', description: '현재 프로젝트에서 D1처럼 부품을 구분하는 이름을 확인하고 선택합니다.' },
    { title: '주변 회로 확인', description: '연결 개념도로 주변 부품과 배선을 살펴봅니다.', crop: [1080, 600, 360, 225] },
  ] },
  { title: '질문·조건 작성', phase: '질문', x: 39, y: 64, path: [0, 1, 2], image: 'question', crop: [225, 885, 850, 110], description: '바꾸려는 부품과 알고 있는 사용 조건을 함께 적습니다.', scenes: [
    { title: '질문 작성', description: '예: D1을 SS34로 바꿀 수 있나요?' },
    { title: '조건 추가', description: '예: 최대 입력 12 V, 부하 전류 1 A, 기판 수정 가능.' },
    { title: '질문 전송', description: '전송 버튼으로 질문과 조건을 보냅니다.' },
  ] },
  { title: '조건 보완', phase: '질문 · 필요한 경우', x: 39, y: 174, path: [0, 1, 2, 4], description: '에이전트가 추가 정보를 요청한 경우에만 조건을 보완합니다.', scenes: [
    { title: '요청 확인', description: '추가 입력 영역에서 어떤 값이나 역할 정보가 필요한지 확인합니다.' },
    { title: '정보 보완', description: '확인한 값을 입력해 같은 검토를 이어갑니다. 모르는 값은 추측해서 적지 마세요.' },
  ] },
  { title: '답변 확인', phase: '결과 검토', x: 61, y: 64, path: [0, 1, 2, 3], image: 'evidence', crop: [220, 240, 850, 531.25], description: '확인된 내용과 아직 확인하지 못한 내용을 함께 읽습니다.', scenes: [
    { title: '답변 읽기', description: '판정과 사용 조건, 남아 있는 제한을 살펴봅니다.' },
    { title: '상세 자료 열기', description: '답변의 후보 비교나 문서 근거로 이어서 확인합니다.', crop: [220, 400, 850, 531.25] },
  ] },
  { title: '후보 비교', phase: '결과 검토', x: 61, y: 158, path: [0, 1, 2, 3, 6], description: '답변에 후보가 있는 경우 부품별 판정과 제한을 비교합니다.', scenes: [
    { title: '후보 비교 열기', description: '답변의 후보 비교를 눌러 오른쪽 상세 영역을 엽니다.' },
    { title: '판정 확인', description: '각 후보에서 확인한 조건과 문서로 확인하지 못한 항목을 구분해 읽습니다.' },
  ] },
  { title: '문서 근거', phase: '결과 검토', x: 81, y: 158, path: [0, 1, 2, 3, 7], image: 'evidence', crop: [1080, 135, 360, 225], description: '답변이 인용한 문서와 사양 항목을 확인합니다.', scenes: [
    { title: '근거 열기', description: '답변의 인용 번호나 문서 근거 메뉴를 누릅니다.' },
    { title: '항목 확인', description: '판정에 사용한 사양과 제한을 살펴봅니다.', crop: [1080, 350, 360, 225] },
    { title: '위치 확인', description: '표시된 문서의 페이지와 항목을 확인합니다.', crop: [1080, 550, 360, 225] },
  ] },
  { title: '원문 확인', phase: '결과 검토', x: 81, y: 238, path: [0, 1, 2, 3, 7, 8], description: '근거에서 연결한 데이터시트 원문을 확인합니다.', scenes: [
    { title: '원문 열기', description: '문서 근거에 표시된 원문 링크를 엽니다.' },
    { title: '내용 대조', description: '인용한 페이지와 항목을 찾아 실제 문서 내용과 함께 검토합니다.' },
  ] },
]
const paths = ['M160 88H190', 'M260 112V144', 'M330 168H360V88H390', 'M530 88H610', 'M460 112V174', 'M530 198H570V88H610', 'M680 112V158', 'M750 88H880V158', 'M880 206V238']
type Position = { left: number; top: number; width: number; maxHeight: number; side: 'bottom' | 'top' | 'left' | 'right'; arrow: number }
const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(value, max))

export default function LandingGuide() {
  const [selected, setSelected] = useState<number | null>(null)
  const [scene, setScene] = useState(0)
  const [expanded, setExpanded] = useState(false)
  const [position, setPosition] = useState<Position>({ left: 12, top: 12, width: 460, maxHeight: 380, side: 'bottom', arrow: 24 })
  const stage = useRef<HTMLDivElement>(null), popup = useRef<HTMLDivElement>(null), closeButton = useRef<HTMLButtonElement>(null)
  const buttons = useRef<(HTMLButtonElement | null)[]>([])
  const step = selected === null ? null : steps[selected]
  const action = step?.scenes[scene]
  const crop = action?.crop ?? step?.crop
  const image = step?.image ? `/assets/landing-guide-${step.image}.png` : ''
  function close(restoreFocus = true) {
    setSelected(null)
    if (restoreFocus && selected !== null) buttons.current[selected]?.focus({ preventScroll: true })
  }
  function open(index: number) {
    const node = stage.current, rect = node?.getBoundingClientRect()
    if (rect && (rect.top < 96 || rect.bottom > window.innerHeight - 12)) node?.scrollIntoView?.({ block: 'center', behavior: 'instant' })
    setScene(0); setSelected(index)
  }
  useLayoutEffect(() => { if (selected !== null) closeButton.current?.focus({ preventScroll: true }) }, [selected])
  useLayoutEffect(() => {
    const area = stage.current, panel = popup.current, anchor = selected === null ? null : buttons.current[selected]
    if (!area || !panel || !anchor) return
    function place() {
      const bounds = area!.getBoundingClientRect(), target = anchor!.getBoundingClientRect()
      const areaWidth = area!.clientWidth, areaHeight = area!.clientHeight
      if (!areaWidth || !areaHeight) return
      const width = Math.min(460, areaWidth - 24), maxHeight = Math.max(80, Math.min(380, areaHeight - 24, window.innerHeight - 160))
      const height = Math.min(panel!.getBoundingClientRect().height, maxHeight)
      const x = target.left - bounds.left - area!.clientLeft, y = target.top - bounds.top - area!.clientTop
      const middleX = x + target.width / 2, middleY = y + target.height / 2
      let left = middleX - width / 2, top = y + target.height + 12, side: Position['side'] = 'bottom'
      if (top + height > areaHeight - 12) {
        if (y - height - 12 >= 12) { top = y - height - 12; side = 'top' }
        else if (x + target.width + width + 24 <= areaWidth) { left = x + target.width + 12; top = middleY - height / 2; side = 'right' }
        else if (x - width - 12 >= 12) { left = x - width - 12; top = middleY - height / 2; side = 'left' }
      }
      left = Math.round(clamp(left, 12, areaWidth - width - 12)); top = Math.round(clamp(top, 12, areaHeight - height - 12))
      const arrow = Math.round(side === 'bottom' || side === 'top' ? clamp(middleX - left, 18, width - 18) : clamp(middleY - top, 18, height - 18))
      const next = { left, top, width, maxHeight, side, arrow }
      setPosition(previous => Object.keys(next).every(key => previous[key as keyof Position] === next[key as keyof Position]) ? previous : next)
    }
    place()
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(place)
    observer?.observe(area); observer?.observe(panel)
    window.addEventListener('resize', place)
    return () => { observer?.disconnect(); window.removeEventListener('resize', place) }
  }, [selected, scene])
  useEffect(() => {
    if (selected === null || expanded) return
    function keydown(event: KeyboardEvent) { if (event.key === 'Escape') { event.preventDefault(); close() } }
    function outside(event: PointerEvent) {
      if (event.target instanceof Node && !popup.current?.contains(event.target) && !(event.target instanceof Element && event.target.closest('.landing-guide-node'))) close(false)
    }
    document.addEventListener('keydown', keydown); document.addEventListener('pointerdown', outside)
    return () => { document.removeEventListener('keydown', keydown); document.removeEventListener('pointerdown', outside) }
  }, [selected, expanded])
  return <div ref={stage} className="landing-guide-map" aria-label="사용 방법 지도">
    <svg className="landing-guide-connections" viewBox="0 0 1000 360" preserveAspectRatio="none" aria-hidden="true">{paths.map((path, index) => <path key={path} d={path} className={step?.path.includes(index) ? 'selected' : ''} strokeDasharray={index === 4 || index === 5 ? '4 4' : undefined} />)}</svg>
    <div className="landing-guide-phases" aria-hidden="true"><span>01 회로 준비</span><span>02 질문</span><span>03 결과 검토</span></div>
    <div className="landing-guide-nodes" role="group" aria-label="회로 검토 사용 흐름">{steps.map((item, index) => <button key={item.title} ref={node => { buttons.current[index] = node }} type="button" className="landing-guide-node" style={{ left: `${item.x}%`, top: item.y }} aria-expanded={selected === index} aria-controls={selected === index ? 'landing-guide-popup' : undefined} onClick={() => open(index)}>{item.title}</button>)}</div>
    <p className="landing-guide-legend">스텝을 누르면 과정을 볼 수 있습니다. 점선은 추가 정보가 필요한 경우입니다.</p>
    {step && action && <div ref={popup} id="landing-guide-popup" className="landing-guide-popup" data-side={position.side} role="dialog" aria-modal="false" aria-labelledby="landing-guide-title" style={{ left: position.left, top: position.top, width: position.width, maxHeight: position.maxHeight, '--guide-arrow': `${position.arrow}px` } as CSSProperties}>
      <header className="landing-guide-heading"><div><p>{step.phase}</p><h3 id="landing-guide-title">{step.title}</h3></div><button ref={closeButton} type="button" className="secondary" aria-label="과정 설명 닫기" onClick={() => close()}>×</button></header>
      <div className="landing-guide-body">
        <p className="landing-guide-description">{step.description}</p>
        <div className="landing-guide-scenes" role="group" aria-label="세부 과정">{step.scenes.map((item, index) => <button key={item.title} type="button" className="secondary" aria-pressed={scene === index} onClick={() => setScene(index)}>{index + 1} {item.title}</button>)}</div>
        <p className="landing-guide-instruction" aria-live="polite">{action.description}</p>
        {image && crop && <figure className="landing-guide-example"><button type="button" className="landing-guide-image-button" aria-label="예시 화면 크게 보기" onClick={() => setExpanded(true)}><span className="landing-guide-crop" style={{ aspectRatio: `${crop[2]} / ${crop[3]}` }}><img src={image} alt={`${step.title} 참고 화면`} width="1440" height="1000" style={{ width: `${1440 / crop[2] * 100}%`, left: `${-crop[0] / crop[2] * 100}%`, top: `${-crop[1] / crop[3] * 100}%` }} /></span></button><figcaption>예시 데이터 · 실제 분석 결과가 아닙니다. 이미지를 누르면 전체 화면을 볼 수 있습니다.</figcaption></figure>}
      </div>
    </div>}
    {expanded && step && image && <AccessibleDialog title={`${step.title} 예시 화면`} className="landing-image-dialog" onClose={() => setExpanded(false)}><p>기존 예시 캡처입니다. 가로·세로로 이동해 확인하세요.</p><div className="landing-image-scroll" tabIndex={0} role="region" aria-label={`${step.title} 확대 화면`}><img src={image} alt={`${step.title} 전체 참고 화면`} width="1440" height="1000" /></div></AccessibleDialog>}
  </div>
}
