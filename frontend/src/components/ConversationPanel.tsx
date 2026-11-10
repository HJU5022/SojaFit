import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createThread, listDemoQuestions, listThreads } from '../api/conversations'
import type { DemoQuestionDto, RoleLabel } from '../api/conversations'
import { errorMessage } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import RunStatus from './RunStatus'
import InterruptForm from './InterruptForm'
import ProfileHints from './ProfileHints'

export default function ConversationPanel({ projectId, demoId = null, targetRef, roleLabels = [], initialQuestion = '', initialConditions = '', onResult, onConditions, onShowEvidence, onShowJudgement }: {
  projectId: number
  demoId?: string | null
  targetRef: string
  roleLabels?: RoleLabel[]
  initialQuestion?: string
  initialConditions?: string
  onResult: (result: ReturnType<typeof useRunStream>['state']) => void
  onConditions?: (conditions: string) => void
  onShowEvidence?: () => void
  onShowJudgement?: () => void
}) {
  const client = useQueryClient()
  const threads = useQuery({ queryKey: ['threads', projectId], queryFn: ({ signal }) => listThreads(projectId, signal), retry: false, gcTime: 0 })
  const [threadId, setThreadId] = useState('')
  const [question, setQuestion] = useState(initialQuestion)
  const [conditions, setConditions] = useState(initialConditions)
  const [submitted, setSubmitted] = useState<{ question: string; conditions: string } | null>(null)
  const [creating, setCreating] = useState(false)
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
      setSubmitted({ question: text, conditions: extra })
      void run.start(id, { question: text, target_ref: targetRef, conditions: extra })
    } catch (error) { onResult({ status: 'failed', error: error as never }) }
  }
  function askRecorded(item: DemoQuestionDto) {
    setQuestion(item.question); setConditions(item.conditions); setDemoItem(item)
    void submit(item.question, item.conditions, true)
  }
  const busy = creating || run.state.status === 'running'
  const interruptState = run.state.status === 'requires_input' ? run.state : null
  const forTarget = recorded.filter(item => item.target === targetRef)
  const resume = demoItem?.resume
  return <section className="conversation-panel" aria-labelledby="conversation-heading"><div className="conversation-title"><div><span className="eyebrow">분석 대화</span><h2 id="conversation-heading">대체 가능성 분석 흐름</h2></div><span className="target-badge">{targetRef || '대상 미선택'}</span></div>
    <div className="conversation-stream" aria-live="polite">
      {recorded.length > 0 && <div className="demo-questions" role="group" aria-label="데모 질문"><p>키 없는 데모는 기록한 질문만 재생합니다. 누르면 새 대화로 보냅니다.</p>
        {forTarget.map(item => <button key={item.id} className="secondary" disabled={busy} onClick={() => askRecorded(item)}>{item.question}</button>)}
        {forTarget.length === 0 && <p>데모 질문이 있는 대상 부품: {[...new Set(recorded.map(item => item.target))].join(', ')}</p>}</div>}
      {!submitted && <article className="conversation-card input-card"><span className="card-kicker">회로 입력 확인</span><h3>{targetRef ? `${targetRef} 분석 준비` : '대상 부품을 선택하세요'}</h3><p>{targetRef ? '질문과 실제 사용 조건을 입력하면 대체 가능성 분석을 시작합니다.' : '회로에서 교체할 부품을 선택하세요.'}</p></article>}
      {submitted && <><article className="conversation-card user-card"><span className="card-kicker">사용자 질문</span><h3>{submitted.question}</h3><p>{submitted.conditions || '사용 조건 정보 필요'}</p></article><article className={`conversation-card status-card status-${run.state.status}`}><span className="card-kicker">분석 상태</span><RunStatus state={run.state} /></article></>}
      {interruptState && <article className="conversation-card interrupt-card"><span className="card-kicker">추가 정보 요청</span>{resume
        ? <div className="interrupt-form"><h3>추가 정보</h3><p>{interruptState.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</p><p>기록한 답: {Object.entries(resume.answers).map(([key, value]) => `${key}=${value}`).join(', ') || '모름'} · 역할: {resume.role || '없음'}</p><button onClick={() => void run.resume(interruptState.runId, { answers: resume.answers, role: resume.role || undefined })}>기록한 답으로 계속하기</button></div>
        : <InterruptForm interrupt={interruptState.interrupt} roleLabels={roleLabels} busy={false} onSubmit={(answers, role) => void run.resume(interruptState.runId, { answers, role })} />}</article>}
      {(run.state.status === 'completed' || run.state.status === 'refused') && <article className={`conversation-card final-card status-${run.state.status}`}><span className="card-kicker">{run.state.status === 'completed' ? '최종 답변' : '거절 또는 확인 불가'}</span><p>{run.state.result.answer || run.state.result.refusal || '표시할 답변이 없습니다.'}</p><ProfileHints hints={run.state.result.profile_hints ?? []} />{run.state.status === 'completed' && <div className="composer-actions"><button className="secondary" onClick={() => onShowEvidence?.()}>근거 보기</button><button className="secondary" onClick={() => onShowJudgement?.()}>후보 비교 결과 보기</button></div>}</article>}
      {threads.error && <p role="alert">{errorMessage(threads.error)}</p>}
      {run.state.status === 'failed' && <p ref={errorSummary} role="alert" tabIndex={-1}>{errorMessage(run.state.error)}</p>}
    </div>
    <div className="composer"><div className="composer-context"><strong>대상 {targetRef || '미선택'}</strong><span>{busy ? '분석 중에는 중복 전송할 수 없습니다.' : '질문과 확인된 조건만 전송합니다.'}</span></div>
      <label htmlFor="d5-question">질문</label><textarea id="d5-question" rows={3} maxLength={4000} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} placeholder="예: D1을 SS34로 바꿔도 되나요?" />
      <label htmlFor="d5-conditions">사용 조건 (선택)</label><textarea id="d5-conditions" rows={2} maxLength={2000} value={conditions} disabled={busy} onChange={event => setConditions(event.target.value)} />
      <div className="composer-actions"><button disabled={busy || !targetRef || !question.trim()} onClick={() => { setDemoItem(null); void submit() }}>{run.state.status === 'failed' && submitted ? '다시 분석하기' : '분석하기'}</button><button className="secondary" disabled={!busy} onClick={run.cancel}>분석 취소</button></div>
      {!targetRef && <p>먼저 대상 부품을 선택하세요.</p>}</div>
  </section>
}
