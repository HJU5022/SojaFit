import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network as mockNetwork } from '../test/network'
import { demo, first, second, summary, openWorkbench, renderWithQueries as render, showDetail } from '../test/projects'
import CircuitSetup from './CircuitSetup'

// These existing creation fixtures exercise demo mode explicitly.
function network(handler: Parameters<typeof mockNetwork>[0]) {
  mockNetwork((path, init) => path === '/api/auth/demo' ? Response.json({ enabled: true }) : handler(path, init))
}

afterEach(() => vi.unstubAllGlobals())
it.each(['disabled', 'not-found', 'unavailable'])('keeps creation file-only when demo status is %s', async status => {
  const calls: string[] = []
  mockNetwork(path => {
    calls.push(path)
    if (path === '/api/auth/demo') return status === 'disabled' ? Response.json({ enabled: false }) : failure('HTTP_ERROR', 'Unavailable', status === 'not-found' ? 404 : 503)
    if (path === '/api/demo-circuits') return Response.json([demo])
    return Response.json([])
  })
  render(<CircuitSetup onCreated={vi.fn()} />)
  await waitFor(() => expect(calls).toContain('/api/auth/demo'))
  expect(screen.getByRole('form', { name: '넷리스트 첨부' })).toBeVisible()
  expect(screen.queryByRole('form', { name: '데모 회로로 시작' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '데모로 만들기' })).not.toBeInTheDocument()
  expect(screen.queryByText(/공개 데모/)).not.toBeInTheDocument()
  expect(calls).not.toContain('/api/demo-circuits')
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '파일 회로' } })
  fireEvent.change(screen.getByLabelText('KiCad 넷리스트'), { target: { files: [new File(['synthetic'], 'board.net')] } })
  expect(screen.getByRole('button', { name: '파일로 만들기' })).toBeEnabled()
})
function openCreator() {
  const trigger = screen.queryAllByRole('button', { name: '프로젝트 추가' })[0]
  if (trigger) fireEvent.click(trigger)
  else if (screen.queryByRole('button', { name: /^프로젝트$/ })) {
    fireEvent.click(screen.getByRole('button', { name: /^프로젝트$/ }))
    fireEvent.click(screen.getByRole('button', { name: '새 프로젝트 만들기' }))
  }
  else {
    fireEvent.click(screen.getByRole('button', { name: 'D1을 SS34로 바꿔도 되나요?' }))
    fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
  }
}
function openProjectList() { fireEvent.click(screen.getByRole('button', { name: /^프로젝트 선택:/ })) }
it('creates a demo, selects its server summary and keeps data out of browser storage', async () => {
  let created = false
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects' && init.method === 'POST') {
      expect(JSON.parse(init.body as string)).toEqual({ demo_id: demo.id, name: '나의 회로' })
      created = true; return Response.json(first, { status: 201 })
    }
    if (path === '/api/projects') return Response.json(created ? [summary(first)] : [])
    if (path === '/api/projects/11') return Response.json(first)
    throw new Error(`Unexpected request: ${path}`)
  })
  const storage = vi.spyOn(Storage.prototype, 'setItem')
  const database = vi.fn(); vi.stubGlobal('indexedDB', { open: database })
  const client = openWorkbench()
  openCreator()
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '나의 회로' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })).toBeInTheDocument()
  expect(screen.queryByText('부품 2개 · 넷 1개')).not.toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11')
  openProjectList()
  expect(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: first.name })).toBeInTheDocument()
  expect(client.getQueryData(['projects'])).toEqual([summary(first)])
  expect(client.getQueryData(['project', 11])).toEqual(first)
  expect(client.getQueryData(['demo-circuits'])).toEqual([demo])
  expect(screen.queryByRole('button', { name: '가격·재고 조회' })).not.toBeInTheDocument()
  expect(storage).not.toHaveBeenCalled(); expect(database).not.toHaveBeenCalled(); storage.mockRestore()
})
it.each(['D2', 'D7', 'R9'])('uploads .net and immediately shows the server circuit around %s', async target => {
  const uploadedProject = target === 'D2' ? second : { ...second, connections: { parts: [
    { ref: 'R9', value: 'UPLOAD-RESISTOR', footprint: '' },
    ...(target === 'D7' ? [{ ref: 'D7', value: 'UPLOAD-DIODE', footprint: '' }] : []),
  ], nets: [{ name: 'UPLOAD-NET', nodes: [{ ref: 'R9', pin: '1' }, ...(target === 'D7' ? [{ ref: 'D7', pin: '2' }] : [])] }] } }
  let uploaded = false
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects/upload') {
      const form = init.body as FormData
      expect([...form.keys()]).toEqual(['name', 'file'])
      expect(form.get('name')).toBe('회로 업로드')
      expect((form.get('file') as File).name).toBe('board.net')
      expect(new Headers(init.headers).has('Content-Type')).toBe(false)
      uploaded = true; return Response.json(uploadedProject, { status: 201 })
    }
    if (path === '/api/projects') return Response.json(uploaded ? [summary(second)] : [])
    if (path === '/api/projects/12') return Response.json(uploadedProject)
    throw new Error(`Unexpected request: ${path}`)
  })
  openWorkbench()
  openCreator()
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '회로 업로드' } })
  const input = screen.getByLabelText('KiCad 넷리스트') as HTMLInputElement
  expect(input).toHaveAttribute('accept', '.net')
  fireEvent.change(input, { target: { files: [new File(['unparsed server input'], 'board.net')] } })
  // jsdom does not populate a native FileList; model the browser's filename display.
  Object.defineProperty(input, 'value', { writable: true, configurable: true, value: 'C:\\fakepath\\board.net' })
  // Submit explicitly because jsdom's native validity does not see the synthetic FileList.
  fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  await waitFor(() => expect(input.value).toBe(''))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent(`targetRef=${target}`)
  expect(screen.getByRole('img', { name: `${target} 주변 연결 개념도` })).toBeVisible()
  expect(screen.getByRole('tab', { name: '회로' })).toHaveAttribute('aria-selected', 'true')
  if (target !== 'D2') expect(screen.getByText('UPLOAD-NET')).toBeInTheDocument()
})
it.each([[400, '올바른 UTF-8 KiCad 넷리스트를 올려 주세요.'], [413, '넷리스트는 5 MiB 이하여야 합니다.']])('shows upload %s common error/request ID and clears the file', async (status, message) => {
  network((path) => path === '/api/projects/upload' ? failure('HTTP_ERROR', message, status)
    : Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  openCreator()
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '실패 회로' } })
  const input = screen.getByLabelText('KiCad 넷리스트') as HTMLInputElement
  fireEvent.change(input, { target: { files: [new File(['bad'], 'board.net')] } })
  Object.defineProperty(input, 'value', { writable: true, configurable: true, value: 'C:\\fakepath\\board.net' })
  // Submit explicitly because jsdom's native validity does not see the synthetic FileList.
  fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
  expect(await screen.findByRole('alert')).toHaveTextContent(`${message} (요청 ID: req-test)`)
  await waitFor(() => expect(input.value).toBe(''))
  expect(screen.getByLabelText('현재 경로')).toBeEmptyDOMElement()
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
})

it.each(['demo', 'upload'] as const)('cancels pending %s on project switching without late refresh or selection changes', async (kind) => {
  let finish!: (response: Response) => void; let signal: AbortSignal | null | undefined
  const projectReads: string[] = []
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (init.method === 'POST') { signal = init.signal; return new Promise(resolve => { finish = resolve }) }
    projectReads.push(path)
    return Response.json(path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second)
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  showDetail('회로')
  await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  openCreator()
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '진행 중 회로' } })
  const input = screen.getByLabelText('KiCad 넷리스트') as HTMLInputElement
  if (kind === 'demo') {
    await screen.findByRole('option', { name: demo.name })
    fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
    fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  } else {
    fireEvent.change(input, { target: { files: [new File(['server input'], 'board.net')] } })
    Object.defineProperty(input, 'value', { writable: true, configurable: true, value: 'C:\\fakepath\\board.net' })
    fireEvent.submit(screen.getByRole('button', { name: '파일로 만들기' }).closest('form')!)
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.click(screen.getByRole('button', { name: /^닫기$/ }))
  openProjectList()
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })
  expect(signal?.aborted).toBe(true)
  fireEvent.change(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByLabelText('분석할 부품'), { target: { value: 'D2' } })
  showDetail('회로')
  const before = [...projectReads]
  await act(async () => finish(Response.json(kind === 'demo' ? first : { ...second, id: 13 }, { status: 201 })))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('?projectId=12&targetRef=D2')
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  expect(screen.getByRole('img', { name: 'D2 주변 연결 개념도' })).toBeInTheDocument()
  expect(projectReads).toEqual(before)
  expect(signal?.aborted).toBe(true)
  openCreator()
  expect(screen.getByLabelText('새 프로젝트 이름')).toBeEnabled()
  expect(screen.getByLabelText('KiCad 넷리스트')).toBeEnabled()
  if (kind === 'upload') {
    expect(input.value).toBe('')
    expect(screen.getByLabelText('KiCad 넷리스트')).toHaveValue('')
  }
})

it('keeps file creation disabled until a file is selected', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench(); openCreator()
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '파일 회로' } })
  const input = screen.getByLabelText('KiCad 넷리스트') as HTMLInputElement
  const button = screen.getByRole('button', { name: '파일로 만들기' })
  expect(button).toBeDisabled()
  fireEvent.change(input, { target: { files: [new File(['server input'], 'board.net')] } })
  expect(button).toBeEnabled()
})

it('offers retry when demo loading fails', async () => {
  let attempts = 0
  network(path => path === '/api/demo-circuits'
    ? (++attempts === 1 ? failure('HTTP_ERROR', '데모를 불러오지 못했습니다.', 503) : Response.json([demo]))
    : Response.json([]))
  render(<CircuitSetup onCreated={vi.fn()} />)
  expect(await screen.findByRole('button', { name: '다시 불러오기' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
  expect(await screen.findByRole('option', { name: demo.name })).toBeInTheDocument()
  expect(attempts).toBe(2)
})
