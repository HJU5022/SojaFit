import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createThread, getRun, recoverRun, getThread, listDemoQuestions } from '../api/conversations'
import type { DemoQuestionDto, EvidenceDto, ResultDto, RoleLabel } from '../api/conversations'
import { errorMessage } from '../api/client'
import { useRunStream } from '../hooks/useRunStream'
import RunStatus, { ProcessingIcon } from './RunStatus'
import InterruptForm from './InterruptForm'
import ProfileHints from './ProfileHints'
import SafeMarkdown from './SafeMarkdown'
import type { RunState } from '../hooks/useRunStream'
import { approvableCandidatesOf, candidatesOf } from './circuitContext'

export type ComposerDraft = { question: string; files: File[] }
type DraftProps = { draft?: ComposerDraft; onDraftChange?: (draft: ComposerDraft) => void }
type SubmittedQuestion = { question: string; conditions: string; files: string[] }
type TranscriptTurn = { submitted: SubmittedQuestion; answer?: string; error?: string; stopped?: boolean }

export function ConversationComposer({ draft, onDraftChange, onSend, sendDisabled = true, receiving = false, processing = false, hint = '' }: {
  draft: ComposerDraft; onDraftChange: (draft: ComposerDraft) => void; onSend?: () => void
  sendDisabled?: boolean; receiving?: boolean; processing?: boolean; hint?: string
}) {
  const picker = useRef<HTMLInputElement>(null)
  const [fileError, setFileError] = useState('')
  function selectFiles(files: FileList | null) {
    if (!files?.length) return
    const next = [...draft.files]
    for (const file of Array.from(files)) {
      if (!/\.(net|txt)$/i.test(file.name) || file.size === 0 || file.size > 5 * 1024 * 1024) { setFileError('UTF-8 NET·TXT 파일을 5 MiB 이하로 선택하세요. PDF·이미지는 아직 지원하지 않으며 빈 파일은 첨부할 수 없습니다.'); return }
      if (!next.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) next.push(file)
    }
    if (next.length > 5 || next.reduce((size, file) => size + file.size, 0) > 20 * 1024 * 1024) { setFileError('첨부는 최대 5개, 합계 20 MiB까지 선택할 수 있습니다.'); return }
    setFileError(''); onDraftChange({ ...draft, files: next })
  }
  return <div className="composer">
    <label htmlFor="d5-question">질문</label>
    <div className="composer-input-row">
      <textarea id="d5-question" rows={3} maxLength={4000} value={draft.question} onChange={event => onDraftChange({ ...draft, question: event.target.value })} onKeyDown={event => {
        if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return
        event.preventDefault()
        if (!receiving && !sendDisabled && draft.question.trim() && !event.repeat) onSend?.()
      }} placeholder="메시지를 입력하세요. Shift+Enter로 줄바꿈" />
      {import.meta.env.DEV && <><button type="button" className="composer-attach secondary" aria-label="파일 첨부" title="NET·TXT 파일 첨부" onClick={() => picker.current?.click()}><svg aria-hidden="true" viewBox="0 0 24 24"><path d="m9 15 7-7a3 3 0 0 1 4 4L10 22a6 6 0 0 1-8-8L13 3a4 4 0 0 1 6 6L8 20" /></svg></button>
      <input ref={picker} type="file" multiple accept=".net,.txt" aria-label="첨부 파일 선택" className="sr-only" tabIndex={-1} onChange={event => { selectFiles(event.target.files); event.target.value = '' }} /></>}
      <button type="button" className="composer-send" aria-label={receiving ? '응답 수신 중단' : '질문 전송'} title={receiving ? '응답 수신 중단' : '질문 전송'} aria-busy={processing} disabled={sendDisabled || (!receiving && !draft.question.trim())} onClick={onSend}>{processing ? <ProcessingIcon stop={receiving} /> : <svg aria-hidden="true" viewBox="0 0 24 24">{receiving ? <rect x="6" y="6" width="12" height="12" rx="1" /> : <path d="M12 19V5M6 11l6-6 6 6" />}</svg>}</button>
    </div>
    {hint && <p className="composer-hint">{hint}</p>}
    {draft.files.length > 0 && <><ul className="composer-attachments" aria-label="선택한 첨부 파일">{draft.files.map((file, index) => <li key={`${file.name}-${file.size}-${file.lastModified}`}><span title={file.name}>{file.name}</span><button type="button" className="secondary" aria-label={`${file.name} 첨부 제거`} onClick={() => { onDraftChange({ ...draft, files: draft.files.filter((_, i) => i !== index) }); setFileError('') }}>×</button></li>)}</ul><p className="composer-hint" role="status">NET·TXT는 질문과 함께 서버에서 읽습니다. 원본 파일은 저장하지 않으며, 추출 내용은 분석 기록에 포함될 수 있습니다.</p></>}
    {fileError && <p role="alert">{fileError}</p>}
  </div>
}

function AnswerText({ text, evidence = [], onShowEvidence }: { text: string; evidence?: EvidenceDto[]; onShowEvidence?: () => void }) {
  const citations = new Set(evidence.map(item => `[${item.citation_number}]`))
  const renderCitations = (value: string) => value.split(/(\[\d+\])/g).map((part, index) => citations.has(part) && onShowEvidence
    ? <button key={index} type="button" className="answer-citation-link" aria-label={`문서 근거 ${part} 보기`} onClick={onShowEvidence}>{part}</button>
    : part)
  return <SafeMarkdown text={text} renderText={renderCitations} />
}

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

export function SavedConversationPanel({ projectId, threadId, onRestore, onEmptyThread, draft, onDraftChange, onShowActivity, onShowJudgement, onShowEvidence, onShowActions }: {
  projectId: number; threadId: string; onRestore: (target: string, state: RunState) => void
  onEmptyThread?: (threadId: string) => void
  onShowActivity: () => void; onShowJudgement: () => void; onShowEvidence: () => void; onShowActions: () => void
} & DraftProps) {
  const client = useQueryClient()
  const [selectedRunId, setSelectedRunId] = useState('')
  const stream = useRef<HTMLDivElement>(null)
  const initialPosition = useRef(false)
  const olderPosition = useRef<{ height: number; top: number } | null>(null)
  const loadingOlder = useRef(false)
  const history = useInfiniteQuery({ queryKey: ['thread-history', projectId, threadId], initialPageParam: undefined as number | undefined,
    queryFn: async ({ signal, pageParam }) => {
      const detail = await getThread(threadId, AbortSignal.any([signal, AbortSignal.timeout(10_000)]), pageParam)
      if (detail.id !== threadId || detail.project_id !== projectId) throw new Error('선택한 프로젝트의 대화가 아닙니다.')
      return detail
    }, getNextPageParam: page => page.next_before_message_id ?? undefined, retry: false, gcTime: 0, refetchOnWindowFocus: false })
  const first = history.data?.pages[0]
  const messages = [...new Map((first ? history.data?.pages.flatMap(page => page.messages) ?? [] : []).map(message => [message.id, message])).values()].sort((a, b) => a.id - b.id)
  const runId = selectedRunId || first?.latest_run?.id || ''
  useLayoutEffect(() => {
    const node = stream.current
    if (!node || !first) return
    if (olderPosition.current) {
      node.scrollTop = olderPosition.current.top + node.scrollHeight - olderPosition.current.height
      olderPosition.current = null
    } else if (!initialPosition.current) {
      node.scrollTop = node.scrollHeight
      initialPosition.current = true
    }
  }, [messages.length, history.data?.pages.length, first])
  function loadEarlier() {
    if (!history.hasNextPage || history.isFetchingNextPage || loadingOlder.current) return
    loadingOlder.current = true
    if (stream.current) olderPosition.current = { height: stream.current.scrollHeight, top: stream.current.scrollTop }
    void history.fetchNextPage().then(result => { if (result.isError) olderPosition.current = null })
      .catch(() => { olderPosition.current = null }).finally(() => { loadingOlder.current = false })
  }
  useEffect(() => {
    if (first && first.target_locked === false && first.latest_run === null && first.messages.length === 0 && first.next_before_message_id === null) onEmptyThread?.(threadId)
  }, [first, onEmptyThread, threadId])
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
    <div ref={stream} className="conversation-stream" aria-live="polite" onScroll={event => { if (olderPosition.current) olderPosition.current.top = event.currentTarget.scrollTop; if (event.currentTarget.scrollTop <= 80 && !history.isFetchNextPageError) loadEarlier() }}>
      {history.isPending && <p role="status">저장된 대화를 불러오는 중입니다.</p>}
      {error && <div><p role="alert">{error instanceof Error ? error.message : errorMessage(error)}</p><button className="secondary" onClick={() => void (history.error ? history.refetch() : run.refetch())}>기록 다시 불러오기</button></div>}
      {history.hasNextPage && <button className="secondary" disabled={history.isFetchingNextPage} onClick={loadEarlier}>이전 메시지 더 보기</button>}
      {first && messages.length === 0 && <p>저장된 메시지가 없습니다.</p>}
      {messages.map(message => <article key={message.id} aria-label={`${message.id}번 ${message.role === 'user' ? '사용자' : '에이전트'} 메시지`} className={`conversation-card ${message.role === 'user' ? 'user-card' : 'final-card'}`}>
        <span className="card-kicker">{message.role === 'user' ? '사용자 질문' : '에이전트 답변'}</span><div className="answer-text"><AnswerText text={message.content} evidence={message.role === 'assistant' && message.run_id === runId && !run.error && run.data?.message_id === message.id ? run.data.result.evidence : undefined} onShowEvidence={onShowEvidence} /></div>
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
    {draft && onDraftChange && <ConversationComposer draft={draft} onDraftChange={onDraftChange} hint="저장된 기록입니다. 왼쪽 +로 새 대화를 시작하면 질문을 전송할 수 있습니다." />}
  </section>
}

export default function ConversationPanel({ projectId, demoId = null, targetRef, roleLabels = [], initialQuestion = '', initialThreadId = '', disabled = false, draft, onDraftChange, onResult, onConditions, onShowEvidence, onShowJudgement, onShowActivity, onShowActions, onThreadChange, onBusyChange }: {
  projectId: number
  demoId?: string | null
  targetRef: string
  roleLabels?: RoleLabel[]
  initialQuestion?: string
  initialThreadId?: string
  disabled?: boolean
  onResult: (result: ReturnType<typeof useRunStream>['state']) => void
  onConditions?: (conditions: string) => void
  onShowEvidence?: () => void
  onShowJudgement?: () => void
  onShowActivity?: () => void
  onShowActions?: () => void
  onThreadChange?: (id: string) => void
  onBusyChange?: (busy: boolean) => void
} & DraftProps) {
  const client = useQueryClient()
  const [threadId, setThreadId] = useState(initialThreadId)
  const [localDraft, setLocalDraft] = useState<ComposerDraft>({ question: initialQuestion, files: [] })
  const currentDraft = draft ?? localDraft
  const setDraft = onDraftChange ?? setLocalDraft
  const question = currentDraft.question
  const [submitted, setSubmitted] = useState<SubmittedQuestion | null>(null)
  const [transcript, setTranscript] = useState<TranscriptTurn[]>([])
  const transcriptThread = useRef(initialThreadId)
  const stream = useRef<HTMLDivElement>(null)
  const followLatest = useRef(true)
  const [creating, setCreating] = useState(false)
  const [creationError, setCreationError] = useState<unknown>(null)
  const [receivingStopped, setReceivingStopped] = useState(false)
  const demoQuestions = useQuery({ queryKey: ['demo-questions'], queryFn: ({ signal }) => listDemoQuestions(signal), retry: false, gcTime: 0, enabled: demoId !== null })
  const recorded = Array.isArray(demoQuestions.data) ? demoQuestions.data.filter(item => item.demo_id === demoId) : []
  const [demoItem, setDemoItem] = useState<DemoQuestionDto | null>(null)
  const errorSummary = useRef<HTMLParagraphElement>(null)
  useEffect(() => { if (initialThreadId && targetRef) document.getElementById('d5-question')?.focus() }, [initialThreadId, targetRef])
  const run = useRunStream()
  useLayoutEffect(() => {
    if (followLatest.current && stream.current) stream.current.scrollTop = stream.current.scrollHeight
  }, [submitted, transcript, run.state, creationError])
  function rememberTurn(stopped = false) {
    if (!submitted) return
    if (stopped) setTranscript(current => [...current, { submitted, stopped: true }])
    else if (run.state.status === 'completed' || run.state.status === 'refused') {
      const answer = run.state.result.answer || run.state.result.refusal || '표시할 답변이 없습니다.'
      setTranscript(current => [...current, { submitted, answer }])
    } else if (run.state.status === 'failed' && run.state.runId) {
      const error = errorMessage(run.state.error)
      setTranscript(current => [...current, { submitted, error }])
    }
  }
  const pendingDraft = useRef<{ draft: ComposerDraft; state: RunState } | null>(null)
  useEffect(() => {
    const sent = pendingDraft.current
    if (!sent || sent.state === run.state || run.state.status === 'idle' || (run.state.status === 'running' && !run.state.runId)) return
    pendingDraft.current = null
    if ((run.state.status !== 'failed' || run.state.runId) && currentDraft === sent.draft) setDraft({ question: '', files: [] })
  }, [run.state, currentDraft, setDraft])
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
    if (!text || !targetRef || busy || disabled) return
    followLatest.current = true
    const sentDraft = fresh ? { ...currentDraft, question: text } : currentDraft
    if (fresh) setDraft(sentDraft)
    setCreationError(null)
    try {
      setReceivingStopped(false)
      const id = await ensureThread(fresh)
      if (fresh || (transcriptThread.current && transcriptThread.current !== id)) setTranscript([])
      else rememberTurn()
      transcriptThread.current = id
      run.reset()
      onConditions?.(extra)
      pendingDraft.current = { draft: sentDraft, state: run.state }
      setSubmitted({ question: text, conditions: extra, files: sentDraft.files.map(file => file.name) })
      void run.start(id, { question: text, target_ref: targetRef, conditions: extra, ...(sentDraft.files.length ? { attachments: sentDraft.files } : {}) })
    } catch (error) { pendingDraft.current = null; setCreationError(error); onResult({ status: 'failed', error: error as never }) }
  }
  function askRecorded(item: DemoQuestionDto) {
    setDemoItem(item)
    void submit(item.question, item.conditions, true)
  }
  function stopReceiving() {
    rememberTurn(true)
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
    <div ref={stream} className="conversation-stream" aria-live="polite" onScroll={event => { const node = event.currentTarget; followLatest.current = node.scrollHeight - node.scrollTop - node.clientHeight <= 64 }}>
      {transcript.map((turn, index) => <Fragment key={index}>
        <article className="conversation-card user-card"><span className="card-kicker">사용자 질문</span><h3>{turn.submitted.question}</h3>{turn.submitted.files.length > 0 && <p>첨부: {turn.submitted.files.join(', ')}</p>}{turn.submitted.conditions && <p>{turn.submitted.conditions}</p>}{turn.stopped && <p>응답 수신 중단</p>}</article>
        {(turn.answer || turn.error) && <article className="conversation-card final-card"><span className="card-kicker">에이전트 답변</span><SafeMarkdown text={turn.answer || turn.error || ""} /></article>}
      </Fragment>)}
      {receivingStopped && <p role="status">응답 수신을 중단했습니다. 서버 분석은 계속될 수 있으며 다음 질문은 새 대화에서 시작합니다.</p>}
      {recorded.length > 0 && <div className="demo-questions" role="group" aria-label="데모 질문"><p>키 없는 데모는 기록한 질문만 재생합니다. 누르면 새 대화로 보냅니다.</p>
        {forTarget.map(item => <button key={item.id} className="secondary" disabled={busy || disabled} onClick={() => askRecorded(item)}>{item.question}</button>)}
        {forTarget.length === 0 && <p>데모 질문이 있는 대상 부품: {[...new Set(recorded.map(item => item.target))].join(', ')}</p>}</div>}
      {submitted && <><article className="conversation-card user-card"><span className="card-kicker">사용자 질문</span><h3>{submitted.question}</h3>{submitted.files.length > 0 && <p>첨부: {submitted.files.join(', ')}</p>}{submitted.conditions && <p>{submitted.conditions}</p>}</article>{!failure && <article className={`conversation-card status-card status-${run.state.status}`}><span className="card-kicker">분석 상태</span><RunStatus state={run.state} /></article>}</>}
      {interruptState && <article className="conversation-card interrupt-card"><span className="card-kicker">추가 정보 요청</span>{interruptState.error && <p role="alert">{errorMessage(interruptState.error)}</p>}{resume
        ? <div className="interrupt-form"><h3>추가 정보</h3><p>{interruptState.interrupt.question || '판정에 필요한 값을 알려 주세요.'}</p><p>기록한 답: {Object.entries(resume.answers).map(([key, value]) => `${key}=${value}`).join(', ') || '모름'} · 역할: {resume.role || '없음'}</p><button onClick={() => void run.resume(interruptState.runId, { answers: resume.answers, role: resume.role || undefined })}>기록한 답으로 계속하기</button></div>
        : <InterruptForm interrupt={interruptState.interrupt} roleLabels={roleLabels} busy={false} onSubmit={(answers, role) => void run.resume(interruptState.runId, { answers, role })} />}</article>}
      {(run.state.status === 'completed' || run.state.status === 'refused') && <article className={`conversation-card final-card status-${run.state.status}`}><span className="card-kicker">{run.state.status === 'completed' ? '최종 답변' : '거절 또는 확인 불가'}</span><div className="answer-text"><AnswerText text={run.state.result.answer || run.state.result.refusal || '표시할 답변이 없습니다.'} evidence={run.state.result.evidence} onShowEvidence={onShowEvidence} /></div><ProfileHints hints={run.state.result.profile_hints ?? []} /><ResultMenu result={run.state.result} onShowActivity={onShowActivity} onShowJudgement={onShowJudgement} onShowEvidence={onShowEvidence} onShowActions={onShowActions} /></article>}
      {failure && <div><p ref={errorSummary} role="alert" tabIndex={-1}>{errorMessage(failure)}</p>{!creationError && run.state.status === 'failed' && run.state.runId && <button className="secondary" onClick={() => { if (run.state.status === 'failed' && run.state.runId) void run.refresh(run.state.runId) }}>실행 상태 확인</button>}</div>}
    </div>
    <ConversationComposer draft={currentDraft} onDraftChange={setDraft} receiving={receiving} processing={processing}
      sendDisabled={disabled || creating || (!receiving && !targetRef)}
      hint={!targetRef ? '질문을 미리 작성할 수 있습니다. 프로젝트와 분석할 부품을 선택하면 전송할 수 있습니다.' : ''}
      onSend={() => { if (receiving) stopReceiving(); else { setDemoItem(null); void submit() } }} />
  </section>
}
