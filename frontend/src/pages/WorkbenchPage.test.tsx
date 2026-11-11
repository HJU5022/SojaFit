import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('shows processing on the active session and clears it on completion despite a stale running list', async () => {
  let created = false
  let finish!: () => void
  const result = { status: 'completed', answer: '확인했습니다.', judgement: {}, evidence: [], interrupt: {}, profile_hints: [] }
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') { created = true; return Response.json({ id: 'working-thread', project_id: 11 }, { status: 201 }) }
    if (path === '/api/projects/11/threads') return Response.json(created ? [{ id: 'working-thread', title: '진행 표시 확인', status: 'running' }] : [])
    if (path === '/api/threads/working-thread/runs') return new Response(new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: run_started\ndata: {"run_id":"working-run"}\n\nevent: status\ndata: {"stage":"근거 확인"}\n\n'))
      finish = () => { controller.enqueue(new TextEncoder().encode(`event: completed\ndata: ${JSON.stringify(result)}\n\n`)); controller.close() }
    } }))
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '진행 표시 확인' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  const session = await screen.findByTitle('진행 표시 확인')
  await waitFor(() => expect(session).toHaveAttribute('aria-busy', 'true'))
  expect(session.querySelector('.processing-icon')).not.toBeNull()
  expect(session).toHaveAttribute('aria-current', 'true')
  await act(async () => finish())
  await waitFor(() => expect(session).toHaveAttribute('aria-busy', 'false'))
  expect(session.querySelector('.processing-icon')).toBeNull()
  expect(session.querySelector('.workspace-current-dot')).not.toBeNull()
  expect(screen.getByRole('button', { name: '질문 전송' })).toHaveAttribute('aria-busy', 'false')
})
it('locks project creation and target navigation while the agent waits for more input', async () => {
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') return Response.json({ id: 'waiting-thread', project_id: 11 }, { status: 201 })
    if (path === '/api/threads/waiting-thread/runs') return new Response('event: run_started\ndata: {"run_id":"waiting-run"}\n\nevent: requires_input\ndata: {"interrupt":{"missing":["v_in_max"],"question":"최대 전압을 알려주세요."}}\n\n')
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  const project = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1을 바꿔도 되나요?' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await screen.findByRole('button', { name: '응답 수신 중단' })
  expect(project).toBeDisabled()
  expect(screen.getByRole('button', { name: '프로젝트 추가' })).toBeDisabled()
})
it('keeps a saved conversation target locked and clears it when selecting another project', async () => {
  network(path => Response.json(path === '/api/projects' ? [summary(first), summary(second)] : path === '/api/projects/11' ? first : path === '/api/projects/12' ? second
    : path === '/api/threads/saved' ? { id: 'saved', project_id: 11, target_ref: 'D1', latest_run: null, messages: [], next_before_message_id: null } : []))
  openWorkbench('/app?projectId=11&threadId=saved')
  fireEvent.click(await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` }))
  const dialog = screen.getByRole('dialog', { name: '내 프로젝트' })
  const select = await within(dialog).findByLabelText('분석할 부품')
  expect(select).toBeDisabled()
  await waitFor(() => expect(select).toHaveValue('D1'))
  fireEvent.click(within(dialog).getByRole('button', { name: second.name }))
  await waitFor(() => expect(within(dialog).getByLabelText('분석할 부품')).toBeEnabled())
  const nextSelect = within(dialog).getByLabelText('분석할 부품')
  expect(nextSelect).toHaveValue('')
  expect(within(nextSelect).queryByRole('option', { name: /D1/ })).not.toBeInTheDocument()
  fireEvent.change(nextSelect, { target: { value: 'D2' } })
  expect(screen.getByLabelText('현재 경로')).not.toHaveTextContent('threadId=')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=D2')
})

it('does not offer a target when the selected project has no server-provided parts', async () => {
  network(path => Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? { ...first, connections: { parts: [], nets: [] } } : []))
  openWorkbench('/app?projectId=11')
  fireEvent.click(await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` }))
  const dialog = screen.getByRole('dialog', { name: '내 프로젝트' })
  expect(within(dialog).getByLabelText('분석할 부품')).toBeDisabled()
  expect(within(dialog).getByText('선택할 수 있는 부품이 없습니다.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeDisabled()
})
it('selects the target in the project header dialog without setup controls or copy in the conversation', async () => {
  const calls: string[] = []
  network((path, init) => { calls.push(init.method ?? 'GET'); return Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : []) })
  openWorkbench('/app?projectId=11')
  const trigger = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  expect(screen.queryByLabelText('질문 영역의 대상 부품')).not.toBeInTheDocument()
  expect(screen.queryByText('대체 가능성 분석 흐름')).not.toBeInTheDocument()
  expect(screen.queryByText('회로 입력 확인')).not.toBeInTheDocument()
  expect(screen.queryByText('대상 부품을 선택하세요')).not.toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeDisabled()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('dialog', { name: '내 프로젝트' })
  const select = await within(dialog).findByLabelText('분석할 부품')
  expect(within(select).getByRole('option', { name: 'D1 · 1N4001' })).toBeInTheDocument()
  fireEvent.change(select, { target: { value: 'D1' } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(trigger).toHaveTextContent('D1 · 1N4001')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=D1')
  expect(screen.getByLabelText('질문')).toBeEnabled()
  expect(calls.every(method => method === 'GET')).toBe(true)
})

it('continues from project creation to selecting its server-provided target without starting analysis', async () => {
  let created = false
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'POST') { writes.push(path); created = true; return Response.json(first, { status: 201 }) }
    return Response.json(path === '/api/projects' ? created ? [summary(first)] : [] : path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : [])
  })
  openWorkbench()
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 추가' }))
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: first.name } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  const dialog = await screen.findByRole('dialog', { name: '내 프로젝트' })
  fireEvent.change(await within(dialog).findByLabelText('분석할 부품'), { target: { value: 'C1' } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` })).toHaveTextContent('C1 · 100uF')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=C1')
  expect(writes).toEqual(['/api/projects'])
})
it('shows the selected part above the conversation without a duplicate badge inside it', async () => {
  network(path => Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : []))
  openWorkbench('/app?projectId=11&targetRef=C1')
  await screen.findByLabelText('질문')
  const badge = screen.getByTitle('선택한 부품')
  expect(badge).toHaveTextContent('C1')
  expect(badge.parentElement).toHaveClass('analysis-heading-actions')
  expect(document.querySelector('.conversation-panel .target-badge')).toBeNull()
})
it('shows the signed-in email in the header and account menu without a global run badge', () => {
  network(() => Response.json([]))
  openWorkbench('/app', { user_id: 7, role: 'user', email: 'signed-in@example.test' })
  const header = screen.getByRole('banner')
  const account = within(header).getByRole('button', { name: 'signed-in@example.test' })
  expect(account).toHaveAttribute('title', 'signed-in@example.test')
  expect(within(header).queryByText('분석 대기')).not.toBeInTheDocument()
  expect(within(header).queryByText('사용자 7')).not.toBeInTheDocument()
  fireEvent.click(account)
  expect(within(screen.getByRole('menu', { name: '계정 메뉴' })).getByText('signed-in@example.test')).toBeInTheDocument()
})
it('pins conversations in browser storage, restores order and isolates each project', async () => {
  const key = 'sojafit-pinned-threads:7:11'
  localStorage.removeItem(key)
  network(path => Response.json(path === '/api/projects' ? [summary(first), summary(second)] : path === '/api/projects/11' ? first : path === '/api/projects/12' ? second : path.endsWith('/threads') ? [{ id: 'new', title: '새 기록' }, { id: 'old', title: '오래된 기록' }] : []))
  try {
    openWorkbench('/app?projectId=11', { user_id: 7, role: 'user' })
    const list = screen.getByRole('list', { name: '이전 대화' })
    const actions = await screen.findByRole('group', { name: '오래된 기록 관리' })
    fireEvent.click(within(actions).getByRole('button', { name: '대화 고정' }))
    expect(within(list).getAllByRole('listitem')[0]).toHaveTextContent('오래된 기록')
    expect(JSON.parse(localStorage.getItem(key)!)).toEqual(['old'])
    cleanup()
    openWorkbench('/app?projectId=11', { user_id: 7, role: 'user' })
    await screen.findByRole('button', { name: '대화 고정 해제' })
    fireEvent.click(screen.getByRole('button', { name: second.name }))
    await screen.findByRole('group', { name: '오래된 기록 관리' })
    expect(screen.queryByRole('button', { name: '대화 고정 해제' })).not.toBeInTheDocument()
    expect(screen.getByRole('list', { name: '이전 대화' }).firstChild).toHaveTextContent('새 기록')
    cleanup()
    openWorkbench('/app?projectId=11', { user_id: 8, role: 'user' })
    await screen.findByRole('group', { name: '오래된 기록 관리' })
    expect(screen.queryByRole('button', { name: '대화 고정 해제' })).not.toBeInTheDocument()
  } finally { localStorage.removeItem(key) }
})

it('keeps pinning usable with a clear notice when browser storage is blocked', async () => {
  network(path => Response.json(path === '/api/projects/11' ? first : path === '/api/projects/11/threads' ? [{ id: 'storage-test', title: '저장 제한 기록' }] : []))
  const blocked = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('storage blocked') })
  try {
    openWorkbench('/app?projectId=11')
    const actions = await screen.findByRole('group', { name: '저장 제한 기록 관리' })
    fireEvent.click(within(actions).getByRole('button', { name: '대화 고정' }))
    expect(within(screen.getByRole('navigation', { name: '작업 메뉴' })).getByRole('status')).toHaveTextContent('고정 설정을 저장하지 못했습니다.')
    expect(within(actions).getByRole('button', { name: '대화 고정 해제' })).toBeInTheDocument()
  } finally { blocked.mockRestore() }
})

it('confirms deletion, keeps failed records, then clears only the selected conversation after success', async () => {
  let deleted = false, fail = true
  const deletes: string[] = []
  network((path, init) => {
    if (init.method === 'DELETE') { deletes.push(path); if (fail) return failure('CONFLICT', '분석 중인 대화입니다.', 409); deleted = true; return new Response(null, { status: 204 }) }
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads') return Response.json(deleted ? [{ id: 'other', title: '남길 기록' }] : [{ id: 'current', title: '삭제할 기록' }, { id: 'other', title: '남길 기록' }])
    if (path === '/api/threads/current') return Response.json({ id: 'current', project_id: 11, target_ref: 'D1', messages: [], latest_run: null, next_before_message_id: null })
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1&threadId=current')
  const actions = await screen.findByRole('group', { name: '삭제할 기록 관리' })
  fireEvent.click(within(actions).getByRole('button', { name: '대화 삭제' }))
  expect(deletes).toEqual([])
  let dialog = screen.getByRole('dialog', { name: '대화 삭제' })
  expect(dialog).toHaveTextContent('연결된 승인·견적·사례')
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
  expect(deletes).toEqual([])
  fireEvent.click(within(actions).getByRole('button', { name: '대화 삭제' }))
  dialog = screen.getByRole('dialog', { name: '대화 삭제' })
  fireEvent.click(within(dialog).getByRole('button', { name: '삭제 확인' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('분석 중인 대화입니다.')
  expect(screen.getByRole('button', { name: /삭제할 기록/ })).toBeInTheDocument()
  fail = false
  fireEvent.click(within(dialog).getByRole('button', { name: '삭제 확인' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  await waitFor(() => expect(screen.getByLabelText('현재 경로')).not.toHaveTextContent('threadId'))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11')
  expect(screen.getByLabelText('질문')).toHaveValue('')
  expect(screen.getByRole('button', { name: '남길 기록' })).toBeInTheDocument()
  expect(deletes).toEqual(['/api/threads/current', '/api/threads/current'])
})
it('shows two saved projects in server order and reveals the third without creating anything', async () => {
  const third = { ...first, id: 13, name: '세 번째 프로젝트' }
  const methods: string[] = []
  network((path, init) => {
    methods.push(init.method ?? 'GET')
    if (path === '/api/projects') return Response.json([summary(second), summary(first), summary(third)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/13') return Response.json(third)
    return Response.json([])
  })
  openWorkbench('/app?projectId=11')
  const list = screen.getByRole('list', { name: '저장된 프로젝트' })
  await within(list).findByRole('button', { name: first.name })
  expect(within(list).getAllByRole('button').map(button => button.textContent)).toEqual([second.name, first.name])
  expect(within(list).queryByRole('button', { name: third.name })).not.toBeInTheDocument()
  const more = screen.getByRole('button', { name: '더보기 (1)' })
  expect(more).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(more)
  expect(within(list).getAllByRole('button').map(button => button.textContent)).toEqual([second.name, first.name, third.name])
  fireEvent.click(within(list).getByRole('button', { name: third.name }))
  expect(await screen.findByRole('heading', { name: third.name })).toBeInTheDocument()
  expect(within(list).getByRole('button', { name: third.name })).toHaveAttribute('aria-current', 'true')
  fireEvent.click(screen.getByRole('button', { name: '접기' }))
  expect(within(list).queryByRole('button', { name: third.name })).not.toBeInTheDocument()
  const newChat = screen.getByRole('button', { name: '새 대화' })
  expect(newChat.textContent).toBe('')
  fireEvent.click(newChat)
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=13')
  expect(methods.every(method => method === 'GET')).toBe(true)
})

it('loads saved conversation and its result with GET requests only, then returns to a fresh draft', async () => {
  const calls: string[] = []
  network((path, init) => {
    calls.push(`${init.method ?? 'GET'} ${path}`)
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads') return Response.json([{ id: 'history-thread', project_id: 11 }])
    if (path === '/api/threads/history-thread') return Response.json({ id: 'history-thread', project_id: 11, title: '저장된 질문', target_ref: 'D1', target_locked: true,
      latest_run: { id: 'saved-run', status: 'completed', message_id: 2 }, messages: [{ id: 1, run_id: 'saved-run', role: 'user', content: '저장된 질문', created_at: '' }, { id: 2, run_id: 'saved-run', role: 'assistant', content: '저장된 답변', created_at: '' }], next_before_message_id: null })
    if (path === '/api/runs/saved-run') return Response.json({ id: 'saved-run', thread_id: 'history-thread', message_id: 2,
      result: { status: 'completed', answer: '저장된 답변', judgement: {}, evidence: [{ document: 'saved.pdf', page: 2, table: '', row: '', section: '', citation_number: '1' }], interrupt: {} } })
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  expect(await screen.findByRole('button', { name: first.name })).toHaveAttribute('aria-current', 'true')
  fireEvent.click(await screen.findByRole('button', { name: /대화 history-/ }))
  expect(await screen.findByText('저장된 질문')).toBeInTheDocument()
  expect(await screen.findByText('저장된 답변')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '저장된 대화' })).not.toBeInTheDocument()
  expect(screen.getByRole('region', { name: '저장된 대화' })).toBeInTheDocument()
  const target = await screen.findByTitle('선택한 부품')
  expect(target).toHaveTextContent('D1')
  await waitFor(() => expect(target.nextElementSibling).toBe(screen.getByRole('button', { name: '결과 보기' })))
  expect(within(screen.getByRole('region', { name: '저장된 대화' })).queryByText('D1', { exact: true })).not.toBeInTheDocument()
  const current = screen.getByRole('button', { name: /대화 history-/ })
  expect(current).toHaveAttribute('aria-current', 'true')
  expect(current).toHaveAttribute('title', '대화 history-')
  expect(current).not.toHaveTextContent('저장된 대화 열기')
  fireEvent.click(screen.getByRole('button', { name: first.name }))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('threadId=history-thread')
  expect(screen.getByText('저장된 답변')).toBeInTheDocument()
  expect(screen.queryByLabelText('질문')).not.toBeInTheDocument()
  fireEvent.click(within(screen.getByRole('group', { name: '분석 결과 메뉴' })).getByRole('button', { name: '문서 근거' }))
  expect(await screen.findByText('saved.pdf')).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('threadId=history-thread')
  fireEvent.click(screen.getByRole('button', { name: /대화 history-/ }))
  expect(screen.getByText('saved.pdf')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }))
  expect(await screen.findByLabelText('질문')).toHaveValue('')
  expect(calls.every(path => path.startsWith('GET '))).toBe(true)
})

it('rejects history belonging to a different project without loading its run', async () => {
  const calls: string[] = []
  network(path => {
    calls.push(path)
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path.startsWith('/api/threads/')) return Response.json({ id: 'foreign', project_id: 12, latest_run: { id: 'foreign-run' }, messages: [] })
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&threadId=foreign')
  expect(await screen.findByRole('alert')).toHaveTextContent('선택한 프로젝트의 대화가 아닙니다.')
  expect(calls.some(path => path.includes('/api/runs/'))).toBe(false)
})

it('keeps the second conversation result when a previous run arrives late', async () => {
  let finishA!: (response: Response) => void
  let requestedA = false
  const saved = (thread: string, run: string, name: string) => ({ id: thread, project_id: 11, title: name, target_ref: 'D1', target_locked: true,
    latest_run: { id: run, status: 'completed', message_id: 2 }, messages: [{ id: 2, run_id: run, role: 'assistant', content: name, created_at: '' }], next_before_message_id: null })
  const result = (thread: string, run: string, part: string) => ({ id: run, thread_id: thread, message_id: 2, result: { status: 'completed', answer: part, evidence: [],
    judgement: { kind: 'judge', roles: [], results: [{ part, verdict: 'ROLE_SUFFICIENT' }], shown: [], unverified: [] }, interrupt: {} } })
  network(path => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads') return Response.json([{ id: 'thread-a', project_id: 11 }, { id: 'thread-b', project_id: 11 }])
    if (path === '/api/threads/thread-a') return Response.json(saved('thread-a', 'run-a', '이전 답변'))
    if (path === '/api/threads/thread-b') return Response.json(saved('thread-b', 'run-b', '현재 답변'))
    if (path === '/api/runs/run-a') { requestedA = true; return new Promise<Response>(resolve => { finishA = resolve }) }
    if (path === '/api/runs/run-b') return Response.json(result('thread-b', 'run-b', 'SS34'))
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&threadId=thread-a')
  await waitFor(() => expect(requestedA).toBe(true))
  fireEvent.click(await screen.findByRole('button', { name: /대화 thread-b/ }))
  await screen.findByText('현재 답변')
  expect(await screen.findByRole('cell', { name: 'SS34' })).toBeInTheDocument()
  await act(async () => finishA(Response.json(result('thread-a', 'run-a', '1N5819'))))
  expect(screen.getByRole('cell', { name: 'SS34' })).toBeInTheDocument()
  expect(screen.queryByRole('cell', { name: '1N5819' })).not.toBeInTheDocument()
  expect(screen.queryByText('이전 답변')).not.toBeInTheDocument()
})

it('loads older messages and selects that message run while rejecting mismatched run ownership', async () => {
  const calls: string[] = []
  network((path, init) => {
    calls.push(`${init.method ?? 'GET'} ${path}`)
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path.startsWith('/api/threads/history')) {
      const older = path.includes('before_message_id')
      return Response.json({ id: 'history', project_id: 11, target_ref: 'D1', latest_run: { id: 'new-run', status: 'completed', message_id: 4 },
        messages: [{ id: older ? 2 : 4, run_id: older ? 'old-run' : 'new-run', role: 'assistant', content: older ? '과거 답변' : '최신 답변', created_at: '' }], next_before_message_id: older ? null : 4 })
    }
    if (path.startsWith('/api/runs/')) return Response.json({ id: path.split('/').at(-1), thread_id: path.endsWith('old-run') ? 'another-thread' : 'history', message_id: 4,
      result: { status: 'completed', answer: '결과', judgement: {}, evidence: [], interrupt: {} } })
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&threadId=history')
  fireEvent.click(await screen.findByRole('button', { name: '이전 메시지 더 보기' }))
  const older = await screen.findByRole('article', { name: '2번 에이전트 메시지' })
  fireEvent.click(within(older).getByRole('button', { name: '분석 결과 확인' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('선택한 대화의 분석 결과가 아닙니다.')
  expect(calls).toContain('GET /api/threads/history?before_message_id=4')
  expect(calls).toContain('GET /api/runs/old-run')
  expect(calls.every(call => call.startsWith('GET '))).toBe(true)
})

it('starts a fresh thread rather than silently using the first history item', async () => {
  const starts: string[] = []
  let created = 0
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') { created++; return Response.json({ id: 'fresh-thread', project_id: 11 }, { status: 201 }) }
    if (path === '/api/projects/11/threads') return Response.json([{ id: 'history-thread', project_id: 11 }])
    if (path.startsWith('/api/threads/')) { starts.push(path); return new Response('event: run_started\ndata: {"run_id":"r1"}\n\nevent: completed\ndata: {"status":"completed","answer":"확인 완료","judgement":{},"evidence":[],"price_parts":[],"interrupt":{},"refusal":"","request_id":"req"}\n\n') }
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: /대화 history-/ })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1 확인해줘' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await screen.findByText('확인 완료')
  expect(created).toBe(1)
  expect(starts).toEqual(['/api/threads/fresh-thread/runs'])
  expect(screen.getByRole('group', { name: '분석 결과 메뉴' })).toBeInTheDocument()
  fireEvent.click(within(screen.getByRole('group', { name: '분석 결과 메뉴' })).getByRole('button', { name: '분석 현황' }))
  expect(screen.getByRole('tab', { name: '진행 기록' })).toHaveAttribute('aria-selected', 'true')
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }))
  await waitFor(() => expect(screen.queryByText('확인 완료')).not.toBeInTheDocument())
  expect(created).toBe(1)
})

it('opens the new workspace without an entry modal before a project is selected', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.getByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
  expect(screen.getByRole('list', { name: '저장된 프로젝트' })).toBeEmptyDOMElement()
  expect(screen.getByRole('button', { name: '새 대화' })).toBeDisabled()
  expect(screen.getByLabelText('질문')).toBeDisabled()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: /부품을 바꾸기 전에/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '프로젝트 만들기' })).not.toBeInTheDocument()
  const projectHeading = screen.getByRole('heading', { name: '현재 프로젝트' }).parentElement!
  const addProject = within(projectHeading).getByRole('button', { name: '프로젝트 추가' })
  expect(addProject).toBeEnabled()
  fireEvent.click(addProject)
  expect(screen.getByRole('dialog', { name: '프로젝트 만들기' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('selects an existing project from the empty workspace sidebar without posting an analysis', async () => {
  const calls: string[] = []
  network((path, init) => {
    calls.push(init.method ?? 'GET')
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/12') return Response.json(second)
    return Response.json([])
  })
  openWorkbench()
  expect(await screen.findByRole('button', { name: second.name })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /더보기/ })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: second.name }))
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(calls.every(method => method === 'GET')).toBe(true)
})

it('creates a project from the new workspace and starts with an empty analysis draft', async () => {
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects' && init.method === 'POST') return Response.json(first, { status: 201 })
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects') return Response.json([summary(first)])
    return Response.json([])
  })
  openWorkbench()
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 추가' }))
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '내 전원 회로' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  expect(await screen.findByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toHaveValue('')
  expect(screen.queryByLabelText('사용 조건 (선택)')).not.toBeInTheDocument()
})
it('does not let delayed detail overwrite a newly selected project', async () => {
  let finish!: (response: Response) => void
  network((path) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return new Promise(resolve => { finish = resolve })
    return Response.json(second)
  })
  openWorkbench('/app?projectId=11')
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' }))
  fireEvent.click(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: second.name }))
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  await act(async () => finish(Response.json(first)))
  expect(screen.queryByRole('heading', { name: first.name })).not.toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
})
it('does not select delayed creation after the user switches projects', async () => {
  let finish!: (response: Response) => void
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects' && init.method === 'POST') return new Promise(resolve => { finish = resolve })
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    return Response.json(path.endsWith('/11') ? first : second)
  })
  openWorkbench('/app?projectId=11')
  fireEvent.click(screen.getAllByRole('button', { name: '프로젝트 추가' })[0])
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '늦은 생성' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' }))
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  await act(async () => finish(Response.json(first, { status: 201 })))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
})
it.each(['missing', 'foreign'])('shows the common safe error for a %s project', async () => {
  network(path => path === '/api/projects/99' ? failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404) : Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench('/app?projectId=99&targetRef=D1')
  expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 찾을 수 없습니다. (요청 ID: req-test)')
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
})

it('exposes keyboard-operable result tabs and a labelled project drawer', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const toggle = screen.getByRole('button', { name: '프로젝트 열기' })
  toggle.focus()
  fireEvent.click(toggle)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  await waitFor(() => expect(toggle).toHaveFocus())
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  const judgement = screen.getByRole('tab', { name: '후보 비교' })
  fireEvent.click(judgement)
  expect(judgement).toHaveAttribute('aria-selected', 'true')
})

it('organizes the workbench as a functional rail, analysis surface, and adjustable information console', async () => {
  vi.stubGlobal('innerWidth', 1440)
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : path === '/api/projects' ? [summary(first)] : []))
  openWorkbench('/app?projectId=11')
  expect(screen.getByRole('navigation', { name: '작업 메뉴' })).toBeInTheDocument()
  expect(screen.getByRole('main', { name: '분석 대화 작업면' })).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: '회로와 분석 정보' })).toBeInTheDocument()
  expect(screen.queryByText('회로 및 분석 정보', { exact: true })).not.toBeInTheDocument()
  expect(screen.queryByRole('tab', { name: '회로' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  expect(screen.getByRole('tab', { name: '회로' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: '진행 기록' })).toBeInTheDocument()
  expect(screen.queryByText('회로 및 분석 정보', { exact: true })).not.toBeInTheDocument()
  expect(screen.queryByRole('slider', { name: '정보 패널 너비' })).not.toBeInTheDocument()
  const handle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  expect(handle).toHaveAttribute('aria-valuemax', '480')
  fireEvent.pointerDown(handle, { clientX: 900, pointerId: 3 })
  fireEvent.pointerMove(handle, { clientX: 500, pointerId: 3 })
  fireEvent.pointerUp(handle, { pointerId: 3 })
  expect(handle).toHaveAttribute('aria-valuenow', '480')
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 접기' }))
  expect(screen.getByRole('button', { name: '정보 패널 펼치기' })).toBeInTheDocument()
})

it('shows the left rail as a named work menu by default', () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const rail = screen.getByRole('navigation', { name: '작업 메뉴' })
  expect(rail).toHaveClass('expanded')
  expect(within(rail).getByText('작업 메뉴')).toBeVisible()
  expect(within(rail).getByRole('heading', { name: '현재 프로젝트' })).toBeVisible()
  expect(within(rail).getByRole('heading', { name: '이전 대화' })).toBeVisible()
  for (const name of ['프로젝트', '회로', '근거', '후보 비교', '승인·견적']) {
    expect(within(rail).queryByRole('button', { name })).not.toBeInTheDocument()
  }
  expect(within(rail).queryByRole('button', { name: '분석 대화' })).not.toBeInTheDocument()
  expect(within(rail).queryByRole('button', { name: '계정' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '계정' }))
  expect(screen.getByRole('menu', { name: '계정 메뉴' })).toBeInTheDocument()
  expect(screen.getByRole('menuitem', { name: '로그인' })).toBeInTheDocument()
})

it('opens the project picker from the current project name', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : path === '/api/projects' ? [summary(first)] : []))
  openWorkbench('/app?projectId=11')
  const projectName = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.click(projectName)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
})

it('resizes both desktop side panels by dragging their borders', () => {
  vi.stubGlobal('innerWidth', 1440)
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const leftHandle = screen.getByRole('separator', { name: '작업 메뉴 너비 조절' })
  fireEvent.pointerDown(leftHandle, { clientX: 220, pointerId: 1 })
  fireEvent.pointerMove(leftHandle, { clientX: 280, pointerId: 1 })
  fireEvent.pointerUp(leftHandle, { pointerId: 1 })
  expect(leftHandle).toHaveAttribute('aria-valuenow', '268')

  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  const rightHandle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  fireEvent.pointerDown(rightHandle, { clientX: 900, pointerId: 2 })
  fireEvent.pointerMove(rightHandle, { clientX: 850, pointerId: 2 })
  fireEvent.pointerUp(rightHandle, { pointerId: 2 })
  expect(rightHandle).toHaveAttribute('aria-valuenow', '410')
  vi.stubGlobal('innerWidth', 1200)
  fireEvent(window, new Event('resize'))
  expect(rightHandle).toHaveAttribute('aria-valuemax', '372')
  expect(rightHandle).toHaveAttribute('aria-valuenow', '372')
})

it('searches only loaded projects and current circuit parts', async () => {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json(second)
  })
  openWorkbench('/app?projectId=11')
  const search = await screen.findByRole('searchbox', { name: '프로젝트 또는 부품 찾기' })
  fireEvent.change(search, { target: { value: 'D1' } })
  fireEvent.click(within(screen.getByRole('listbox', { name: '검색 결과' })).getByRole('option', { name: /D1.*1N4001/ }))
  expect(screen.getByTitle('선택한 부품')).toHaveTextContent('D1')
})

it('guides the user from project selection to approval and keeps target controls in the project dialog', async () => {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json([])
  })
  openWorkbench('/app?projectId=11')
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })).toBeInTheDocument()
  expect(screen.getByText('대상 선택')).toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeInTheDocument()
  expect(screen.getByText('결과 검토')).toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  expect(screen.getByRole('tab', { name: '승인·견적' })).toBeInTheDocument()
  expect(screen.queryByLabelText('질문 영역의 대상 부품')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` }))
  expect(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByLabelText('분석할 부품')).toBeInTheDocument()
})

it('uses a single actions destination and accessible tab relationships', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.queryByRole('button', { name: '승인·견적' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '승인 사례·이력' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  const tabs = screen.getAllByRole('tab')
  expect(tabs[0]).toHaveAttribute('aria-controls', 'panel-circuit')
  expect(screen.getByRole('tabpanel', { name: '회로' })).toHaveAttribute('aria-labelledby', tabs[0].id)
  fireEvent.keyDown(tabs[0], { key: 'ArrowRight' })
  expect(tabs[1]).toHaveFocus()
})

it('exposes search results as a keyboard-operable listbox', async () => {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    return Response.json(first)
  })
  openWorkbench('/app?projectId=11')
  const search = await screen.findByRole('searchbox', { name: '프로젝트 또는 부품 찾기' })
  fireEvent.change(search, { target: { value: '회로' } })
  expect(screen.getByRole('listbox', { name: '검색 결과' })).toBeInTheDocument()
  const options = within(screen.getByRole('listbox', { name: '검색 결과' })).getAllByRole('option')
  expect(options[0]).toHaveAttribute('tabIndex', '0')
  fireEvent.keyDown(search, { key: 'ArrowDown' })
  expect(options[0]).toHaveFocus()
  fireEvent.keyDown(options[0], { key: 'ArrowDown' })
  expect(options[1]).toHaveFocus()
  fireEvent.keyDown(options[1], { key: 'ArrowUp' })
  expect(options[0]).toHaveFocus()
  fireEvent.keyDown(options[0], { key: 'Escape' })
  expect(search).toHaveFocus()
  expect(screen.queryByRole('listbox', { name: '검색 결과' })).not.toBeInTheDocument()
})

it('connects project, role, run, candidate, and citation API data without a fixture fallback', async () => {
  const result = {
    answer: '판정 완료', status: 'completed', stage: '완료', question_type: 'judge', evidence: [], price_parts: [], refusal: '', interrupt: {}, request_id: 'req-run',
    judgement: { kind: 'judge', roles: ['R01'], role_evidence: ['D1.K → GND'], shown: [], unverified: [], capped: false,
      results: [{ part: 'SS34', role: 'R01', verdict: 'ROLE_SUFFICIENT', checks: [{ code: 'VRRM', value: 40, unit: 'V', condition: '입력 최대 전압', citation: { document: 'ss34.pdf', page: 3, table: 'Ratings', row: 'VRRM' } }] }] },
  }
  network((path, init) => {
    if (path === '/api/judge/roles') return Response.json([{ code: 'R01', name: '역극성 보호(직렬)' }])
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') return Response.json({ id: 'thread-1', project_id: 11 }, { status: 201 })
    if (path === '/api/projects/11/threads') return Response.json([])
    if (path === '/api/threads/thread-1/runs') return new Response([
      'event: run_started', 'data: {"run_id":"run-1","request_id":"req-run"}', '',
      'event: completed', `data: ${JSON.stringify(result)}`, '', '',
    ].join('\n'))
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByText('D1 / 1N4001')
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '입력 최대 12 V에서 D1을 SS34로 바꿔도 되나요?' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  expect(await screen.findByText('역극성 보호(직렬)')).toBeInTheDocument()
  expect(within(screen.getByLabelText('개념도 사용 조건')).getByText('판정 결과에서 확인된 사용 조건이 없습니다.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '후보 비교' }))
  fireEvent.click(await screen.findByRole('button', { name: 'SS34 후보 선택' }))
  fireEvent.click(screen.getByRole('tab', { name: '근거' }))
  expect(screen.getByText('SS34 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('ss34.pdf')).toBeInTheDocument()
})
