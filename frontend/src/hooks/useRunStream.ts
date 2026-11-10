import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiError } from '../api/client'
import { getRun, openRunStream, readEventStream } from '../api/conversations'
import type { InterruptDto, ResultDto, StreamEvent } from '../api/conversations'

export type RunState =
  | { status: 'idle' }
  | { status: 'running'; runId: string; stage: string }
  | { status: 'requires_input'; runId: string; interrupt: InterruptDto }
  | { status: 'completed' | 'refused'; runId: string; result: ResultDto }
  | { status: 'failed'; runId?: string; error: ApiError }

const wait = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const timer = window.setTimeout(resolve, ms)
  signal.addEventListener('abort', () => { window.clearTimeout(timer); reject(signal.reason) }, { once: true })
})

function publicError(error: unknown): ApiError {
  const value = error as Partial<ApiError> | null
  return value?.message ? { code: value.code ?? 'STREAM_ERROR', message: value.message, requestId: value.requestId ?? '' }
    : { code: 'STREAM_ERROR', message: '실행 연결이 종료되었습니다.', requestId: '' }
}

export function useRunStream() {
  const [state, setState] = useState<RunState>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(async (path: string, body: unknown) => {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    let runId = ''
    let terminal = false
    try {
      const response = await openRunStream(path, body, active.signal)
      await readEventStream(response, ({ event, data }: StreamEvent) => {
        if (event === 'run_started') { runId = typeof data.run_id === 'string' ? data.run_id : ''; setState({ status: 'running', runId, stage: '입력 확인' }); return }
        if (event === 'status') { setState({ status: 'running', runId, stage: typeof data.stage === 'string' ? data.stage : '결과 정리' }); return }
        if (event === 'requires_input') { terminal = true; const result = data as unknown as ResultDto; setState({ status: 'requires_input', runId, interrupt: result.interrupt ?? {} }); return }
        terminal = true
        const result = data as unknown as ResultDto
        if (event === 'completed' || event === 'refused') setState({ status: event, runId, result })
        else {
          // [왜] 서버가 정한 공통 오류 문구(데모 질문 422, 기록 재생 실패 503 등)가 있으면 그대로 보인다
          const error = (data as { error?: { code?: string; message?: string } }).error
          setState({ status: 'failed', runId, error: { code: error?.code ?? 'RUN_FAILED', message: error?.message ?? '실행을 완료하지 못했습니다.', requestId: result.request_id ?? '' } })
        }
      }, active.signal)
      if (!terminal && runId) {
        let recovered = await getRun(runId, active.signal)
        while (recovered.result.status === 'running') { await wait(1000, active.signal); recovered = await getRun(runId, active.signal) }
        if (recovered.result.status === 'requires_input') setState({ status: 'requires_input', runId, interrupt: recovered.result.interrupt })
        else if (recovered.result.status === 'completed' || recovered.result.status === 'refused') setState({ status: recovered.result.status, runId, result: recovered.result })
        else setState({ status: 'failed', runId, error: { code: 'RUN_FAILED', message: '실행을 완료하지 못했습니다.', requestId: recovered.result.request_id } })
      }
    } catch (error) {
      if (active.signal.aborted) return
      if (runId) {
        try {
          const recovered = await getRun(runId, active.signal)
          if (recovered.result.status === 'completed' || recovered.result.status === 'refused') { setState({ status: recovered.result.status, runId, result: recovered.result }); return }
          if (recovered.result.status === 'requires_input') { setState({ status: 'requires_input', runId, interrupt: recovered.result.interrupt }); return }
        } catch { /* 공개 오류는 아래 하나로 정규화한다. */ }
      }
      setState({ status: 'failed', runId: runId || undefined, error: publicError(error) })
    }
  }, [])
  const cancel = useCallback(() => controller.current?.abort(), [])
  const reset = useCallback(() => { controller.current?.abort(); setState({ status: 'idle' }) }, [])
  return {
    state,
    start: (threadId: string, body: { question: string; target_ref: string; conditions?: string }) => run(`/api/threads/${threadId}/runs`, body),
    resume: (runId: string, body: { answers: Record<string, string>; role?: string }) => run(`/api/runs/${runId}/resume`, body),
    cancel,
    reset,
  }
}
