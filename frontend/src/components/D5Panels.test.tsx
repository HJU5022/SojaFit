import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { expect, it, vi } from 'vitest'
import EvidencePanel from './EvidencePanel'
import InterruptForm from './InterruptForm'
import JudgementTable from './JudgementTable'
import RunStatus from './RunStatus'
import ProfileHints from './ProfileHints'
import ConversationPanel, { ConversationComposer, SavedConversationPanel } from './ConversationPanel'
import type { ComposerDraft } from './ConversationPanel'
import { createThread, listDemoQuestions } from '../api/conversations'

const startRun = vi.fn()
const resetRun = vi.fn()
const refreshRun = vi.fn()
let mockedRunState: any = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
vi.mock('../api/conversations', async () => {
  const actual = await vi.importActual<typeof import('../api/conversations')>('../api/conversations')
  return { ...actual, listThreads: vi.fn().mockResolvedValue([]), createThread: vi.fn().mockResolvedValue({ id: 'thread-1' }), listDemoQuestions: vi.fn().mockResolvedValue([]) }
})
vi.mock('../hooks/useRunStream', () => ({
  useRunStream: () => ({
    state: mockedRunState,
    start: startRun, resume: vi.fn(), cancel: vi.fn(), reset: resetRun, refresh: refreshRun,
  }),
}))

function renderConversation(props: Partial<React.ComponentProps<typeof ConversationPanel>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ConversationPanel projectId={1} targetRef="D1" onResult={vi.fn()} {...props} /></QueryClientProvider>)
}

function ComposerHarness() {
  const [draft, setDraft] = useState<ComposerDraft>({ question: '', files: [] })
  return <ConversationComposer draft={draft} onDraftChange={setDraft} sendDisabled={false} onSend={startRun} />
}

it('keeps both question-answer pairs in one live thread without repeating the previous answer', async () => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  resetRun.mockImplementation(() => { mockedRunState = { status: 'idle' } })
  startRun.mockClear(); vi.mocked(createThread).mockClear()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const ui = () => <QueryClientProvider client={client}><ConversationPanel projectId={1} targetRef="D1" initialQuestion="첫 질문" onResult={vi.fn()} /></QueryClientProvider>
  try {
    const view = render(ui())
    fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
    await waitFor(() => expect(startRun).toHaveBeenCalledTimes(1))
    mockedRunState = { status: 'completed', runId: 'first-run', result: { answer: '첫 답변', evidence: [] } }
    view.rerender(ui())
    expect(screen.getByText('첫 답변')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '두 번째 질문' } })
    fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
    await waitFor(() => expect(startRun).toHaveBeenCalledTimes(2))
    expect(screen.getByRole('heading', { name: '첫 질문' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '두 번째 질문' })).toBeInTheDocument()
    expect(screen.getAllByText('첫 답변')).toHaveLength(1)
    mockedRunState = { status: 'refused', runId: 'second-run', result: { answer: '두 번째 응답', evidence: [] } }
    view.rerender(ui())
    expect(screen.getByText('첫 답변')).toBeInTheDocument()
    expect(screen.getByText('두 번째 응답')).toBeInTheDocument()
    expect(vi.mocked(createThread)).toHaveBeenCalledTimes(1)
  } finally { mockedRunState = previous; resetRun.mockReset() }
})

it('keeps saved messages on a failed older-page read and preserves the scroll anchor on retry', async () => {
  let requests = 0
  let finish!: (response: Response) => void
  const fetcher = vi.fn((path: string) => {
    if (path.includes('before_message_id')) {
      requests++
      if (requests === 1) return Promise.resolve(Response.json({ error: { code: 'UNAVAILABLE', message: '이전 기록 읽기 실패', request_id: 'older-page' } }, { status: 503 }))
      return new Promise<Response>(resolve => { finish = resolve })
    }
    return Promise.resolve(Response.json({ id: 'saved-thread', project_id: 1, target_ref: 'D1', target_locked: true, latest_run: null,
      messages: [{ id: 3, run_id: 'r', role: 'user', content: '최근 질문' }, { id: 4, run_id: 'r', role: 'assistant', content: '최근 답변' }], next_before_message_id: 3 }))
  })
  vi.stubGlobal('fetch', fetcher)
  try {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><SavedConversationPanel projectId={1} threadId="saved-thread" onRestore={vi.fn()}
      onShowActivity={vi.fn()} onShowEvidence={vi.fn()} onShowJudgement={vi.fn()} onShowActions={vi.fn()} /></QueryClientProvider>)
    await screen.findByText('최근 답변')
    const stream = document.querySelector<HTMLDivElement>('.saved-conversation .conversation-stream')!
    let height = 1000
    Object.defineProperty(stream, 'scrollHeight', { get: () => height })
    fireEvent.scroll(stream, { target: { scrollTop: 20 } })
    await screen.findByRole('alert')
    expect(screen.getByText('최근 질문')).toBeInTheDocument()
    expect(screen.getByText('최근 답변')).toBeInTheDocument()
    fireEvent.scroll(stream, { target: { scrollTop: 10 } })
    expect(requests).toBe(1)
    fireEvent.click(screen.getByRole('button', { name: '이전 메시지 더 보기' }))
    await waitFor(() => expect(requests).toBe(2))
    height = 1800
    await act(async () => finish(Response.json({ id: 'saved-thread', project_id: 1, target_ref: 'D1', target_locked: true, latest_run: null,
      messages: [{ id: 1, run_id: 'old', role: 'user', content: '처음 질문' }, { id: 2, run_id: 'old', role: 'assistant', content: '처음 답변' }], next_before_message_id: null })))
    await screen.findByText('처음 답변')
    expect(stream.scrollTop).toBe(810)
    expect(screen.getByText('최근 답변')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '이전 메시지 더 보기' })).not.toBeInTheDocument()
    expect(fetcher.mock.calls.every(([, init]: any[]) => !init?.method || init.method === 'GET')).toBe(true)
  } finally { vi.unstubAllGlobals() }
})

it.each([false, true])('clears an accepted question once without clearing the next draft (shared=%s)', async shared => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  startRun.mockClear()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  function Panel() {
    const [draft, setDraft] = useState<ComposerDraft>({ question: 'D1 설명해줘', files: [] })
    return <ConversationPanel projectId={1} targetRef="D1" initialQuestion="D1 설명해줘" onResult={vi.fn()}
      draft={shared ? draft : undefined} onDraftChange={shared ? setDraft : undefined} />
  }
  const ui = () => <QueryClientProvider client={client}><Panel /></QueryClientProvider>
  try {
    const view = render(ui())
    fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
    await waitFor(() => expect(startRun).toHaveBeenCalledTimes(1))
    expect(screen.getByLabelText('질문')).toHaveValue('D1 설명해줘')
    mockedRunState = { status: 'running', runId: 'accepted-run', stage: '입력 확인' }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('')
    expect(screen.getByRole('heading', { name: 'D1 설명해줘' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '다음 질문' } })
    mockedRunState = { status: 'completed', runId: 'accepted-run', result: { answer: '회로 설명입니다.', evidence: [] } }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('다음 질문')
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1 설명해줘' } })
    expect(screen.getByLabelText('질문')).toHaveValue('D1 설명해줘')
    fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
    await waitFor(() => expect(startRun).toHaveBeenCalledTimes(2))
    mockedRunState = { status: 'failed', error: { code: 'UNAVAILABLE', message: '접수 실패', requestId: '' } }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('D1 설명해줘')
  } finally { mockedRunState = previous }
})

it('preserves a changed question and new attachment while thread creation and the reply are pending', async () => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  let finish!: (value: { id: string; project_id: number }) => void
  vi.mocked(createThread).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  startRun.mockClear()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const ui = () => <QueryClientProvider client={client}><ConversationPanel projectId={1} targetRef="D1" initialQuestion="전송할 질문" onResult={vi.fn()} /></QueryClientProvider>
  try {
    const view = render(ui())
    fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '다음 질문 초안' } })
    fireEvent.change(screen.getByLabelText('첨부 파일 선택'), { target: { files: [new File(['synthetic'], 'next.txt')] } })
    await act(async () => finish({ id: 'created-thread', project_id: 1 }))
    expect(startRun).toHaveBeenCalledExactlyOnceWith('created-thread', { question: '전송할 질문', target_ref: 'D1', conditions: '' })
    mockedRunState = { status: 'running', runId: 'accepted-run', stage: '입력 확인' }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('다음 질문 초안')
    expect(screen.getByText('next.txt')).toBeInTheDocument()
    mockedRunState = { status: 'completed', runId: 'accepted-run', result: { answer: '확인했습니다.', evidence: [] } }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('다음 질문 초안')
    expect(screen.getByText('next.txt')).toBeInTheDocument()
  } finally { mockedRunState = previous }
})

it('clears the recorded question through the same submission path on an immediate result', async () => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  startRun.mockClear()
  vi.mocked(listDemoQuestions).mockResolvedValueOnce([{ id: 'recorded', kind: 'judge', circuit: 'test', demo_id: 'test', target: 'D1', question: '기록한 질문', conditions: '12 V', resume: null }])
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const ui = () => <QueryClientProvider client={client}><ConversationPanel projectId={1} targetRef="D1" demoId="test" onResult={vi.fn()} /></QueryClientProvider>
  try {
    const view = render(ui())
    fireEvent.click(await screen.findByRole('button', { name: '기록한 질문' }))
    await waitFor(() => expect(startRun).toHaveBeenCalledExactlyOnceWith('thread-1', { question: '기록한 질문', target_ref: 'D1', conditions: '12 V' }))
    expect(screen.getByLabelText('질문')).toHaveValue('기록한 질문')
    mockedRunState = { status: 'completed', runId: 'recorded-run', result: { answer: '기록한 답변', evidence: [] } }
    view.rerender(ui())
    expect(screen.getByLabelText('질문')).toHaveValue('')
    expect(screen.getByRole('heading', { name: '기록한 질문' })).toBeInTheDocument()
  } finally { mockedRunState = previous }
})

it('stages NET/TXT files and allows a question to be sent with them', () => {
  startRun.mockClear()
  render(<ComposerHarness />)
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '이 부품 확인' } })
  const file = new File(['test-only'], 'notes.txt', { type: 'text/plain', lastModified: 1 })
  const input = screen.getByLabelText('첨부 파일 선택')
  fireEvent.change(input, { target: { files: [file] } })
  fireEvent.change(input, { target: { files: [file] } })
  expect(screen.getAllByText('notes.txt')).toHaveLength(1)
  expect(screen.getByRole('status')).toHaveTextContent('질문과 함께 서버에서 읽습니다')
  expect(screen.getByLabelText('질문')).toBeEnabled()
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeEnabled()
  fireEvent.keyDown(screen.getByLabelText('질문'), { key: 'Enter' })
  expect(startRun).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: 'notes.txt 첨부 제거' }))
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeEnabled()
  fireEvent.keyDown(screen.getByLabelText('질문'), { key: 'Enter' })
  expect(startRun).toHaveBeenCalledTimes(2)
})

it('preserves files and question when attachment limits or types are rejected', () => {
  render(<ComposerHarness />)
  const input = screen.getByLabelText('첨부 파일 선택')
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '작성 중' } })
  const file = new File(['test'], 'circuit.net')
  fireEvent.change(input, { target: { files: [file] } })
  for (const invalid of [new File(['bad'], 'script.svg'), new File([], 'empty.txt'), new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'large.txt')]) {
    fireEvent.change(input, { target: { files: [invalid] } })
    expect(screen.getByRole('alert')).toHaveTextContent('5 MiB 이하')
    expect(screen.getByText('circuit.net')).toBeInTheDocument()
  }
  fireEvent.change(input, { target: { files: Array.from({ length: 5 }, (_, index) => new File(['test'], `extra${index}.txt`)) } })
  expect(screen.getByRole('alert')).toHaveTextContent('최대 5개')
  fireEvent.change(input, { target: { files: Array.from({ length: 4 }, (_, index) => new File([new Uint8Array(5 * 1024 * 1024)], `total${index}.txt`)) } })
  expect(screen.getByRole('alert')).toHaveTextContent('합계 20 MiB')
  expect(screen.getByRole('list', { name: '선택한 첨부 파일' }).children).toHaveLength(1)
  expect(screen.getByLabelText('질문')).toHaveValue('작성 중')
})

it('rejects PDF and images without changing the draft or creating an image preview', () => {
  const create = vi.spyOn(URL, 'createObjectURL')
  try {
    render(<ComposerHarness />)
    fireEvent.change(screen.getByLabelText('질문'), { target: { value: '작성한 질문' } })
    for (const name of ['sheet.pdf', 'circuit.png']) {
      fireEvent.change(screen.getByLabelText('첨부 파일 선택'), { target: { files: [new File(['test'], name)] } })
      expect(screen.getByRole('alert')).toHaveTextContent('PDF·이미지는 아직 지원하지 않으며')
      expect(screen.queryByRole('list', { name: '선택한 첨부 파일' })).not.toBeInTheDocument()
      expect(screen.getByLabelText('질문')).toHaveValue('작성한 질문')
    }
    expect(create).not.toHaveBeenCalled()
  } finally { create.mockRestore() }
})

it.each(['idle', 'running', 'requires_input', 'failed'])('keeps typing enabled without a target in %s and never sends or stops with Enter', status => {
  const previous = mockedRunState
  mockedRunState = { status, runId: 'r', interrupt: {}, error: { code: 'FAIL', message: '실패', requestId: '' } }
  startRun.mockClear(); resetRun.mockClear()
  try {
    renderConversation({ targetRef: '', disabled: true })
    const question = screen.getByLabelText('질문')
    expect(question).toBeEnabled()
    expect(question).not.toHaveAttribute('readonly')
    fireEvent.change(question, { target: { value: '분석 중에도 작성' } })
    fireEvent.keyDown(question, { key: 'Enter' })
    expect(question).toHaveValue('분석 중에도 작성')
    expect(startRun).not.toHaveBeenCalled()
    expect(resetRun).not.toHaveBeenCalled()
  } finally { mockedRunState = previous }
})

it.each(['idle', 'running', 'requires_input', 'failed'])('hides result actions before an answer in %s', status => {
  const previous = mockedRunState
  mockedRunState = { status, runId: 'run-1', stage: '분석', interrupt: { missing: [] }, error: { code: 'FAIL', message: '실패' } }
  try {
    renderConversation()
    expect(screen.queryByRole('group', { name: '분석 결과 메뉴' })).not.toBeInTheDocument()
  } finally { mockedRunState = previous }
})

it.each([
  { status: 'completed', verdict: null, evidence: false, expected: ['분석 현황'] },
  { status: 'completed', verdict: null, evidence: true, expected: ['분석 현황', '문서 근거'] },
  { status: 'completed', verdict: 'NOT_SUFFICIENT', evidence: false, expected: ['분석 현황', '후보 비교'] },
  { status: 'completed', verdict: 'NOT_VERIFIED', evidence: true, expected: ['분석 현황', '후보 비교', '문서 근거'] },
  { status: 'completed', verdict: 'ROLE_SUFFICIENT', evidence: true, expected: ['분석 현황', '후보 비교', '문서 근거', '승인·견적'] },
  { status: 'completed', verdict: 'IDENTICAL', evidence: false, expected: ['분석 현황', '후보 비교', '승인·견적'] },
  { status: 'completed', verdict: 'SPEC_EQUIVALENT', evidence: false, expected: ['분석 현황', '후보 비교', '승인·견적'] },
  { status: 'refused', verdict: null, evidence: false, expected: ['분석 현황'] },
])('shows only actions backed by the $status result ($verdict / $evidence)', ({ status, verdict, evidence, expected }) => {
  const previous = mockedRunState
  mockedRunState = { status, runId: 'run-1', result: { status, answer: '답변', evidence: evidence ? [{ document: 'sheet.pdf' }] : [],
    judgement: verdict ? { kind: 'judge', results: [{ part: 'SS34', verdict }], shown: [], unverified: [] } : {}, profile_hints: [] } }
  try {
    renderConversation()
    const menu = screen.getByRole('group', { name: '분석 결과 메뉴' })
    expect(within(menu).getAllByRole('button').map(button => button.textContent)).toEqual(expected)
    expect(within(menu).getAllByRole('button').every(button => !(button as HTMLButtonElement).disabled)).toBe(true)
  } finally { mockedRunState = previous }
})

it('does not offer approval for find candidates that were not shown in the answer', () => {
  const previous = mockedRunState
  mockedRunState = { status: 'completed', runId: 'run-1', result: { status: 'completed', answer: '확인할 후보', evidence: [],
    judgement: { kind: 'find', results: [{ part: 'hidden', verdict: 'IDENTICAL' }], shown: [], unverified: [{ part: 'shown', verdict: 'NOT_VERIFIED' }] } } }
  try {
    renderConversation()
    expect(within(screen.getByRole('group', { name: '분석 결과 메뉴' })).getAllByRole('button').map(button => button.textContent)).toEqual(['분석 현황', '후보 비교'])
  } finally { mockedRunState = previous }
})

it('links only citation numbers present in the current answer evidence', () => {
  const previous = mockedRunState
  const showEvidence = vi.fn()
  mockedRunState = { status: 'completed', runId: 'run-1', result: { status: 'completed', answer: '확인된 근거 [7], 미확인 번호 [99]',
    evidence: [{ document: 'sheet.pdf', citation_number: '7' }], judgement: {} } }
  try {
    renderConversation({ onShowEvidence: showEvidence })
    fireEvent.click(screen.getByRole('button', { name: '문서 근거 [7] 보기' }))
    expect(showEvidence).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: '문서 근거 [99] 보기' })).not.toBeInTheDocument()
  } finally { mockedRunState = previous }
})

it('waits for a saved answer result before revealing only its available actions', async () => {
  let finish!: (response: Response) => void
  const showEvidence = vi.fn()
  vi.stubGlobal('fetch', vi.fn((path: string) => path.startsWith('/api/threads/')
    ? Promise.resolve(Response.json({ id: 'saved-thread', project_id: 1, target_ref: 'D1', latest_run: { id: 'saved-run', status: 'completed', message_id: 2 },
      messages: [{ id: 2, run_id: 'saved-run', role: 'assistant', content: '저장 답변 [1]' }], next_before_message_id: null }))
    : new Promise<Response>(resolve => { finish = resolve })))
  try {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><SavedConversationPanel projectId={1} threadId="saved-thread" onRestore={vi.fn()}
      onShowActivity={vi.fn()} onShowJudgement={vi.fn()} onShowEvidence={showEvidence} onShowActions={vi.fn()} /></QueryClientProvider>)
    await screen.findByText('저장 답변 [1]')
    expect(screen.queryByRole('button', { name: '문서 근거 [1] 보기' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: '분석 결과 메뉴' })).not.toBeInTheDocument()
    await waitFor(() => expect(finish).toBeDefined())
    await act(async () => finish(Response.json({ id: 'saved-run', thread_id: 'saved-thread', message_id: 2,
      result: { status: 'completed', evidence: [{ document: 'sheet.pdf', citation_number: '1' }], judgement: {} } })))
    const menu = await screen.findByRole('group', { name: '분석 결과 메뉴' })
    expect(within(menu).getAllByRole('button').map(button => button.textContent)).toEqual(['분석 현황', '문서 근거'])
    fireEvent.click(screen.getByRole('button', { name: '문서 근거 [1] 보기' }))
    expect(showEvidence).toHaveBeenCalledTimes(1)
    fireEvent.click(within(menu).getByRole('button', { name: '문서 근거' }))
    expect(showEvidence).toHaveBeenCalledTimes(2)
  } finally { vi.unstubAllGlobals() }
})

it('checks a failed run status without submitting another question', () => {
  const previous = mockedRunState
  mockedRunState = { status: 'failed', runId: 'run-check', error: { code: 'RUN_STATUS_PENDING', message: '상태를 확인해 주세요.', requestId: 'req-1' } }
  refreshRun.mockClear(); startRun.mockClear()
  renderConversation()
  fireEvent.click(screen.getByRole('button', { name: '실행 상태 확인' }))
  expect(refreshRun).toHaveBeenCalledWith('run-check')
  expect(startRun).not.toHaveBeenCalled()
  mockedRunState = previous
})

it('keeps the input form visible next to a recoverable resume error', () => {
  const previous = mockedRunState
  mockedRunState = { status: 'requires_input', runId: 'run-input', interrupt: { missing: ['v_in_max'] },
    error: { code: 'VALIDATION_ERROR', message: '입력을 확인하세요.', requestId: 'req-1' } }
  renderConversation()
  expect(screen.getByRole('alert')).toHaveTextContent('입력을 확인하세요.')
  expect(screen.getByLabelText('입력 전원 최대 전압')).toBeInTheDocument()
  mockedRunState = previous
})

it('checks and clears a stopped saved run without starting analysis', async () => {
  let recovered = false
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    if (path === '/api/threads/saved-thread') return Response.json({ id: 'saved-thread', project_id: 1, target_ref: 'D1', messages: [], next_before_message_id: null,
      latest_run: { id: 'saved-run', status: 'running', message_id: null } })
    if (init?.method === 'POST') recovered = true
    return Response.json({ id: 'saved-run', thread_id: 'saved-thread', message_id: null, result: { status: recovered ? 'failed' : 'running' } })
  })
  vi.stubGlobal('fetch', fetcher)
  try {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><SavedConversationPanel projectId={1} threadId="saved-thread" onRestore={vi.fn()}
      onShowActivity={vi.fn()} onShowJudgement={vi.fn()} onShowEvidence={vi.fn()} onShowActions={vi.fn()} /></QueryClientProvider>)
    fireEvent.click(await screen.findByRole('button', { name: '실행 상태 새로고침' }))
    expect(await screen.findByText('이 실행은 중단된 상태입니다. 새 대화에서 다시 시작해 주세요.')).toBeInTheDocument()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST').map(([path]) => path)).toEqual(['/api/runs/saved-run/recover'])
  } finally { vi.unstubAllGlobals() }
})

it.each(['running', 'requires_input'])('uses a stop icon during %s without claiming server cancellation', status => {
  const previous = mockedRunState
  resetRun.mockClear()
  mockedRunState = { status, runId: 'run-1', stage: '분석', interrupt: { missing: ['i_max'] } }
  try {
    const busy = vi.fn()
    renderConversation({ onBusyChange: busy })
    expect(screen.getByLabelText('질문')).toBeEnabled()
    expect(screen.queryByRole('button', { name: '질문 전송' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '응답 수신 중단' })).toBeEnabled()
    const stop = screen.getByRole('button', { name: '응답 수신 중단' })
    expect(stop).toHaveAttribute('aria-busy', String(status === 'running'))
    expect(Boolean(stop.querySelector('.processing-icon'))).toBe(status === 'running')
    expect(busy).toHaveBeenCalledWith(true)
    fireEvent.click(screen.getByRole('button', { name: '응답 수신 중단' }))
    expect(resetRun).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/서버 분석은 계속될 수 있으며 다음 질문은 새 대화에서 시작합니다/)).toBeInTheDocument()
  } finally { mockedRunState = previous }
})

it('releases the workspace navigation lock when a busy conversation unmounts', () => {
  const previous = mockedRunState
  mockedRunState = { status: 'running', runId: 'run-1', stage: '분석' }
  try {
    const busy = vi.fn()
    const view = renderConversation({ onBusyChange: busy })
    expect(busy).toHaveBeenLastCalledWith(true)
    view.unmount()
    expect(busy).toHaveBeenLastCalledWith(false)
  } finally { mockedRunState = previous }
})

it.each(['completed', 'refused'])('renders %s answer links, images and HTML as text', (status) => {
  const previous = mockedRunState
  const answer = '[link](https://fixtures.invalid/leak) ![image](https://fixtures.invalid/pixel) <img src="https://fixtures.invalid/html" />'
  mockedRunState = { status, runId: 'run-1', result: { answer, refusal: '', profile_hints: [] } }
  try {
    const { container } = renderConversation()
    expect(screen.getByText(answer)).toBeInTheDocument()
    expect(container.querySelector('a, img')).toBeNull()
  } finally { mockedRunState = previous }
})

it('renders evidence coordinates exactly without inventing text', () => {
  render(<EvidencePanel evidence={[{ document: 'sheet.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }]} />)
  expect(screen.getByText('sheet.pdf')).toBeInTheDocument()
  expect(screen.getByText('2쪽 · RATINGS · VRRM')).toBeInTheDocument()
  expect(screen.getByText('인용 7')).toBeInTheDocument()
})

it('opens evidence details from supplied citation fields without fabricating a PDF', () => {
  render(<EvidencePanel evidence={[{ document: 'sheet.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: 'Absolute maximum', citation_number: '7' }]} />)
  const trigger = screen.getByRole('button', { name: /sheet\.pdf/ })
  trigger.focus()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('dialog', { name: '데이터시트 근거 상세' })
  expect(within(dialog).getByText('Absolute maximum')).toBeInTheDocument()
  expect(within(dialog).getByText('저장소에 원문이 제공되지 않은 경우 PDF 내용을 대신 표시하지 않습니다.')).toBeInTheDocument()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(trigger).toHaveFocus()
})

it('maps only backend verdict codes and always shows the disclaimer', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: true }] }} />)
  expect(screen.getByText('역할상 충분')).toBeInTheDocument()
  expect(screen.getByText('필요')).toBeInTheDocument()
  expect(screen.getByText('같은 동작은 보장하지 않습니다.')).toBeInTheDocument()
})

it('shows candidate details with explicit missing values', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34', verdict: 'NOT_VERIFIED', checks: [{ code: 'IF', value: null, unit: 'A' }] }] }} />)
  fireEvent.click(screen.getByRole('button', { name: 'SS34 상세' }))
  const dialog = screen.getByRole('dialog', { name: '후보 상세' })
  expect(within(dialog).getAllByText('MISSING')).toHaveLength(2)
  expect(within(dialog).getByText('문서로 확인 안 됨')).toBeInTheDocument()
})

it('selects a candidate and shows only its supplied datasheet coordinates', () => {
  const select = vi.fn()
  const candidate = { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const,
    checks: [{ code: 'VRRM', value: 40, unit: 'V', citation: { document: 'ss34.pdf', page: 3, table: 'Ratings', row: 'VRRM' } }] }
  render(<><JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [candidate] }} selectedIndex={0} onSelectCandidate={select} />
    <EvidencePanel evidence={[]} candidate={candidate} /></>)
  fireEvent.click(screen.getByRole('button', { name: 'SS34 후보 선택' }))
  expect(select).toHaveBeenCalledWith(candidate, 0)
  expect(screen.getByText('SS34 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('ss34.pdf')).toBeInTheDocument()
  expect(screen.getByText('3쪽 · Ratings · VRRM')).toBeInTheDocument()
})

it('keeps duplicate part numbers distinct by candidate index', () => {
  const select = vi.fn()
  const candidates = [
    { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const },
    { part: 'SS34', verdict: 'NOT_SUFFICIENT' as const },
  ]
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: candidates }} selectedIndex={1} onSelectCandidate={select} />)
  const buttons = screen.getAllByRole('button', { name: 'SS34 후보 선택' })
  expect(buttons[0]).toHaveAttribute('aria-pressed', 'false')
  expect(buttons[1]).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(buttons[1])
  expect(select).toHaveBeenCalledWith(candidates[1], 1)
})

it('requires missing values and a listed role before resuming', () => {
  const submit = vi.fn()
  render(<InterruptForm interrupt={{ missing: ['v_in_max'], role_choices: ['R01', 'R02'], question: '값을 알려 주세요.' }} busy={false} onSubmit={submit} />)
  const button = screen.getByRole('button', { name: '같은 실행 계속하기' })
  expect(button).toBeDisabled()
  fireEvent.change(screen.getByLabelText('회로 역할'), { target: { value: 'R02' } })
  fireEvent.change(screen.getByLabelText('입력 전원 최대 전압'), { target: { value: '5 V' } })
  fireEvent.click(button)
  expect(submit).toHaveBeenCalledWith({ v_in_max: '5 V' }, 'R02')
})

it('translates condition keys into Korean labels', () => {
  render(<InterruptForm interrupt={{ missing: ['v_in_max'], question: '값을 알려 주세요.' }} busy={false} onSubmit={vi.fn()} />)
  expect(screen.getByLabelText('입력 전원 최대 전압')).toBeInTheDocument()
})

it('sends conditions within the question and permits retry with the same send icon', async () => {
  startRun.mockClear()
  renderConversation()
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '5 V에서 교체 가능한가요?' } })
  expect(screen.queryByLabelText('사용 조건 (선택)')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeInTheDocument()
  expect(screen.queryByText('D5 실행 흐름')).not.toBeInTheDocument()
  expect(screen.queryByText('우측 회로 탭에서 교체할 부품을 선택하세요.')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await waitFor(() => expect(startRun).toHaveBeenCalledWith('thread-1', { question: '5 V에서 교체 가능한가요?', target_ref: 'D1', conditions: '' }))
  expect(screen.queryByText('사용 조건 정보 필요')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await waitFor(() => expect(startRun).toHaveBeenCalledTimes(2))
})

it('sends on Enter but preserves Shift+Enter and IME input without repeated sends', async () => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  startRun.mockClear()
  try {
    renderConversation({ initialQuestion: 'D1을 교체해도 되나요?' })
    const question = screen.getByLabelText('질문')
    expect(fireEvent.keyDown(question, { key: 'Enter', shiftKey: true })).toBe(true)
    expect(fireEvent.keyDown(question, { key: 'Enter', isComposing: true })).toBe(true)
    expect(fireEvent.keyDown(question, { key: 'Enter', keyCode: 229 })).toBe(true)
    expect(fireEvent.keyDown(question, { key: 'Enter', repeat: true })).toBe(false)
    expect(startRun).not.toHaveBeenCalled()
    expect(fireEvent.keyDown(question, { key: 'Enter' })).toBe(false)
    await waitFor(() => expect(startRun).toHaveBeenCalledExactlyOnceWith('thread-1', { question: 'D1을 교체해도 되나요?', target_ref: 'D1', conditions: '' }))
  } finally { mockedRunState = previous }
})

it.each([
  { status: 'idle', targetRef: 'D1', question: '' },
  { status: 'idle', targetRef: '', question: '교체할까요?' },
  { status: 'running', targetRef: 'D1', question: '교체할까요?' },
  { status: 'requires_input', targetRef: 'D1', question: '교체할까요?' },
])('does not send or stop on Enter when unavailable: $status / $targetRef / $question', ({ status, targetRef, question }) => {
  const previous = mockedRunState
  mockedRunState = { status, runId: 'run-1', stage: '판정', interrupt: { missing: [] } }
  startRun.mockClear(); resetRun.mockClear()
  try {
    renderConversation({ targetRef, initialQuestion: question })
    fireEvent.keyDown(screen.getByLabelText('질문'), { key: 'Enter' })
    expect(startRun).not.toHaveBeenCalled()
    expect(resetRun).not.toHaveBeenCalled()
  } finally { mockedRunState = previous }
})

it('disables sending while creating a thread and makes only one request', async () => {
  const previous = mockedRunState
  mockedRunState = { status: 'idle' }
  let finish!: (value: { id: string; project_id: number }) => void
  vi.mocked(createThread).mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  startRun.mockClear()
  try {
    renderConversation({ initialQuestion: 'D1 확인해줘' })
    const send = screen.getByRole('button', { name: '질문 전송' })
    expect(send.textContent).toBe('')
    fireEvent.click(send)
    expect(send).toBeDisabled()
    expect(send).toHaveAttribute('aria-busy', 'true')
    expect(send.querySelector('.processing-icon')).not.toBeNull()
    fireEvent.click(send)
    fireEvent.keyDown(screen.getByLabelText('질문'), { key: 'Enter' })
    finish({ id: 'created-thread', project_id: 1 })
    await waitFor(() => expect(startRun).toHaveBeenCalledTimes(1))
  } finally { mockedRunState = previous }
})

it('exposes evidence and candidate comparison callbacks in the final answer', () => {
  const showEvidence = vi.fn()
  const showJudgement = vi.fn()
  mockedRunState = { status: 'completed', runId: 'run-1', result: { status: 'completed', answer: '교체 가능합니다.', evidence: [{ document: 'sheet.pdf' }],
    judgement: { kind: 'find', shown: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT' }], unverified: [] } } }
  renderConversation({ onShowEvidence: showEvidence, onShowJudgement: showJudgement })
  fireEvent.click(screen.getByRole('button', { name: '문서 근거' }))
  fireEvent.click(screen.getByRole('button', { name: '후보 비교' }))
  expect(showEvidence).toHaveBeenCalledTimes(1)
  expect(showJudgement).toHaveBeenCalledTimes(1)
  mockedRunState = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
})

it('announces run progress through a polite live region', () => {
  render(<RunStatus state={{ status: 'running', runId: 'run-1', stage: '판정' }} />)
  expect(screen.getByText('판정 진행 중')).toHaveAttribute('aria-live', 'polite')
})

it('shows role names with codes and Korean value names but sends the internal keys', () => {
  const submit = vi.fn()
  render(<InterruptForm interrupt={{ missing: ['v_in_max', 'new_key'], role_choices: ['R01', 'R08'] }} busy={false} onSubmit={submit}
    roleLabels={[{ code: 'R01', name: '역극성 보호(직렬)' }]} />)
  expect(screen.getByRole('option', { name: '역극성 보호(직렬) (R01)' })).toHaveValue('R01')
  expect(screen.getByRole('option', { name: 'R08' })).toBeInTheDocument()  // 이름을 못 받은 역할은 코드 그대로
  fireEvent.change(screen.getByLabelText('회로 역할'), { target: { value: 'R01' } })
  fireEvent.change(screen.getByLabelText('입력 전원 최대 전압'), { target: { value: '12V' } })
  fireEvent.change(screen.getByLabelText('new_key'), { target: { value: '1' } })  // 모르는 이름은 내부 이름 그대로
  fireEvent.click(screen.getByRole('button', { name: '같은 실행 계속하기' }))
  expect(submit).toHaveBeenCalledWith({ v_in_max: '12V', new_key: '1' }, 'R01')
})

it('separates a system failure from a refusal answer and keeps completion neutral', () => {
  const result = { answer: '', status: 'completed', stage: '완료', question_type: 'rating', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: 'req-1' }
  const { rerender } = render(<RunStatus state={{ status: 'completed', runId: 'run-1', result }} />)
  expect(screen.getByText('분석이 끝났습니다.')).toBeInTheDocument()
  rerender(<RunStatus state={{ status: 'refused', runId: 'run-1', result: { ...result, status: 'refused' } }} />)
  expect(screen.getByText('이 질문에는 답할 수 없어 거절했습니다.')).toBeInTheDocument()
  rerender(<RunStatus state={{ status: 'failed', runId: 'run-1', error: { code: 'RUN_FAILED', message: '실행을 완료하지 못했습니다.', requestId: 'req-1' } }} />)
  expect(screen.getByText('오류로 멈췄습니다. 실행을 완료하지 못했습니다.')).toBeInTheDocument()
})

it('shows profile hints as reference apart from evidence and nothing when empty', () => {
  const { rerender } = render(<ProfileHints hints={[{ kind: 'mounting_preference', value: 'smd', text: '이 사용자는 SMD 실장을 선호한다.' }]} />)
  expect(screen.getByRole('complementary', { name: '참고(내 설정)' })).toHaveTextContent('이 사용자는 SMD 실장을 선호한다.')
  expect(screen.getByText('판정 근거가 아니라 내 설정에서 찾은 사실입니다.')).toBeInTheDocument()
  rerender(<ProfileHints hints={[]} />)
  expect(screen.queryByRole('complementary', { name: '참고(내 설정)' })).not.toBeInTheDocument()
})

const officialCitation = { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'VRRM',
  source_url: 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf', outline_page: 4 }

it('opens deduplicated official datasheet and outline pages with a conservative package boundary', () => {
  render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: true,
    checks: [{ code: 'VRRM', citation: officialCitation }, { code: 'IF', citation: { ...officialCitation, row: 'IF' } }],
    package_citation: { ...officialCitation, page: 4 },
  }} />)
  const documentLink = screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })
  expect(documentLink).toHaveAttribute('href', `${officialCitation.source_url}#page=1`)
  expect(documentLink).toHaveAttribute('target', '_blank')
  expect(documentLink).toHaveAttribute('rel', 'noreferrer noopener')
  expect(screen.getByRole('link', { name: '패키지 외형 4쪽 열기' })).toHaveAttribute('href', `${officialCitation.source_url}#page=4`)
  expect(screen.getByText('기판 변경 가능성 있음')).toBeInTheDocument()
  expect(screen.getByText('패키지가 달라질 수 있다는 뜻이며 납땜·재배선 방법을 뜻하지 않습니다.')).toBeInTheDocument()
})

it.each([undefined, 'javascript:alert(1)', 'file:///tmp/SS34.pdf', 'http://example.com/SS34.pdf'])(
  'keeps citation coordinates without a fake link for unsafe or missing source %s', source_url => {
    render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'NOT_VERIFIED',
      checks: [{ code: 'VRRM', citation: { ...officialCitation, source_url } }],
    }} />)
    expect(screen.getByText('SS34L SERIES_C2103.pdf')).toBeInTheDocument()
    expect(screen.getByText('1쪽 · MAXIMUM RATINGS · VRRM')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('패키지 변경 여부 확인 필요')).toBeInTheDocument()
  },
)

it('keeps the official document link when an outline page is missing and never promises direct replacement', () => {
  render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: false,
    checks: [{ code: 'VRRM', citation: { ...officialCitation, outline_page: null } }],
  }} />)
  expect(screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /패키지 외형/ })).not.toBeInTheDocument()
  expect(screen.getByText('동일 패키지 가능성')).toBeInTheDocument()
  expect(screen.getByText('데이터시트 패키지 기준이며 직접 교체 보증이 아닙니다.')).toBeInTheDocument()
})


it('shows the requirement, calculation, candidate value, result, and citation together', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', checks: [{ code: 'VRRM', tier: 'required', op: '>=',
      basis: '입력 최대 전압 12 V × 안전 여유 1.25', threshold: 15, value: 40, unit: 'V', condition: 'TA=25°C',
      result: 'pass', why: '후보 정격이 요구 기준 이상입니다.', citation: officialCitation }] }] }} />)
  fireEvent.click(screen.getByRole('button', { name: 'SS34L 상세' }))
  const dialog = screen.getByRole('dialog', { name: '후보 상세' })
  expect(within(dialog).getByRole('table', { name: 'SS34L 판정 조건표' })).toBeInTheDocument()
  expect(within(dialog).getByText('입력 최대 전압 12 V × 안전 여유 1.25')).toBeInTheDocument()
  expect(within(dialog).getByText('≥ 15 V')).toBeInTheDocument()
  expect(within(dialog).getByText('40 V')).toBeInTheDocument()
  expect(within(dialog).getByText('통과')).toBeInTheDocument()
  expect(within(dialog).getByRole('link', { name: 'VRRM 근거 열기' })).toHaveAttribute('href', `${officialCitation.source_url}#page=1`)
})


it('preserves the structured answer line breaks from the backend', () => {
  mockedRunState = { status: 'completed', runId: 'run-1', result: { answer: '판정\n| 조건 | 결과 |\n| VRRM | 통과 |', evidence: [], judgement: {} } }
  renderConversation()
  expect(screen.getByText(/판정\s+\| 조건 \| 결과 \|/)).toHaveClass('answer-text')
  mockedRunState = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
})
