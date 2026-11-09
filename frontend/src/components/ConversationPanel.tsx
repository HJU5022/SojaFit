import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createThread, listThreads } from '../api/conversations'
import { errorMessage } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import RunStatus from './RunStatus'
import InterruptForm from './InterruptForm'
import ProfileHints from './ProfileHints'

export default function ConversationPanel({ projectId, targetRef, onResult, onConditions }: {
  projectId: number
  targetRef: string
  onResult: (result: ReturnType<typeof useRunStream>['state']) => void
  onConditions?: (conditions: string) => void
}) {
  const client = useQueryClient()
  const threads = useQuery({ queryKey: ['threads', projectId], queryFn: ({ signal }) => listThreads(projectId, signal), retry: false, gcTime: 0 })
  const [threadId, setThreadId] = useState('')
  const [question, setQuestion] = useState('')
  const [conditions, setConditions] = useState('')
  const [creating, setCreating] = useState(false)
  const errorSummary = useRef<HTMLParagraphElement>(null)
  const run = useRunStream()
  useEffect(() => { setThreadId(threads.data?.[0]?.id ?? '') }, [threads.data])
  useEffect(() => { onResult(run.state) }, [onResult, run.state])
  useEffect(() => () => run.cancel(), [run.cancel])
  useEffect(() => { if (run.state.status === 'failed') errorSummary.current?.focus() }, [run.state])
  async function ensureThread() {
    if (threadId) return threadId
    setCreating(true)
    try {
      const created = await createThread(projectId)
      setThreadId(created.id)
      void client.invalidateQueries({ queryKey: ['threads', projectId] })
      return created.id
    } finally { setCreating(false) }
  }
  async function submit() {
    if (!question.trim() || !targetRef || run.state.status === 'running') return
    try {
      const id = await ensureThread()
      onConditions?.(conditions.trim())
      void run.start(id, { question: question.trim(), target_ref: targetRef, conditions: conditions.trim() })
    }
    catch (error) { onResult({ status: 'failed', error: error as never }) }
  }
  const busy = creating || run.state.status === 'running'
  const interruptState = run.state.status === 'requires_input' ? run.state : null
  return <section className="panel conversation-panel" aria-labelledby="conversation-heading"><h2 id="conversation-heading">D5 대화</h2>
    <RunStatus state={run.state} />
    {(run.state.status === 'completed' || run.state.status === 'refused') && <ProfileHints hints={run.state.result.profile_hints ?? []} />}
    <label htmlFor="d5-question">질문</label><textarea id="d5-question" rows={4} maxLength={4000} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} placeholder="예: D1을 SS34로 바꿔도 되나요?" />
    <label htmlFor="d5-conditions">사용 조건 (선택)</label><textarea id="d5-conditions" rows={2} maxLength={2000} value={conditions} disabled={busy} onChange={event => setConditions(event.target.value)} />
    <button disabled={busy || !targetRef || !question.trim()} onClick={() => void submit()}>D5에 질문하기</button>
    {!targetRef && <p>먼저 대상 부품을 선택하세요.</p>}
    {threads.error && <p role="alert">{errorMessage(threads.error)}</p>}
    {run.state.status === 'failed' && <p ref={errorSummary} role="alert" tabIndex={-1}>{errorMessage(run.state.error)}</p>}
    {interruptState && <InterruptForm interrupt={interruptState.interrupt} busy={false} onSubmit={(answers, role) => void run.resume(interruptState.runId, { answers, role })} />}
    <button className="secondary" disabled={!busy} onClick={run.cancel}>실행 취소</button>
  </section>
}
