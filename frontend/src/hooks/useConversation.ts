import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { createThread, getThread } from '../api/conversations'
import { useRunStream } from './useRunStream'

export type Turn = { runId: string; question: string }

// 대화 한 건의 상태: 저장된 질문 목록, 지금 실행 중인 질문, 단계 이름, 고른 질문.
export function useConversation({ projectId, targetRef, threadId, onThread }: { projectId: number; targetRef: string; threadId: string; onThread: (threadId: string, targetRef?: string) => void }) {
  const client = useQueryClient()
  const stream = useRunStream()
  const [history, setHistory] = useState<Turn[]>([])
  const [live, setLive] = useState<{ question: string } | null>(null)
  const [stages, setStages] = useState<string[]>([])
  const [text, setText] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const activeSend = useRef<AbortController | null>(null)
  const pendingDraft = useRef<{ question: string; files: File[] } | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const [before, setBefore] = useState<number | null>(null)
  const [loadingOlder, setLoadingOlder] = useState(false)
  const [olderError, setOlderError] = useState<unknown>(null)
  const activeOlder = useRef<AbortController | null>(null)
  const liveThread = useRef<string | null>(null)
  const state = stream.state
  const running = state.status === 'running' || state.status === 'stopped' || sending || (state.status === 'failed' && state.error.code === 'RUN_STATUS_PENDING')
  const waiting = state.status === 'requires_input'

  useEffect(() => {
    if (threadId === liveThread.current) return
    activeSend.current?.abort(); activeSend.current = null; setSending(false)
    pendingDraft.current = null
    activeOlder.current?.abort(); activeOlder.current = null; setBefore(null); setLoadingOlder(false); setOlderError(null)
    liveThread.current = threadId
    stream.reset(); setLive(null); setStages([]); setHistory([]); setError(null); setPicked(null); setLoading(false)
    if (!threadId) return
    const controller = new AbortController()
    setLoading(true)
    client.fetchQuery({ queryKey: ['thread', threadId], queryFn: ({ signal }) => getThread(threadId, signal), retry: false }).then((thread) => {
      if (controller.signal.aborted || thread.project_id !== projectId) return
      const turns = thread.messages.filter(message => message.role === 'user').map(message => ({ runId: message.run_id, question: message.content }))
      const active = thread.latest_run && ['running', 'requires_input', 'failed'].includes(thread.latest_run.status)
        ? turns.find(item => item.runId === thread.latest_run!.id) : undefined
      setHistory(active ? turns.filter(item => item !== active) : turns)
      setBefore(thread.next_before_message_id ?? null)
      if (active) { setLive({ question: active.question }); void stream.restore(active.runId) }
      if (thread.target_ref && thread.target_ref !== targetRef) onThread(threadId, thread.target_ref)
    }).catch((reason) => { if (!controller.signal.aborted) setError(reason) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => { controller.abort(); activeOlder.current?.abort(); liveThread.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 대화가 바뀔 때만 다시 읽는다
  }, [threadId])
  useEffect(() => () => activeSend.current?.abort(), [])

  useEffect(() => {
    if (state.status === 'running' && state.stage) setStages(current => current.includes(state.stage) ? current : [...current, state.stage])
    if (state.status === 'completed' || state.status === 'refused' || state.status === 'failed') {
      void client.invalidateQueries({ queryKey: ['threads', projectId] })
      if (state.runId) void client.invalidateQueries({ queryKey: ['run', state.runId] })
    }
  }, [state, client, projectId])

  useEffect(() => {
    if (state.status === 'idle' || !('runId' in state) || !state.runId || !pendingDraft.current) return
    const draft = pendingDraft.current
    pendingDraft.current = null
    if (text === draft.question && files.length === draft.files.length && files.every((file, index) => file === draft.files[index])) {
      setText(''); setFiles([])
    }
  }, [state, text, files])

  async function loadOlder() {
    if (before === null || activeOlder.current || loading || !threadId) return
    const active = new AbortController()
    activeOlder.current = active; setLoadingOlder(true); setOlderError(null)
    try {
      const page = await getThread(threadId, AbortSignal.any([active.signal, AbortSignal.timeout(10_000)]), before)
      if (active.signal.aborted || liveThread.current !== threadId || page.project_id !== projectId) return
      setHistory(current => {
        const seen = new Set(current.map(item => item.runId))
        const older = page.messages.filter(item => item.role === 'user').filter(item => {
          if (seen.has(item.run_id)) return false
          seen.add(item.run_id); return true
        }).map(item => ({ runId: item.run_id, question: item.content }))
        return [...older, ...current]
      })
      setBefore(page.next_before_message_id ?? null)
    } catch (reason) { if (!active.signal.aborted) setOlderError(reason) }
    finally {
      if (!active.signal.aborted) setLoadingOlder(false)
      if (activeOlder.current === active) activeOlder.current = null
    }
  }

  // 데모 질문은 기록한 글자 그대로 보내야 하므로 질문과 사용 조건을 직접 넘겨받는다.
  async function send(recorded?: { question: string; conditions?: string }) {
    const question = recorded?.question ?? text.trim()
    if (activeSend.current || !question || files.length || loading || running || waiting || !targetRef) return
    const active = new AbortController()
    activeSend.current = active; setSending(true); setError(null)
    if (recorded && !text) setText(current => current || question)
    try {
      let id = threadId
      if (!id) {
        id = (await createThread(projectId, AbortSignal.any([active.signal, AbortSignal.timeout(10_000)]))).id
        active.signal.throwIfAborted()
        liveThread.current = id; onThread(id)
      }
      active.signal.throwIfAborted()
      if (live && 'runId' in state && state.runId) setHistory(current => [...current, { runId: state.runId!, question: live.question }])
      setLive({ question }); setStages([]); setPicked(null)
      pendingDraft.current = { question: recorded?.question ?? text, files }
      await stream.start(id, { question, target_ref: targetRef, ...(recorded?.conditions !== undefined ? { conditions: recorded.conditions } : {}) })
    } catch (reason) { if (!active.signal.aborted) setError(reason) }
    finally { if (!active.signal.aborted) setSending(false); if (activeSend.current === active) activeSend.current = null }
  }

  return { history, live, stages, text, setText, files, setFiles, error, loading, picked, setPicked, before, loadingOlder, olderError, loadOlder, state, running, waiting, send, stream: { ...stream, cancel: () => { activeSend.current?.abort(); activeSend.current = null; setSending(false); stream.cancel() } } }
}
