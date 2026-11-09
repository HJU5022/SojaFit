import type { RunState } from '../hooks/useRunStream'

export default function RunStatus({ state }: { state: RunState }) {
  let text = '질문을 입력해 주세요.'
  if (state.status === 'running') text = `${state.stage} 진행 중`
  else if (state.status === 'requires_input') text = '추가 정보가 필요합니다.'
  else if (state.status === 'completed') text = '판정이 완료되었습니다.'
  else if (state.status === 'refused') text = '요청을 처리할 수 없습니다.'
  else if (state.status === 'failed') text = state.error.message
  return <p className={`run-status run-${state.status}`} aria-live="polite">{text}</p>
}
