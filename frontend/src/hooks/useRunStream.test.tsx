import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useRunStream } from './useRunStream'

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks(); vi.useRealTimers() })
const dto = { answer: '완료 답', status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: 'req-1' }
const sse = (...frames: [string, object][]) => new Response(frames.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join(''), { headers: { 'Content-Type': 'text/event-stream' } })

it('rejects files at the analysis boundary so netlists must be imported first', async () => {
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '첨부 확인', target_ref: 'D1', attachments: [new File(['memo'], 'notes.txt')] }) })
  expect(fetcher).not.toHaveBeenCalled()
  expect(result.current.state).toMatchObject({ status: 'failed', error: { code: 'UNSUPPORTED_ATTACHMENT' } })
})

it('uses the 120 second stream deadline and restores via GET when it aborts', async () => {
  const deadline = new AbortController()
  const timeout = vi.spyOn(AbortSignal, 'timeout').mockImplementation(ms => ms === 120_000 ? deadline.signal : new AbortController().signal)
  const fetcher = vi.fn((path: string, init: RequestInit = {}) => Promise.resolve(path.includes('/threads/')
    ? new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: run_started\ndata: {"run_id":"deadline-run"}\n\n'))
      init.signal?.addEventListener('abort', () => controller.error(init.signal?.reason), { once: true })
    } }))
    : Response.json({ id: 'deadline-run', result: dto })))
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  let done!: Promise<void>
  act(() => { done = result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  await waitFor(() => expect(result.current.state.status).toBe('running'))
  await act(async () => { deadline.abort(new DOMException('시험 수신 시간 초과', 'TimeoutError')); await done })
  expect(result.current.state.status).toBe('completed')
  expect(timeout.mock.calls.map(([ms]) => ms)).toEqual([120_000, 10_000])
  expect(fetcher.mock.calls.map(([path]) => path)).toEqual(['/api/threads/thread-1/runs', '/api/runs/deadline-run'])
})

it('retains the run ID after the 10 second recovery request deadline without resending', async () => {
  const deadline = new AbortController()
  vi.spyOn(AbortSignal, 'timeout').mockImplementation(ms => ms === 10_000 ? deadline.signal : new AbortController().signal)
  const fetcher = vi.fn((path: string, init: RequestInit = {}) => path.includes('/threads/')
    ? Promise.resolve(sse(['run_started', { run_id: 'read-deadline' }]))
    : new Promise<Response>((_, reject) => init.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true })))
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  let done!: Promise<void>
  act(() => { done = result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2))
  await act(async () => { deadline.abort(new DOMException('시험 조회 시간 초과', 'TimeoutError')); await done })
  expect(result.current.state).toMatchObject({ status: 'failed', runId: 'read-deadline' })
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('bounds recovery polling and allows checking status without a second analysis POST', async () => {
  vi.useFakeTimers()
  const fetcher = vi.fn((path: string) => Promise.resolve(path.includes('/threads/')
    ? sse(['run_started', { run_id: 'run-stuck' }])
    : Response.json({ id: 'run-stuck', thread_id: 'thread-1', result: { ...dto, status: 'running' } })))
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  let done: Promise<void>
  act(() => { done = result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  await act(async () => { await vi.advanceTimersByTimeAsync(35_000) })
  expect(result.current.state).toMatchObject({ status: 'failed', runId: 'run-stuck', error: { code: 'RUN_STATUS_PENDING' } })
  await done!
  expect(fetcher.mock.calls.filter(([path]) => path === '/api/runs/run-stuck')).toHaveLength(30)
  fetcher.mockImplementation(() => Promise.resolve(Response.json({ id: 'run-stuck', thread_id: 'thread-1', result: dto })))
  await act(async () => { await result.current.refresh('run-stuck') })
  expect(result.current.state.status).toBe('completed')
  expect(fetcher.mock.calls.filter(([path]) => path.includes('/threads/'))).toHaveLength(1)
})

it('restores the input form and its error after a rejected resume', async () => {
  const interrupt = { missing: ['v_in_max'], role_choices: [] }
  vi.stubGlobal('fetch', vi.fn((path: string) => Promise.resolve(path.endsWith('/resume')
    ? Response.json({ error: { code: 'VALIDATION_ERROR', message: '입력을 확인하세요.', request_id: 'req-input' } }, { status: 422 })
    : Response.json({ id: 'run-1', result: { ...dto, status: 'requires_input', interrupt } }))))
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.resume('run-1', { answers: { other: '12' } }) })
  expect(result.current.state).toMatchObject({ status: 'requires_input', runId: 'run-1', interrupt,
    error: { code: 'VALIDATION_ERROR', message: '입력을 확인하세요.' } })
})

it('polls after a broken stream until the saved result is completed', async () => {
  vi.useFakeTimers()
  let reads = 0
  const fetcher = vi.fn((path: string) => {
    if (path.includes('/threads/')) {
      let chunks = 0
      return Promise.resolve(new Response(new ReadableStream({ pull(controller) {
        if (chunks++ === 0) controller.enqueue(new TextEncoder().encode('event: run_started\ndata: {"run_id":"run-broken"}\n\n'))
        else controller.error(new TypeError('connection lost'))
      } })))
    }
    return Promise.resolve(Response.json({ id: 'run-broken', result: { ...dto, status: reads++ === 0 ? 'running' : 'completed' } }))
  })
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  let done: Promise<void>
  act(() => { done = result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); await done! })
  expect(result.current.state.status).toBe('completed')
  expect(reads).toBe(2)
  expect(fetcher.mock.calls.filter(([path]) => path.includes('/threads/'))).toHaveLength(1)
})

it('follows ordered events to a completed result', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(sse(['run_started', { run_id: 'run-1' }], ['status', { ...dto, status: 'running', stage: '문서 검색' }], ['completed', dto]))))
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  expect(result.current.state).toMatchObject({ status: 'completed', runId: 'run-1', result: { answer: '완료 답' } })
})

it('recovers a closed stream with GET without resubmitting the question', async () => {
  const fetcher = vi.fn((path: string) => path.startsWith('/api/threads/')
    ? Promise.resolve(sse(['run_started', { run_id: 'run-2' }]))
    : Promise.resolve(Response.json({ id: 'run-2', thread_id: 'thread-1', result: dto })))
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  await waitFor(() => expect(result.current.state.status).toBe('completed'))
  expect(fetcher.mock.calls.filter(([path]) => String(path).startsWith('/api/threads/'))).toHaveLength(1)
  expect(fetcher.mock.calls.filter(([path]) => String(path) === '/api/runs/run-2')).toHaveLength(1)
})

it('turns a malformed frame into a public failure', async () => {
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('event: run_started\ndata: not-json\n\n'))))
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  expect(result.current.state).toMatchObject({ status: 'failed', error: { code: 'STREAM_ERROR' } })
})

it('shows the server message of a failed frame', async () => {
  const error = { code: 'VALIDATION_ERROR', message: '기록한 데모 질문과 질문 · 사용 조건이 다릅니다.' }
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(sse(['run_started', { run_id: 'run-3' }], ['failed', { ...dto, status: 'failed', error }]))))
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '질문', target_ref: 'D1' }) })
  expect(result.current.state).toMatchObject({ status: 'failed', runId: 'run-3', error: { ...error, requestId: 'req-1' } })
})

it('rejects unsupported production attachments without a request or a paid run', async () => {
  vi.stubEnv('DEV', false)
  const fetcher = vi.fn()
  vi.stubGlobal('fetch', fetcher)
  const { result } = renderHook(() => useRunStream())
  await act(async () => { await result.current.start('thread-1', { question: '첨부 확인', target_ref: 'D1', attachments: [new File(['memo'], 'notes.txt')] }) })
  expect(fetcher).not.toHaveBeenCalled()
  expect(result.current.state).toMatchObject({ status: 'failed', error: { code: 'UNSUPPORTED_ATTACHMENT' } })
})
