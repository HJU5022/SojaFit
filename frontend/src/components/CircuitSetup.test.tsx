import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
function openCreator() {
  const trigger = screen.queryAllByRole('button', { name: '프로젝트 추가' })[0]
  if (trigger) fireEvent.click(trigger)
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
  expect(await screen.findByRole('heading', { name: first.name })).toBeInTheDocument()
  expect(screen.getByText('부품 2개 · 넷 1개')).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11')
  openProjectList()
  expect(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: first.name })).toBeInTheDocument()
  expect(client.getQueryData(['projects'])).toEqual([summary(first)])
  expect(client.getQueryData(['project', 11])).toEqual(first)
  expect(client.getQueryData(['demo-circuits'])).toEqual([demo])
  expect(screen.queryByRole('button', { name: '가격·재고 조회' })).not.toBeInTheDocument()
  expect(storage).not.toHaveBeenCalled(); expect(database).not.toHaveBeenCalled(); storage.mockRestore()
})
it('uploads .net multipart without parsing and clears the input on success', async () => {
  let uploaded = false
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects/upload') {
      const form = init.body as FormData
      expect([...form.keys()]).toEqual(['name', 'file'])
      expect(form.get('name')).toBe('회로 업로드')
      expect((form.get('file') as File).name).toBe('board.net')
      expect(new Headers(init.headers).has('Content-Type')).toBe(false)
      uploaded = true; return Response.json(second, { status: 201 })
    }
    if (path === '/api/projects') return Response.json(uploaded ? [summary(second)] : [])
    if (path === '/api/projects/12') return Response.json(second)
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
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  await waitFor(() => expect(input.value).toBe(''))
  expect(screen.getByText('부품 1개 · 넷 1개')).toBeInTheDocument()
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
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  await screen.findByRole('heading', { name: first.name })
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
  await screen.findByRole('heading', { name: second.name })
  expect(signal?.aborted).toBe(true)
  fireEvent.change(screen.getByLabelText('대상 부품'), { target: { value: 'D2' } })
  const before = [...projectReads]
  await act(async () => finish(Response.json(kind === 'demo' ? first : { ...second, id: 13 }, { status: 201 })))
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('?projectId=12&targetRef=D2')
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByText('선택한 대상: D2')).toBeInTheDocument()
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
  openWorkbench(); openCreator()
  expect(await screen.findByRole('button', { name: '다시 불러오기' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
  expect(await screen.findByRole('option', { name: demo.name })).toBeInTheDocument()
  expect(attempts).toBe(2)
})
