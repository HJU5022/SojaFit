import type { RunState } from '../hooks/useRunStream'

export function ProcessingIcon({ stop = false }: { stop?: boolean }) {
  return <svg className="processing-icon" viewBox="0 0 24 24" aria-hidden="true">
    <g className="processing-ring"><circle className="processing-track" cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="9" strokeDasharray="14 43" strokeLinecap="round" /></g>
    {stop && <rect x="8" y="8" width="8" height="8" rx="1" />}
  </svg>
}

export default function RunStatus({ state }: { state: RunState }) {
  let text = '질문을 입력해 주세요.'
  if (state.status === 'running') text = `${state.stage} 진행 중`
  else if (state.status === 'requires_input') text = '추가 정보가 필요합니다.'
  // [왜] 완료는 판정 · 정격 · 역할 질문 모두에 온다. 거절은 답(답할 수 없는 질문)이고, 실패는 시스템 오류라 문구를 나눈다
  else if (state.status === 'completed') text = '분석이 끝났습니다.'
  else if (state.status === 'refused') text = '이 질문에는 답할 수 없어 거절했습니다.'
  else if (state.status === 'failed') text = `오류로 멈췄습니다. ${state.error.message}`
  return <p className={`run-status run-${state.status}`} aria-live="polite">{text}</p>
}
