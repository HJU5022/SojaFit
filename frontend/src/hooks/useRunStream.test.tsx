import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useRunStream } from './useRunStream'

afterEach(() => vi.unstubAllGlobals())
const dto = { answer: '완료 답', status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: 'req-1' }
const sse = (...frames: [string, object][]) => new Response(frames.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join(''), { headers: { 'Content-Type': 'text/event-stream' } })

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
