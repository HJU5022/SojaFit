import type { ContextNet } from '../lib/circuit'

const ROW = 46
const W = 424
// 1px 선이 화소 경계에 걸쳐 번지지 않게 모든 좌표를 화소 가운데(.5)에 맞춘다.
const px = (value: number) => Math.round(value) + 0.5

// 연결 줄은 동작이 없으므로 초점을 받지 않는다. 설명은 그림 전체의 aria-label에 있다.
export default function ContextDiagram({ targetRef, targetValue, nets }: { targetRef: string; targetValue: string; nets: ContextNet[] }) {
  let row = 0
  const laid = nets.map((net) => {
    const count = Math.max(1, net.neighbors.length + (net.more ? 1 : 0))
    const ys = Array.from({ length: count }, (_, index) => px(30 + (row + index) * ROW))
    row += count
    return { ...net, ys, y: px((ys[0] + ys[ys.length - 1]) / 2) }
  })
  const height = Math.max(76, row * ROW + 14)
  const targetY = px(laid.length ? laid.reduce((sum, net) => sum + net.y, 0) / laid.length : height / 2)
  if (!laid.length) return <p className="diagram-empty">이 부품에 연결된 넷이 없습니다. 부품 고르기에서 다른 부품을 선택해 주세요.</p>
  const diode = /^D\d/i.test(targetRef) && !/led/i.test(targetValue)
  const textX = diode ? 58 : 20
  const limit = diode ? 9 : 13
  // 직각 배선: 대상 핀에서 나와 세로 모선을 타고 각 넷으로 간다.
  const elbow = (x1: number, y1: number, x2: number, y2: number, bend: number) => `M${x1} ${y1} H${bend} V${y2} H${x2}`
  const exit = (y: number) => targetY + (y < targetY ? -8 : y > targetY ? 8 : 0)
  return <svg className="diagram" width={W} height={height} viewBox={`0 0 ${W} ${height}`} role="img"
    aria-label={`${targetRef} 연결 개념도. ${laid.map(net => `${net.pin} 핀은 ${net.name} 넷으로 ${net.neighbors.map(item => item.ref).join(', ') || '다른 부품 없이'} 연결`).join('. ')}`}>
    {laid.map(net => <g className="diagram-net" key={net.name}>
      <title>{`핀 ${net.pin}, 넷 ${net.name}`}</title>
      <path className="diagram-wire" d={elbow(118.5, exit(net.y), 292.5, net.y, 142.5)} />
      {net.ys.map((y, index) => <path className="diagram-wire" key={y} d={elbow(262.5, net.y, 292.5, y, 276.5)} strokeDasharray={index >= net.neighbors.length ? '2 3' : undefined} />)}
      <circle className="diagram-node" cx={142.5} cy={net.y} r={2.5} />
      <text className="diagram-pill-text" x={150} y={net.y - 7}>{net.name.length > 16 ? `${net.name.slice(0, 15)}…` : net.name}</text>
      <text className="diagram-pin" x={123} y={exit(net.y) + (net.y < targetY ? -5 : 12)}>{net.pin.length > 4 ? `${net.pin.slice(0, 3)}…` : net.pin}</text>
      {net.neighbors.map((part, index) => <g key={part.ref}>
        <title>{`${part.ref}, 값 ${part.value}`}</title>
        <rect className="diagram-part" x={292.5} y={net.ys[index] - 15} width={124} height={30} rx={4} />
        <text className="diagram-ref" x={302} y={net.ys[index] + 4}>{part.ref}</text>
        <text className="diagram-value" x={408} y={net.ys[index] + 4} textAnchor="end">{part.value.length > 9 ? `${part.value.slice(0, 8)}…` : part.value}</text>
      </g>)}
      {net.more > 0 && <text className="diagram-more" x={302} y={net.ys[net.ys.length - 1] + 4}>외 {net.more}개</text>}
    </g>)}
    <rect className="diagram-target" x={8.5} y={targetY - 30} width={110} height={60} rx={4} />
    {/* 범위 밖 부품을 다이오드로 오해하지 않도록 기호를 제한한다. */}
    {diode && <path className="diagram-symbol" d={`M24.5 ${targetY - 9} V${targetY + 9} L40.5 ${targetY} Z M40.5 ${targetY - 9} V${targetY + 9} M14 ${targetY} H24.5 M40.5 ${targetY} H50`} />}
    <text className="diagram-target-ref" x={textX} y={targetY - 3}>{targetRef}</text>
    <text className="diagram-target-value" x={textX} y={targetY + 13}>{targetValue.length > limit ? `${targetValue.slice(0, limit - 1)}…` : targetValue}</text>
  </svg>
}
