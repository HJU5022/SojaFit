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
  const [picked, setPicked] = useState<number | null>(null)
  const liveThread = useRef('')
  const state = stream.state
  const running = state.status === 'running'

  useEffect(() => {
    if (threadId === liveThread.current) return
    liveThread.current = threadId
    stream.reset(); setLive(null); setStages([]); setHistory([]); setError(null); setPicked(null)
    if (!threadId) return
    const controller = new AbortController()
    setLoading(true)
    getThread(threadId, controller.signal).then((thread) => {
      setHistory(thread.messages.filter(message => message.role === 'user').map(message => ({ runId: message.run_id, question: message.content })))
      if (thread.target_ref && thread.target_ref !== targetRef) onThread(threadId, thread.target_ref)
    }).catch((reason) => { if (!controller.signal.aborted) setError(reason) }).finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 대화가 바뀔 때만 다시 읽는다
  }, [threadId])

  useEffect(() => {
    if (state.status === 'running' && state.stage) setStages(current => current.includes(state.stage) ? current : [...current, state.stage])
    if (state.status === 'completed' || state.status === 'refused') void client.invalidateQueries({ queryKey: ['threads', projectId] })
  }, [state, client, projectId])

  // 데모 질문은 기록한 글자 그대로 보내야 하므로 질문과 사용 조건을 직접 넘겨받는다.
  async function send(recorded?: { question: string; conditions?: string }) {
    const question = recorded?.question ?? text.trim()
    if (!question || running || !targetRef) return
    setError(null)
    try {
      let id = threadId
      if (!id) { id = (await createThread(projectId)).id; liveThread.current = id; onThread(id) }
      if (live && 'runId' in state && state.runId && state.status !== 'failed') setHistory(current => [...current, { runId: state.runId!, question: live.question }])
      const attachments = recorded ? [] : files
      setLive({ question }); setStages([]); setText(''); setFiles([]); setPicked(null)
      await stream.start(id, { question, target_ref: targetRef, ...(recorded?.conditions !== undefined ? { conditions: recorded.conditions } : {}), ...(attachments.length ? { attachments } : {}) })
    } catch (reason) { setError(reason) }
  }

  return { history, live, stages, text, setText, files, setFiles, error, loading, picked, setPicked, state, running, send, stream }
}
