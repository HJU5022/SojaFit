import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network as mockNetwork } from '../test/network'
import { demo, first, second, summary, openWorkbench, showDetail } from '../test/projects'

function network(handler: Parameters<typeof mockNetwork>[0]) {
  mockNetwork((path, init) => path === '/api/auth/demo' ? Response.json({ enabled: true }) : handler(path, init))
}

afterEach(() => vi.unstubAllGlobals())
it('keeps the half-width cap in sync with rail collapse and keyboard resizing', () => {
  vi.stubGlobal('innerWidth', 1440)
  network(() => Response.json([]))
  openWorkbench()
  showDetail('회로')
  const handle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  expect(handle).toHaveAttribute('aria-valuemax', '616')
  fireEvent.click(screen.getByRole('button', { name: '작업 메뉴 접기' }))
  expect(handle).toHaveAttribute('aria-valuemax', '691')
  for (let i = 0; i < 50; i++) fireEvent.keyDown(handle, { key: 'ArrowLeft' })
  expect(handle).toHaveAttribute('aria-valuenow', '691')
  fireEvent.click(screen.getByRole('button', { name: '작업 메뉴 펼치기' }))
  expect(handle).toHaveAttribute('aria-valuenow', '616')
  fireEvent.keyDown(handle, { key: 'ArrowRight' })
  expect(handle).toHaveAttribute('aria-valuenow', '606')
})
it('opens basic help without writes or losing the draft and restores focus on close', async () => {
  const writes: string[] = []
  network((_, init) => { if (init.method && init.method !== 'GET') writes.push(init.method); return Response.json([]) })
  openWorkbench()
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '도움말 뒤에도 유지할 질문' } })
  const help = screen.getByRole('button', { name: '도움말' })
  help.focus(); fireEvent.click(help)
  const dialog = await screen.findByRole('dialog', { name: '기본 사용방법' })
  for (const title of ['프로젝트 등록', '분석할 부품 선택', '새 대화 시작', '질문 보내기', '결과 확인', '응답이 지연될 때']) expect(within(dialog).getByRole('heading', { name: title })).toBeInTheDocument()
  expect(dialog).toHaveTextContent('Shift+Enter')
  expect(dialog).toHaveTextContent('질문과 함께 읽어 설명·비교에 사용합니다')
  const close = within(dialog).getByRole('button', { name: '닫기' })
  expect(close).toHaveFocus()
  fireEvent.keyDown(close, { key: 'Tab' })
  expect(close).toHaveFocus()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(help).toHaveFocus()
  fireEvent.click(help)
  fireEvent.click(within(screen.getByRole('dialog', { name: '기본 사용방법' })).getByRole('button', { name: '닫기' }))
  expect(help).toHaveFocus()
  expect(screen.getByLabelText('질문')).toHaveValue('도움말 뒤에도 유지할 질문')
  expect(writes).toEqual([])
})
it('keeps a question typed before project selection through project and target preparation', async () => {
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    return Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : [])
  })
  openWorkbench()
  const question = screen.getByLabelText('질문')
  expect(question).toBeEnabled()
  fireEvent.change(question, { target: { value: '먼저 작성한 질문' } })
  fireEvent.keyDown(question, { key: 'Enter' })
  expect(writes).toEqual([])
  fireEvent.click(await screen.findByRole('button', { name: first.name }))
  await waitFor(() => expect(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` })).toBeEnabled())
  expect(screen.getByLabelText('질문')).toHaveValue('먼저 작성한 질문')
  fireEvent.click(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` }))
  fireEvent.change(await screen.findByLabelText('분석할 부품'), { target: { value: 'D1' } })
  expect(screen.getByLabelText('질문')).toHaveValue('먼저 작성한 질문')
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeEnabled()
  expect(writes).toEqual([])
})
it('creates a session on plus, focuses the composer and reuses it for the first question', async () => {
  let creates = 0
  const runs: string[] = []
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads') {
      if (init.method === 'POST') { creates++; return Response.json({ id: 'plus-thread', project_id: 11 }, { status: 201 }) }
      return Response.json(creates ? [{ id: 'plus-thread', project_id: 11, title: '새 대화', latest_run_id: null, status: null }] : [])
    }
    if (path.endsWith('/runs')) { runs.push(path); return new Response('event: completed\ndata: {"status":"completed","answer":"새 세션 응답","judgement":{},"evidence":[],"interrupt":{}}\n\n') }
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: first.name })
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }))
  await waitFor(() => expect(screen.getByLabelText('질문')).toHaveFocus())
  const sessions = screen.getByRole('list', { name: '이전 대화' })
  expect(await within(sessions).findByRole('button', { name: /새 대화.*현재 대화/ })).toHaveAttribute('aria-current', 'true')
  expect(creates).toBe(1)
  expect(runs).toEqual([])
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1 분석' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await screen.findByText('새 세션 응답')
  expect(creates).toBe(1)
  expect(runs).toEqual(['/api/threads/plus-thread/runs'])
})

it('locks navigation during session creation and preserves the draft on failure before retry', async () => {
  let finish!: (response: Response) => void
  let creates = 0
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') {
      creates++
      return creates === 1 ? new Promise<Response>(resolve => { finish = resolve }) : Response.json({ id: 'retried', project_id: 11 })
    }
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: first.name })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '보존할 초안' } })
  const plus = screen.getByRole('button', { name: '새 대화' })
  fireEvent.click(plus); fireEvent.click(plus)
  await waitFor(() => expect(creates).toBe(1))
  expect(plus).toBeDisabled()
  expect(screen.getByRole('button', { name: second.name })).toBeDisabled()
  expect(screen.getByRole('button', { name: '질문 전송' })).toBeDisabled()
  await act(async () => finish(failure('SERVICE_UNAVAILABLE', '대화를 생성하지 못했습니다.', 503)))
  expect(await screen.findByRole('alert')).toHaveTextContent('대화를 생성하지 못했습니다.')
  expect(screen.getByLabelText('질문')).toHaveValue('보존할 초안')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
  fireEvent.click(plus)
  await waitFor(() => expect(screen.getByLabelText('질문')).toHaveValue(''))
  expect(creates).toBe(2)
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

it.each([true, false])('reopens a verified empty saved session and selects its target without another thread (selected=%s)', async selected => {
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'POST') writes.push(path)
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads') return Response.json([{ id: 'empty-thread', project_id: 11, title: '새 대화', status: null, latest_run_id: null }])
    if (path === '/api/threads/empty-thread') return Response.json({ id: 'empty-thread', project_id: 11, target_ref: null, target_locked: false, latest_run: null, messages: [], next_before_message_id: null })
    if (path.endsWith('/runs')) return new Response('event: completed\ndata: {"status":"completed","answer":"빈 세션 응답","judgement":{},"evidence":[],"interrupt":{}}\n\n')
    return Response.json([])
  })
  openWorkbench(`/app?projectId=11${selected ? '&targetRef=D1' : ''}&threadId=empty-thread`)
  await waitFor(() => expect(screen.getByLabelText('현재 경로')).not.toHaveTextContent('threadId='))
  if (!selected) {
    fireEvent.click(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` }))
    fireEvent.change(await screen.findByLabelText('분석할 부품'), { target: { value: 'D1' } })
  }
  await waitFor(() => expect(screen.getByLabelText('질문')).toBeEnabled())
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1 분석' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  await screen.findByText('빈 세션 응답')
  expect(writes).toEqual(['/api/threads/empty-thread/runs'])
})

it('aborts plus creation on unmount and ignores a late response', async () => {
  let finish!: (response: Response) => void
  let signal: AbortSignal | undefined
  network((path, init) => {
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') { signal = init.signal as AbortSignal; return new Promise<Response>(resolve => { finish = resolve }) }
    return Response.json([])
  })
  const client = openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: first.name })
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }))
  await waitFor(() => expect(signal).toBeDefined())
  const write = vi.spyOn(client, 'setQueryData')
  cleanup()
  expect(signal?.aborted).toBe(true)
  await act(async () => finish(Response.json({ id: 'late', project_id: 11 })))
  expect(write).not.toHaveBeenCalled()
})

it.each([true, false])('confirms row project deletion without changing selection first (current=%s)', async current => {
  const victim = current ? first : second
  let removed = false
  const writes: string[] = []
  network((path, init) => {
    if (init.method === 'DELETE') { writes.push(path); removed = true; return new Response(null, { status: 204 }) }
    if (path === '/api/projects') return Response.json([first, second].filter(p => !removed || p.id !== victim.id).map(summary))
    return Response.json(path === '/api/projects/11' ? first : path === '/api/projects/12' ? second : [])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '보존할 초안' } })
  const remove = screen.getByRole('button', { name: `${victim.name} 프로젝트 삭제` })
  fireEvent.click(remove)
  const dialog = screen.getByRole('dialog', { name: '프로젝트 삭제' })
  expect(dialog).toHaveTextContent(victim.name)
  expect(dialog).toHaveTextContent('되돌릴 수 없습니다')
  expect(writes).toEqual([])
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
  fireEvent.click(within(dialog).getByRole('button', { name: '취소' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(writes).toEqual([])
  fireEvent.click(remove)
  fireEvent.click(within(screen.getByRole('dialog', { name: '프로젝트 삭제' })).getByRole('button', { name: '삭제 확인' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(writes).toEqual([`/api/projects/${victim.id}`])
  await waitFor(() => expect(within(screen.getByRole('list', { name: '저장된 프로젝트' })).queryByRole('button', { name: victim.name })).not.toBeInTheDocument())
  if (current) expect(screen.getByLabelText('현재 경로')).toBeEmptyDOMElement()
  else {
    expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
    expect(screen.getByLabelText('질문')).toHaveValue('보존할 초안')
  }
})

it('keeps the project and draft on row deletion errors and allows retry', async () => {
  let attempts = 0
  network((path, init) => {
    if (init.method === 'DELETE') return ++attempts === 1 ? failure('CONFLICT', '진행 중인 분석이 있습니다.', 409) : new Response(null, { status: 204 })
    return Response.json(path === '/api/projects' ? attempts > 1 ? [] : [summary(first)] : path === '/api/projects/11' ? first : [])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '오류 후에도 보존' } })
  fireEvent.click(screen.getByRole('button', { name: `${first.name} 프로젝트 삭제` }))
  const dialog = screen.getByRole('dialog', { name: '프로젝트 삭제' })
  fireEvent.click(within(dialog).getByRole('button', { name: '삭제 확인' }))
  expect(await within(dialog).findByRole('alert')).toHaveTextContent('진행 중인 분석이 있습니다. (요청 ID: req-test)')
  expect(within(dialog).getAllByRole('alert')).toHaveLength(1)
  expect(screen.getByLabelText('질문')).toHaveValue('오류 후에도 보존')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
  expect(within(screen.getByRole('list', { name: '저장된 프로젝트' })).getByRole('button', { name: first.name })).toBeInTheDocument()
  fireEvent.click(within(dialog).getByRole('button', { name: '삭제 확인' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(attempts).toBe(2)
})

it('locks navigation and prevents duplicate confirmation while a row deletion is pending', async () => {
  let finish!: (response: Response) => void
  let deletes = 0
  network((path, init) => {
    if (init.method === 'DELETE') { deletes++; return new Promise(resolve => { finish = resolve }) }
    return Response.json(path === '/api/projects' ? [summary(first), summary(second)] : path === '/api/projects/11' ? first : [])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.click(screen.getByRole('button', { name: `${second.name} 프로젝트 삭제` }))
  const dialog = screen.getByRole('dialog', { name: '프로젝트 삭제' })
  const confirm = within(dialog).getByRole('button', { name: '삭제 확인' })
  fireEvent.click(confirm); fireEvent.click(confirm)
  expect(deletes).toBe(1)
  expect(within(dialog).getByRole('button', { name: '취소' })).toBeDisabled()
  expect(within(dialog).queryByRole('button', { name: '닫기' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '프로젝트 추가' })).toBeDisabled()
  expect(within(screen.getByRole('list', { name: '저장된 프로젝트' })).getByRole('button', { name: second.name })).toBeDisabled()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(dialog).toBeInTheDocument()
  await act(async () => finish(new Response(null, { status: 204 })))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
})

it('aborts a row deletion on unmount without invalidating a later screen', async () => {
  let finish!: (response: Response) => void
  let signal: AbortSignal | null | undefined
  network((path, init) => {
    if (init.method === 'DELETE') { signal = init.signal; return new Promise(resolve => { finish = resolve }) }
    return Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : [])
  })
  const client = openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.click(screen.getByRole('button', { name: `${first.name} 프로젝트 삭제` }))
  fireEvent.click(within(screen.getByRole('dialog', { name: '프로젝트 삭제' })).getByRole('button', { name: '삭제 확인' }))
  const invalidations = vi.spyOn(client, 'invalidateQueries')
  cleanup()
  expect(signal?.aborted).toBe(true)
  await act(async () => finish(new Response(null, { status: 204 })))
  expect(invalidations).not.toHaveBeenCalled()
})
it('removes the header project summary and opens management from the sidebar heading', async () => {
  network(path => Response.json(path === '/api/projects' ? [summary(first)] : []))
  openWorkbench()
  const header = document.querySelector('.workbench-topbar')!
  expect(header.querySelector('.workbench-context')).toBeNull()
  expect(within(header as HTMLElement).queryByRole('button', { name: /^프로젝트 선택:/ })).not.toBeInTheDocument()
  expect(screen.queryByText('프로젝트 없음')).not.toBeInTheDocument()
  expect(screen.queryByText('대상 부품 미선택')).not.toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toHaveAttribute('placeholder', '메시지를 입력하세요. Shift+Enter로 줄바꿈')
  const manage = screen.getByRole('button', { name: '프로젝트 선택: 프로젝트 없음' })
  expect(manage.closest('.workspace-project-navigation')).not.toBeNull()
  expect(manage).toHaveTextContent('현재 프로젝트')
  fireEvent.click(manage)
  expect(await screen.findByRole('dialog', { name: '내 프로젝트' })).toBeVisible()
})
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
it('selects the target in the sidebar project dialog without setup controls or copy in the conversation', async () => {
  const calls: string[] = []
  network((path, init) => { calls.push(init.method ?? 'GET'); return Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : []) })
  openWorkbench('/app?projectId=11')
  const trigger = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  expect(screen.queryByLabelText('질문 영역의 대상 부품')).not.toBeInTheDocument()
  expect(screen.queryByText('대체 가능성 분석 흐름')).not.toBeInTheDocument()
  expect(screen.queryByText('회로 입력 확인')).not.toBeInTheDocument()
  expect(screen.queryByText('대상 부품을 선택하세요')).not.toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeEnabled()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('dialog', { name: '내 프로젝트' })
  const select = await within(dialog).findByLabelText('분석할 부품')
  expect(within(select).getByRole('option', { name: 'D1 · 1N4001' })).toBeInTheDocument()
  fireEvent.change(select, { target: { value: 'D1' } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(document.querySelector('.target-badge')).toBeNull()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=D1')
  expect(screen.getByLabelText('질문')).toBeEnabled()
  expect(calls.every(method => method === 'GET')).toBe(true)
})

it('creates a project without an automatic management dialog and allows manual target selection', async () => {
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
  const manage = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeEnabled()
  expect(writes).toEqual(['/api/projects'])
  fireEvent.click(manage)
  const dialog = await screen.findByRole('dialog', { name: '내 프로젝트' })
  fireEvent.change(await within(dialog).findByLabelText('분석할 부품'), { target: { value: 'C1' } })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(document.querySelector('.target-badge')).toBeNull()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=C1')
  expect(writes).toEqual(['/api/projects'])
})
it('keeps the selected target without a badge above or inside the conversation', async () => {
  network(path => Response.json(path === '/api/projects' ? [summary(first)] : path === '/api/projects/11' ? first : []))
  openWorkbench('/app?projectId=11&targetRef=C1')
  await screen.findByLabelText('질문')
  expect(screen.queryByTitle('선택한 부품')).not.toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=C1')
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
  expect(Array.from(list.querySelectorAll('.workspace-project-select')).map(button => button.textContent)).toEqual([second.name, first.name])
  expect(within(list).queryByRole('button', { name: third.name })).not.toBeInTheDocument()
  const more = screen.getByRole('button', { name: '더보기 (1)' })
  expect(more).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(more)
  expect(Array.from(list.querySelectorAll('.workspace-project-select')).map(button => button.textContent)).toEqual([second.name, first.name, third.name])
  fireEvent.click(within(list).getByRole('button', { name: third.name }))
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${third.name}` })).toBeInTheDocument()
  expect(within(list).getByRole('button', { name: third.name })).toHaveAttribute('aria-current', 'true')
  fireEvent.click(screen.getByRole('button', { name: '접기' }))
  expect(within(list).queryByRole('button', { name: third.name })).not.toBeInTheDocument()
  const newChat = screen.getByRole('button', { name: '새 대화' })
  expect(newChat.textContent).toBe('')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=13')
  expect(methods.every(method => method === 'GET')).toBe(true)
})

it('loads saved conversation and its result with GET requests only, then returns to a fresh draft', async () => {
  const calls: string[] = []
  network((path, init) => {
    calls.push(`${init.method ?? 'GET'} ${path}`)
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') return Response.json({ id: 'fresh-from-history', project_id: 11 })
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
  expect(screen.queryByTitle('선택한 부품')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '결과 보기' })).not.toBeInTheDocument()
  expect(screen.queryByRole('complementary', { name: '회로와 분석 정보' })).not.toBeInTheDocument()
  expect(within(screen.getByRole('region', { name: '저장된 대화' })).queryByText('D1', { exact: true })).not.toBeInTheDocument()
  const current = screen.getByRole('button', { name: /대화 history-/ })
  expect(current).toHaveAttribute('aria-current', 'true')
  expect(current).toHaveAttribute('title', '대화 history-')
  expect(current).not.toHaveTextContent('저장된 대화 열기')
  fireEvent.click(screen.getByRole('button', { name: first.name }))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('threadId=history-thread')
  expect(screen.getByText('저장된 답변')).toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeEnabled()
  fireEvent.click(within(screen.getByRole('group', { name: '분석 결과 메뉴' })).getByRole('button', { name: '문서 근거' }))
  expect(await screen.findByText('saved.pdf')).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('threadId=history-thread')
  fireEvent.click(screen.getByRole('button', { name: /대화 history-/ }))
  expect(screen.getByText('saved.pdf')).toBeInTheDocument()
  expect(calls.every(path => path.startsWith('GET '))).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '새 대화' }))
  expect(await screen.findByLabelText('질문')).toHaveValue('')
  expect(calls.filter(path => path.startsWith('POST '))).toEqual(['POST /api/projects/11/threads'])
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
  showDetail('후보 비교')
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
  expect(created).toBe(2)
})

it('opens the new workspace without an entry modal before a project is selected', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.getByRole('heading', { name: 'SojaFit 에이전트' })).toBeInTheDocument()
  expect(screen.getByRole('list', { name: '저장된 프로젝트' })).toBeEmptyDOMElement()
  expect(screen.getByRole('button', { name: '새 대화' })).toBeDisabled()
  expect(screen.getByLabelText('질문')).toBeEnabled()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: /회로를 읽고/ })).not.toBeInTheDocument()
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
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
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
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
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
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  await act(async () => finish(Response.json(first, { status: 201 })))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
})
it.each(['missing', 'foreign'])('shows the common safe error for a %s project', async () => {
  network(path => path === '/api/projects/99' ? failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404) : Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench('/app?projectId=99&targetRef=D1')
  expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 찾을 수 없습니다. (요청 ID: req-test)')
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
})

it('exposes detail menu buttons and a labelled project drawer', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const toggle = screen.getByRole('button', { name: '프로젝트 열기' })
  toggle.focus()
  fireEvent.click(toggle)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  await waitFor(() => expect(toggle).toHaveFocus())
  showDetail('회로')
  showDetail('후보 비교')
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
  expect(screen.queryByRole('complementary', { name: '회로와 분석 정보' })).not.toBeInTheDocument()
  expect(screen.queryByText('회로 및 분석 정보', { exact: true })).not.toBeInTheDocument()
  expect(screen.queryByRole('group', { name: '작업 정보 메뉴' })).not.toBeInTheDocument()
  expect(screen.queryByRole('tablist', { name: '열린 자료' })).not.toBeInTheDocument()
  showDetail('회로')
  expect(screen.getByRole('tab', { name: '회로' })).toHaveAttribute('aria-selected', 'true')
  expect(within(screen.getByRole('tablist', { name: '열린 자료' })).getAllByRole('tab')).toHaveLength(1)
  expect(screen.queryByRole('tab', { name: '진행 기록' })).not.toBeInTheDocument()
  expect(screen.queryByText('회로 및 분석 정보', { exact: true })).not.toBeInTheDocument()
  expect(screen.queryByRole('slider', { name: '정보 패널 너비' })).not.toBeInTheDocument()
  const handle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  expect(handle).toHaveAttribute('aria-valuemax', '616')
  fireEvent.pointerDown(handle, { clientX: 900, pointerId: 3 })
  fireEvent.pointerMove(handle, { clientX: 500, pointerId: 3 })
  fireEvent.pointerUp(handle, { pointerId: 3 })
  expect(handle).toHaveAttribute('aria-valuenow', '616')
  fireEvent.click(screen.getByRole('button', { name: '회로 탭 닫기' }))
  expect(screen.queryByRole('tab', { name: '회로' })).not.toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: '자료 열기' })).toBeInTheDocument()
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

it('opens the project picker from the sidebar project heading', async () => {
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

  showDetail('회로')
  const rightHandle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  fireEvent.pointerDown(rightHandle, { clientX: 900, pointerId: 2 })
  fireEvent.pointerMove(rightHandle, { clientX: 850, pointerId: 2 })
  fireEvent.pointerUp(rightHandle, { pointerId: 2 })
  expect(rightHandle).toHaveAttribute('aria-valuenow', '410')
  fireEvent.pointerDown(rightHandle, { clientX: 850, pointerId: 3 })
  fireEvent.pointerMove(rightHandle, { clientX: 0, pointerId: 3 })
  fireEvent.pointerUp(rightHandle, { pointerId: 3 })
  expect(rightHandle).toHaveAttribute('aria-valuenow', '586')
  vi.stubGlobal('innerWidth', 1200)
  fireEvent(window, new Event('resize'))
  expect(rightHandle).toHaveAttribute('aria-valuemax', '466')
  expect(rightHandle).toHaveAttribute('aria-valuenow', '466')
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
  expect(screen.queryByTitle('선택한 부품')).not.toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=D1')
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
  showDetail('회로')
  showDetail('승인·견적')
  expect(screen.getByRole('tab', { name: '승인·견적' })).toBeInTheDocument()
  expect(screen.queryByLabelText('질문 영역의 대상 부품')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: `프로젝트 선택: ${first.name}` }))
  expect(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByLabelText('분석할 부품')).toBeInTheDocument()
})

it('stacks only opened tabs, deduplicates them and closes active or inactive tabs', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.queryByRole('button', { name: '승인·견적' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '승인 사례·이력' })).not.toBeInTheDocument()
  showDetail('회로')
  showDetail('회로')
  expect(screen.getAllByRole('tab')).toHaveLength(1)
  const circuit = screen.getByRole('tab', { name: '회로' })
  expect(circuit).toHaveAttribute('aria-controls', 'panel-circuit')
  expect(screen.getByRole('tabpanel', { name: '회로' })).toHaveAttribute('id', 'panel-circuit')
  showDetail('문서 근거')
  showDetail('문서 근거')
  const evidence = screen.getByRole('tab', { name: '문서 근거' })
  expect(screen.getAllByRole('tab').map(tab => tab.textContent)).toEqual(['회로', '문서 근거'])
  expect(evidence).toHaveAttribute('aria-selected', 'true')
  expect(circuit).toHaveAttribute('aria-selected', 'false')
  fireEvent.keyDown(evidence, { key: 'ArrowRight' })
  expect(circuit).toHaveFocus()
  fireEvent.keyDown(circuit, { key: 'ArrowLeft' })
  expect(evidence).toHaveFocus()
  fireEvent.click(screen.getByRole('button', { name: '회로 탭 닫기' }))
  expect(screen.getAllByRole('tab')).toHaveLength(1)
  expect(evidence).toHaveAttribute('aria-selected', 'true')
  showDetail('회로')
  fireEvent.keyDown(screen.getByRole('tab', { name: '회로' }), { key: 'Home' })
  expect(evidence).toHaveFocus()
  fireEvent.keyDown(evidence, { key: 'End' })
  fireEvent.keyDown(screen.getByRole('tab', { name: '회로' }), { key: 'Delete' })
  await waitFor(() => expect(evidence).toHaveFocus())
  fireEvent.keyDown(evidence, { key: 'Delete' })
  await waitFor(() => expect(screen.getByRole('combobox', { name: '자료 열기' })).toHaveFocus())
  expect(screen.queryByRole('complementary', { name: '회로와 분석 정보' })).not.toBeInTheDocument()
  showDetail('문서 근거')
  expect(screen.getAllByRole('tab')).toHaveLength(1)
  expect(screen.queryByRole('tab', { name: '회로' })).not.toBeInTheDocument()
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
  showDetail('회로')
  await screen.findByText('D1 / 1N4001')
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '입력 최대 12 V에서 D1을 SS34로 바꿔도 되나요?' } })
  fireEvent.click(screen.getByRole('button', { name: '질문 전송' }))
  expect(await screen.findByText('역극성 보호(직렬)')).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '회로' })).toHaveAttribute('aria-selected', 'true')
  expect(within(screen.getByLabelText('개념도 사용 조건')).getByText('판정 결과에서 확인된 사용 조건이 없습니다.')).toBeInTheDocument()
  showDetail('후보 비교')
  fireEvent.click(await screen.findByRole('button', { name: 'SS34 후보 선택' }))
  showDetail('문서 근거')
  expect(screen.getByText('SS34 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('ss34.pdf')).toBeInTheDocument()
})


it('keeps the new workbench collapsed and opens the selected demo original in its result panel', async () => {
  const visual = { ...demo, schematic: {
    image_url: '/circuit-schematics/mosfet_driver.png', original_url: 'https://cdn-learn.adafruit.com/assets/assets/000/117/028/large1024/adafruit_products_schem.png?1670851887',
    source_repo: 'https://github.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB', source_commit: 'a'.repeat(40),
    license: 'CC BY-SA 3.0', license_evidence_url: 'https://raw.githubusercontent.com/adafruit/Adafruit-MOSFET-Driver-STEMMA-PCB/main/license.txt', attribution: 'Adafruit Industries',
  } }
  network(path => path === '/api/demo-circuits' ? Response.json([visual])
    : path === '/api/projects' ? Response.json([summary(first)])
    : path === '/api/projects/11' ? Response.json(first) : Response.json([]))
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByRole('button', { name: '질문 전송' })
  expect(screen.queryByRole('tab', { name: '원본 회로도' })).not.toBeInTheDocument()
  showDetail('회로')
  expect(await screen.findByRole('tab', { name: '원본 회로도' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('img', { name: `${demo.name} 원본 회로도` })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '연결 개념도' }))
  expect(screen.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
})
