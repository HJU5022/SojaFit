import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createThread, getRun, recoverRun, getThread, listDemoQuestions } from '../api/conversations'
import type { DemoQuestionDto, ResultDto, RoleLabel } from '../api/conversations'
import { errorMessage } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import RunStatus, { ProcessingIcon } from './RunStatus'
import InterruptForm from './InterruptForm'
import ProfileHints from './ProfileHints'
import SafeMarkdown from './SafeMarkdown'
import type { RunState } from '../hooks/useRunStream'
import { approvableCandidatesOf, candidatesOf } from './circuitContext'

function ResultMenu({ result, onShowActivity, onShowJudgement, onShowEvidence, onShowActions }: {
  result?: ResultDto
  onShowActivity?: () => void; onShowJudgement?: () => void; onShowEvidence?: () => void; onShowActions?: () => void
}) {
  if (!result || (result.status !== 'completed' && result.status !== 'refused')) return null
  const completed = result.status === 'completed'
  return <div className="conversation-result-menu" role="group" aria-label="분석 결과 메뉴">
    <button className="secondary" onClick={onShowActivity}>분석 현황</button>
    {completed && candidatesOf(result.judgement).length > 0 && <button className="secondary" onClick={onShowJudgement}>후보 비교</button>}
    {(result.evidence?.length ?? 0) > 0 && <button className="secondary" onClick={onShowEvidence}>문서 근거</button>}
    {completed && approvableCandidatesOf(result.judgement).length > 0 && <button className="secondary" onClick={onShowActions}>승인·견적</button>}
  </div>
}

export function SavedConversationPanel({ projectId, threadId, onRestore, onShowActivity, onShowJudgement, onShowEvidence, onShowActions }: {
  projectId: number; threadId: string; onRestore: (target: string, state: RunState) => void
  onShowActivity: () => void; onShowJudgement: () => void; onShowEvidence: () => void; onShowActions: () => void
}) {
  const client = useQueryClient()
  const [selectedRunId, setSelectedRunId] = useState('')
  const history = useInfiniteQuery({ queryKey: ['thread-history', projectId, threadId], initialPageParam: undefined as number | undefined,
    queryFn: async ({ signal, pageParam }) => {
      const detail = await getThread(threadId, signal, pageParam)
      if (detail.id !== threadId || detail.project_id !== projectId) throw new Error('선택한 프로젝트의 대화가 아닙니다.')
      return detail
    }, getNextPageParam: page => page.next_before_message_id ?? undefined, retry: false, gcTime: 0, refetchOnWindowFocus: false })
  const first = history.error ? undefined : history.data?.pages[0]
  const messages = [...new Map((first ? history.data?.pages.flatMap(page => page.messages) ?? [] : []).map(message => [message.id, message])).values()].sort((a, b) => a.id - b.id)
  const runId = selectedRunId || first?.latest_run?.id || ''
  const run = useQuery({ queryKey: ['saved-run', projectId, threadId, runId], enabled: !!first && !!runId,
    queryFn: async ({ signal }) => {
      const value = await getRun(runId, AbortSignal.any([signal, AbortSignal.timeout(10_000)]))
      if (value.id !== runId || value.thread_id !== threadId) throw new Error('선택한 대화의 분석 결과가 아닙니다.')
      const messageId = selectedRunId ? messages.find(message => message.run_id === runId && message.role === 'assistant')?.id : first?.latest_run?.message_id
      if (messageId != null && value.message_id !== messageId) throw new Error('선택한 메시지의 분석 결과가 아닙니다.')
      return value
    }, retry: false, gcTime: 0, refetchOnWindowFocus: false })
  useEffect(() => {
    let state: RunState = { status: 'idle' }
    if (run.data && !run.error && first) {
      const { id, result } = run.data
      if (result.status === 'completed' || result.status === 'refused') state = { status: result.status, runId: id, result }
      else if (result.status === 'requires_input') state = { status: 'requires_input', runId: id, interrupt: result.interrupt }
      else if (result.status === 'running') state = { status: 'running', runId: id, stage: result.stage || '저장된 실행 상태' }
      else state = { status: 'failed', runId: id, error: { code: 'RUN_FAILED', message: '저장된 분석이 실패 상태입니다.', requestId: run.data.result.request_id ?? '' } }
    }
    onRestore(first?.target_ref ?? '', state)
  }, [first, onRestore, run.data, run.error])
  function selectResult(id: string) {
    if (id !== runId) onRestore(first?.target_ref ?? '', { status: 'idle' })
    setSelectedRunId(id)
  }
  const recovery = useMutation({ mutationFn: () => recoverRun(runId, AbortSignal.timeout(10_000)),
    onSuccess: async () => { await run.refetch(); await client.invalidateQueries({ queryKey: ['threads', projectId] }) } })
  const error = history.error || run.error || recovery.error
  return <section className="conversation-panel saved-conversation" aria-label="저장된 대화">
    <div className="conversation-stream" aria-live="polite">
      {history.isPending && <p role="status">저장된 대화를 불러오는 중입니다.</p>}
      {error && <div><p role="alert">{error instanceof Error ? error.message : errorMessage(error)}</p><button className="secondary" onClick={() => void (history.error ? history.refetch() : run.refetch())}>기록 다시 불러오기</button></div>}
      {history.hasNextPage && <button className="secondary" disabled={history.isFetchingNextPage} onClick={() => void history.fetchNextPage()}>이전 메시지 더 보기</button>}
      {first && messages.length === 0 && <p>저장된 메시지가 없습니다.</p>}
      {messages.map(message => <article key={message.id} aria-label={`${message.id}번 ${message.role === 'user' ? '사용자' : '에이전트'} 메시지`} className={`conversation-card ${message.role === 'user' ? 'user-card' : 'final-card'}`}>
        <span className="card-kicker">{message.role === 'user' ? '사용자 질문' : '에이전트 답변'}</span><p className="answer-text">{message.content}</p>
        {message.role === 'assistant' && (message.run_id === runId
          ? <ResultMenu result={!run.error && run.data?.message_id === message.id ? run.data.result : undefined}
            onShowActivity={onShowActivity} onShowJudgement={onShowJudgement} onShowEvidence={onShowEvidence} onShowActions={onShowActions} />
          : <button className="secondary saved-result-link" onClick={() => selectResult(message.run_id)}>분석 결과 확인</button>)}
      </article>)}
      {run.isFetching && <p role="status">저장된 분석 결과를 불러오는 중입니다.</p>}
    </div>
    <div className="saved-conversation-note"><p>저장된 기록을 보고 있습니다. 사용 조건 원문은 저장되지 않아 복원하지 않습니다. 새 분석은 왼쪽의 새 대화에서 시작하세요.</p>
      {run.data?.result.status === 'failed' && <p role="status">이 실행은 중단된 상태입니다. 새 대화에서 다시 시작해 주세요.</p>}
      {run.data && ['running', 'requires_input'].includes(run.data.result.status) && <><p>기록 열람은 분석이나 추가 입력을 자동 재개하지 않습니다.</p><button className="secondary" disabled={recovery.isPending} onClick={() => recovery.mutate()}>실행 상태 새로고침</button></>}
    </div>
  </section>
}

export default function ConversationPanel({ projectId, demoId = null, targetRef, roleLabels = [], initialQuestion = '', onResult, onConditions, onShowEvidence, onShowJudgement, onShowActivity, onShowActions, onThreadChange, onBusyChange }: {
  projectId: number
  demoId?: string | null
  targetRef: string
  roleLabels?: RoleLabel[]
  initialQuestion?: string
  onResult: (result: ReturnType<typeof useRunStream>['state']) => void
  onConditions?: (conditions: string) => void
  onShowEvidence?: () => void
  onShowJudgement?: () => void
  onShowActivity?: () => void
  onShowActions?: () => void
  onThreadChange?: (id: string) => void
  onBusyChange?: (busy: boolean) => void
}) {
  const client = useQueryClient()
  const [threadId, setThreadId] = useState('')
  const [question, setQuestion] = useState(initialQuestion)
  const [submitted, setSubmitted] = useState<{ question: string; conditions: string } | null>(null)
  const [creating, setCreating] = useState(false)
  const [creationError, setCreationError] = useState<unknown>(null)
  const [receivingStopped, setReceivingStopped] = useState(false)
  const demoQuestions = useQuery({ queryKey: ['demo-questions'], queryFn: ({ signal }) => listDemoQuestions(signal), retry: false, gcTime: 0, enabled: demoId !== null })
  const recorded = Array.isArray(demoQuestions.data) ? demoQuestions.data.filter(item => item.demo_id === demoId) : []
  const [demoItem, setDemoItem] = useState<DemoQuestionDto | null>(null)
  const errorSummary = useRef<HTMLParagraphElement>(null)
  const sendButton = useRef<HTMLButtonElement>(null)
  const run = useRunStream()
  useEffect(() => {
    if (run.state.status !== 'idle' && run.state.status !== 'running') void client.invalidateQueries({ queryKey: ['threads', projectId] })
  }, [client, projectId, run.state])
  useEffect(() => { onThreadChange?.(threadId) }, [onThreadChange, threadId])
  useEffect(() => { onResult(run.state) }, [onResult, run.state])
  useEffect(() => () => run.cancel(), [run.cancel])
  useEffect(() => { if (creationError || run.state.status === 'failed') errorSummary.current?.focus() }, [creationError, run.state])
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
  async function submit(text = question.trim(), extra = '', fresh = false) {
    if (!text || !targetRef || busy) return
    setCreationError(null)
    try {
      setReceivingStopped(false)
      const id = await ensureThread(fresh)
      onConditions?.(extra)
      setSubmitted({ question: text, conditions: extra })
      void run.start(id, { question: text, target_ref: targetRef, conditions: extra })
    } catch (error) { setCreationError(error); onResult({ status: 'failed', error: error as never }) }
  }
  function askRecorded(item: DemoQuestionDto) {
    setQuestion(item.question); setDemoItem(item)
    void submit(item.question, item.conditions, true)
  }
  function stopReceiving() {
    run.reset()
    setThreadId(''); setSubmitted(null); setDemoItem(null); setReceivingStopped(true)
  }
  const receiving = run.state.status === 'running' || run.state.status === 'requires_input'
  const processing = creating || run.state.status === 'running'
  const busy = creating || receiving
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false) }, [busy, onBusyChange])
  const interruptState = run.state.status === 'requires_input' ? run.state : null
  const failure = creationError ?? (run.state.status === 'failed' ? run.state.error : null)
  const forTarget = recorded.filter(item => item.target === targetRef)
  const resume = demoItem?.resume
  return <section className="conversation-panel" aria-label="에이전트 대화">
    <div className="conversation-stream" aria-live="polite">
      {receivingStopped && <p role="status">응답 수신을 중단했습니다. 서버 분석은 계속될 수 있으며 다음 질문은 새 대화에서 시작합니다.</p>}
      {recorded.length > 0 && <div className="demo-questions" role="group" aria-label="데모 질문"><p>키 없는 데모는 기록한 질문만 재생합니다. 누르면 새 대화로 보냅니다.</p>
        {forTarget.map(item => <button key={item.id} className="secondary" disabled={busy} onClick={() => askRecorded(item)}>{item.question}</button>)}
        {forTarget.length === 0 && <p>데모 질문이 있는 대상 부품: {[...new Set(recorded.map(item => item.target))].join(', ')}</p>}</div>}
      {submitted && <><article className="conversation-card user-card"><span className="card-kicker">사용자 질문</span><h3>{submitted.question}</h3>{submitted.conditions && <p>{submitted.conditions}</p>}</article>{!failure && <article className={`conversation-card status-card status-${run.state.status}`}><span className="card-kicker">분석 상태</span><RunStatus state={run.state} /></article>}</>}
      {interruptState && <article className="conversation-card interrupt-card"><span className="card-kicker">추가 정보 요청</span>{interruptState.error && <p role="alert">{errorMessage(interruptState.error)}</p>}{resume
        ? <div className="interrupt-form"><h3>추가 정보</h3><p>{interruptState.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</p><p>기록한 답: {Object.entries(resume.answers).map(([key, value]) => `${key}=${value}`).join(', ') || '모름'} · 역할: {resume.role || '없음'}</p><button onClick={() => void run.resume(interruptState.runId, { answers: resume.answers, role: resume.role || undefined })}>기록한 답으로 계속하기</button></div>
        : <InterruptForm interrupt={interruptState.interrupt} roleLabels={roleLabels} busy={false} onSubmit={(answers, role) => void run.resume(interruptState.runId, { answers, role })} />}</article>}
      {(run.state.status === 'completed' || run.state.status === 'refused') && <article className={`conversation-card final-card status-${run.state.status}`}><span className="card-kicker">{run.state.status === 'completed' ? '최종 답변' : '거절 또는 확인 불가'}</span>{run.state.result.answer || run.state.result.refusal ? <SafeMarkdown text={run.state.result.answer || run.state.result.refusal} /> : <p>표시할 답변이 없습니다.</p>}<ProfileHints hints={run.state.result.profile_hints ?? []} />{run.state.status === 'completed' && <div className="composer-actions"><button className="secondary" onClick={() => onShowEvidence?.()}>근거 보기</button><button className="secondary" onClick={() => onShowJudgement?.()}>후보 비교 결과 보기</button></div>}</article>}
      {threads.error && <p role="alert">{errorMessage(threads.error)}</p>}
      {run.state.status === 'failed' && <p ref={errorSummary} role="alert" tabIndex={-1}>{errorMessage(run.state.error)}</p>}
    </div>
  </section>
}
