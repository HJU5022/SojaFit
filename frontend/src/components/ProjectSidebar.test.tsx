import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench, showDetail } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
function openProjectList() { fireEvent.click(screen.getByRole('button', { name: /^프로젝트 선택:/ })) }
it('renames through the owner API and refreshes list and detail', async () => {
  let name = first.name
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([{ ...summary(first), name }])
    if (init.method === 'PATCH') { expect(JSON.parse(init.body as string)).toEqual({ name: '수정한 회로' }); name = '수정한 회로' }
    return Response.json({ ...first, name })
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  showDetail('회로')
  openProjectList()
  fireEvent.change(await screen.findByLabelText('프로젝트 이름 변경'), { target: { value: '수정한 회로' } })
  fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  expect(await screen.findByRole('button', { name: '프로젝트 선택: 수정한 회로' })).toBeInTheDocument()
  expect(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: '수정한 회로' })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('targetRef=D1')
})
it('requires explicit confirmation and clears project/target after successful 204 deletion', async () => {
  let deleted = false; let deletes = 0
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json(deleted ? [] : [summary(first)])
    if (init.method === 'DELETE') { deletes++; deleted = true; return new Response(null, { status: 204 }) }
    return Response.json(first)
  })
  const client = openWorkbench('/app?projectId=11&targetRef=D1')
  showDetail('회로')
  await screen.findByRole('img', { name: 'D1 주변 연결 개념도' })
  openProjectList()
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
  const confirmation = screen.getByRole('group', { name: '프로젝트 삭제 확인' })
  expect(deletes).toBe(0)
  fireEvent.click(within(confirmation).getByRole('button', { name: '취소' }))
  expect(screen.queryByRole('group', { name: '프로젝트 삭제 확인' })).not.toBeInTheDocument()
  expect(deletes).toBe(0)
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
  fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  await waitFor(() => expect(screen.getByLabelText('현재 경로')).toBeEmptyDOMElement())
  expect(screen.queryByLabelText('대상 부품')).not.toBeInTheDocument()
  await waitFor(() => expect(screen.queryByRole('button', { name: first.name })).not.toBeInTheDocument())
  await waitFor(() => expect(client.getQueryData(['project', 11])).toBeUndefined())
  expect(deletes).toBe(1)
})
it('keeps the new selection when an older deletion settles', async () => {
  let deleted = false; let finish!: (response: Response) => void
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json(deleted ? [summary(second)] : [summary(first), summary(second)])
    if (init.method === 'DELETE') return new Promise(resolve => { finish = resolve })
    return Response.json(path.endsWith('/11') ? first : second)
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  showDetail('회로')
  await screen.findByRole('img', { name: 'D1 주변 연결 개념도' })
  openProjectList()
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
  fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  expect(await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  await act(async () => { deleted = true; finish(new Response(null, { status: 204 })) })
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
})
it('shows owner mutation errors and their request IDs', async () => {
  network((path, init) => init.method === 'PATCH' ? failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404) : Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first)] : first))
  openWorkbench('/app?projectId=11')
  showDetail('회로')
  openProjectList()
  fireEvent.change(await screen.findByLabelText('프로젝트 이름 변경'), { target: { value: '수정' } })
  fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 찾을 수 없습니다. (요청 ID: req-test)')
})

it('offers a reload action when the project list request fails', async () => {
  let attempts = 0
  network((path) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') {
      attempts++
      return attempts === 1 ? failure('TEMPORARY', '프로젝트를 불러오지 못했습니다.', 503) : Response.json([summary(first)])
    }
    return Response.json(first)
  })
  openWorkbench('/app')
  openProjectList()
  expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 불러오지 못했습니다.')
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 다시 불러오기' }))
  expect(await within(screen.getByRole('dialog', { name: '내 프로젝트' })).findByRole('button', { name: first.name })).toBeInTheDocument()
  expect(attempts).toBe(2)
})

it.each(['rename', 'delete'] as const)('cancels an owning %s editor when switching projects and skips stale refreshes', async (kind) => {
  let finish!: (response: Response) => void; let signal: AbortSignal | null | undefined; let reads = 0
  network((path, init) => {
    if (init.method === 'PATCH' || init.method === 'DELETE') {
      signal = init.signal; return new Promise(resolve => { finish = resolve })
    }
    reads++
    return Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second)
  })
  openWorkbench('/app?projectId=11')
  showDetail('회로')
  openProjectList()
  await screen.findByLabelText('프로젝트 이름 변경')
  if (kind === 'rename') fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  else {
    fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
    fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  }
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  await screen.findByRole('button', { name: `프로젝트 선택: ${second.name}` })
  const before = reads
  await act(async () => finish(kind === 'delete' ? new Response(null, { status: 204 }) : Response.json(first)))
  expect(screen.getByRole('button', { name: `프로젝트 선택: ${second.name}` })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(reads).toBe(before)
  expect(signal?.aborted).toBe(true)
})
