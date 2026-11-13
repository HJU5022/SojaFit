import { useCallback, useEffect, useRef, useState } from 'react'
import type { ApiError } from '../api/client'
import { getRun, recoverRun, openRunStream, readEventStream } from '../api/conversations'
import type { InterruptDto, ResultDto, StreamEvent } from '../api/conversations'

export type RunState =
  | { status: 'idle' }
  | { status: 'running'; runId: string; stage: string }
  | { status: 'requires_input'; runId: string; interrupt: InterruptDto; error?: ApiError }
  | { status: 'completed' | 'refused'; runId: string; result: ResultDto }
  | { status: 'failed'; runId?: string; error: ApiError }

const wait = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  signal.throwIfAborted()
  const abort = () => { window.clearTimeout(timer); reject(signal.reason) }
  const timer = window.setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, ms)
  signal.addEventListener('abort', abort, { once: true })
})

function restored(runId: string, result: ResultDto, error?: ApiError): RunState {
  if (result.status === 'requires_input') return { status: 'requires_input', runId, interrupt: result.interrupt, error }
  if (result.status === 'completed' || result.status === 'refused') return { status: result.status, runId, result }
  return { status: 'failed', runId, error: { code: 'RUN_FAILED', message: '실행을 완료하지 못했습니다. 새 대화에서 시작해 주세요.', requestId: result.request_id } }
}

function pending(requestId = ''): ApiError {
  return { code: 'RUN_STATUS_PENDING', message: '아직 실행 상태를 확정할 수 없습니다. 실행 상태를 다시 확인해 주세요. 분석은 자동으로 재전송하지 않습니다.', requestId }
}

const requestSignal = (signal: AbortSignal) => AbortSignal.any([signal, AbortSignal.timeout(10_000)])

async function recover(runId: string, signal: AbortSignal, error?: ApiError): Promise<RunState> {
  for (let attempt = 0; attempt < 30; attempt++) {
    const run = await getRun(runId, requestSignal(signal))
    signal.throwIfAborted()
    if (run.result.status !== 'running') return restored(runId, run.result, error)
    if (attempt < 29) await wait(1000, signal)
  }
  const run = await recoverRun(runId, requestSignal(signal))
  signal.throwIfAborted()
  if (run.result.status !== 'running') return restored(runId, run.result, error)
  throw pending(run.result.request_id)
}

function publicError(error: unknown): ApiError {
  const value = error as Partial<ApiError> | null
  return value?.message ? { code: value.code ?? 'STREAM_ERROR', message: value.message, requestId: value.requestId ?? '' }
    : { code: 'STREAM_ERROR', message: '실행 연결이 종료되었습니다.', requestId: '' }
}

export function useRunStream() {
  const [state, setState] = useState<RunState>({ status: 'idle' })
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])

  const run = useCallback(async (path: string, body: unknown, existingRunId = '') => {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    let runId = existingRunId
    let terminal = false
    let failure: unknown
    try {
      const signal = AbortSignal.any([active.signal, AbortSignal.timeout(120_000)])
      const response = await openRunStream(path, body, signal)
      await readEventStream(response, ({ event, data }: StreamEvent) => {
        if (event === 'run_started') { runId = typeof data.run_id === 'string' ? data.run_id : ''; setState({ status: 'running', runId, stage: '입력 확인' }); return }
        if (event === 'status') { setState({ status: 'running', runId, stage: typeof data.stage === 'string' ? data.stage : '결과 정리' }); return }
        if (event === 'requires_input') {
          terminal = true
          const result = data as unknown as ResultDto
          const error = data.error as { code: string; message: string } | undefined
          setState({ status: 'requires_input', runId, interrupt: result.interrupt ?? {}, error: error ? { ...error, requestId: result.request_id } : undefined })
          return
        }
        terminal = true
        const result = data as unknown as ResultDto
        if (event === 'completed' || event === 'refused') setState({ status: event, runId, result })
        else {
          // [왜] 서버가 정한 공통 오류 문구(데모 질문 422, 기록 재생 실패 503 등)가 있으면 그대로 보인다
          const error = (data as { error?: { code?: string; message?: string } }).error
          setState({ status: 'failed', runId, error: { code: error?.code ?? 'RUN_FAILED', message: error?.message ?? '실행을 완료하지 못했습니다.', requestId: result.request_id ?? '' } })
        }
      }, signal)
    } catch (error) { failure = error }
    if (active.signal.aborted || terminal) return
    if (runId) {
      try {
        const next = await recover(runId, active.signal, failure ? publicError(failure) : undefined)
        if (!active.signal.aborted) setState(next)
        return
      } catch (error) { failure = error }
    }
    if (!active.signal.aborted) setState({ status: 'failed', runId: runId || undefined, error: publicError(failure) })
  }, [])
  const refresh = useCallback(async (runId: string) => {
    controller.current?.abort()
    const active = new AbortController()
    controller.current = active
    try {
      const run = await recoverRun(runId, requestSignal(active.signal))
      if (!active.signal.aborted) setState(run.result.status === 'running'
        ? { status: 'failed', runId, error: pending(run.result.request_id) } : restored(runId, run.result))
    } catch (error) {
      if (!active.signal.aborted) setState({ status: 'failed', runId, error: publicError(error) })
    }
  }, [])
  const cancel = useCallback(() => controller.current?.abort(), [])
  const reset = useCallback(() => { controller.current?.abort(); setState({ status: 'idle' }) }, [])
  return {
    state,
    start: (threadId: string, body: { question: string; target_ref: string; conditions?: string; attachments?: File[] }) => {
      if (body.attachments?.length) {
        setState({ status: 'failed', error: { code: 'UNSUPPORTED_ATTACHMENT', message: '넷리스트를 프로젝트에 먼저 반영한 뒤 질문을 보내 주세요.', requestId: '' } })
        return Promise.resolve()
      }
      return run(`/api/threads/${threadId}/runs`, body)
    },
    resume: (runId: string, body: { answers: Record<string, string>; role?: string }) => run(`/api/runs/${runId}/resume`, body, runId),
    refresh,
    cancel,
    reset,
  }
}
