import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createThread, listDemoQuestions, listThreads } from '../api/conversations'
import type { DemoQuestionDto, RoleLabel } from '../api/conversations'
import { errorMessage } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import RunStatus from './RunStatus'
import InterruptForm from './InterruptForm'
import ProfileHints from './ProfileHints'

export default function ConversationPanel({ projectId, demoId = null, targetRef, roleLabels = [], onResult, onConditions }: {
  projectId: number
  demoId?: string | null
  targetRef: string
  roleLabels?: RoleLabel[]
  onResult: (result: ReturnType<typeof useRunStream>['state']) => void
  onConditions?: (conditions: string) => void
}) {
  const client = useQueryClient()
  const threads = useQuery({ queryKey: ['threads', projectId], queryFn: ({ signal }) => listThreads(projectId, signal), retry: false, gcTime: 0 })
  const [threadId, setThreadId] = useState('')
  const [question, setQuestion] = useState('')
  const [conditions, setConditions] = useState('')
  const [creating, setCreating] = useState(false)
  // 키 없는 데모면 이 데모 회로의 기록 질문. 데모 모드가 아니면 목록이 404라 버튼이 없다
  const demoQuestions = useQuery({ queryKey: ['demo-questions'], queryFn: ({ signal }) => listDemoQuestions(signal), retry: false, gcTime: 0, enabled: demoId !== null })
  const recorded = Array.isArray(demoQuestions.data) ? demoQuestions.data.filter(item => item.demo_id === demoId) : []
  const [demoItem, setDemoItem] = useState<DemoQuestionDto | null>(null)
  const errorSummary = useRef<HTMLParagraphElement>(null)
  const run = useRunStream()
  useEffect(() => { setThreadId(threads.data?.[0]?.id ?? '') }, [threads.data])
  useEffect(() => { onResult(run.state) }, [onResult, run.state])
  useEffect(() => () => run.cancel(), [run.cancel])
  useEffect(() => { if (run.state.status === 'failed') errorSummary.current?.focus() }, [run.state])
  async function ensureThread(fresh = false) {
    if (threadId && !fresh) return threadId
    setCreating(true)
    try {
      const created = await createThread(projectId)
      setThreadId(created.id)
      void client.invalidateQueries({ queryKey: ['threads', projectId] })
      return created.id
    } finally { setCreating(false) }
  }
  async function submit(text = question.trim(), extra = conditions.trim(), fresh = false) {
    if (!text || !targetRef || run.state.status === 'running') return
    try {
      const id = await ensureThread(fresh)
      onConditions?.(extra)
      void run.start(id, { question: text, target_ref: targetRef, conditions: extra })
    }
    catch (error) { onResult({ status: 'failed', error: error as never }) }
  }
  function askRecorded(item: DemoQuestionDto) {
    // [왜] 기록은 새 대화의 첫 질문을 글자 그대로 보낼 때만 재생된다. 새 대화를 만들고 다듬지(trim) 않고 보낸다
    setQuestion(item.question); setConditions(item.conditions); setDemoItem(item)
    void submit(item.question, item.conditions, true)
  }
  const busy = creating || run.state.status === 'running'
  const interruptState = run.state.status === 'requires_input' ? run.state : null
  const forTarget = recorded.filter(item => item.target === targetRef)
  const resume = demoItem?.resume
  return <section className="panel conversation-panel" aria-labelledby="conversation-heading"><h2 id="conversation-heading">대화</h2>
    <RunStatus state={run.state} />
    {(run.state.status === 'completed' || run.state.status === 'refused') && <ProfileHints hints={run.state.result.profile_hints ?? []} />}
    {recorded.length > 0 && <div className="demo-questions" role="group" aria-label="데모 질문">
      <p>키 없는 데모는 기록한 질문만 재생합니다. 누르면 새 대화로 보냅니다.</p>
      {forTarget.map(item => <button key={item.id} className="secondary" disabled={busy} onClick={() => askRecorded(item)}>{item.question}</button>)}
      {forTarget.length === 0 && <p>데모 질문이 있는 대상 부품: {[...new Set(recorded.map(item => item.target))].join(', ')}</p>}
    </div>}
    <label htmlFor="d5-question">질문</label><textarea id="d5-question" rows={4} maxLength={4000} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} placeholder="예: D1을 SS34로 바꿔도 되나요?" />
    <label htmlFor="d5-conditions">사용 조건 (선택)</label><textarea id="d5-conditions" rows={2} maxLength={2000} value={conditions} disabled={busy} onChange={event => setConditions(event.target.value)} />
    <button disabled={busy || !targetRef || !question.trim()} onClick={() => { setDemoItem(null); void submit() }}>질문하기</button>
    {!targetRef && <p>먼저 대상 부품을 선택하세요.</p>}
    {threads.error && <p role="alert">{errorMessage(threads.error)}</p>}
    {run.state.status === 'failed' && <p ref={errorSummary} role="alert" tabIndex={-1}>{errorMessage(run.state.error)}</p>}
    {interruptState && (resume
      // [왜] 기록 재생은 기록할 때 보낸 답 · 역할 그대로여야 이어진다. 빈 답('모름')은 입력 폼으로 보낼 수 없어 버튼 하나로 보낸다
      ? <div className="interrupt-form"><h3>추가 정보</h3><p>{interruptState.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</p>
        <p>기록한 답: {Object.entries(resume.answers).map(([key, value]) => `${key}=${value}`).join(', ') || '모름'} · 역할: {resume.role || '없음'}</p>
        <button onClick={() => void run.resume(interruptState.runId, { answers: resume.answers, role: resume.role || undefined })}>기록한 답으로 계속하기</button></div>
      : <InterruptForm interrupt={interruptState.interrupt} roleLabels={roleLabels} busy={false} onSubmit={(answers, role) => void run.resume(interruptState.runId, { answers, role })} />)}
    <button className="secondary" disabled={!busy} onClick={run.cancel}>실행 취소</button>
  </section>
}
