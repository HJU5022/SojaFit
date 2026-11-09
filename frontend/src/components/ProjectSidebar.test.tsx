import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('renames through the owner API and refreshes list and detail', async () => {
  let name = first.name
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([{ ...summary(first), name }])
    if (init.method === 'PATCH') { expect(JSON.parse(init.body as string)).toEqual({ name: '수정한 회로' }); name = '수정한 회로' }
    return Response.json({ ...first, name })
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  fireEvent.change(await screen.findByLabelText('프로젝트 이름 변경'), { target: { value: '수정한 회로' } })
  fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  expect(await screen.findByRole('heading', { name: '수정한 회로' })).toBeInTheDocument()
  expect(await screen.findByRole('button', { name: '수정한 회로' })).toBeInTheDocument()
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
  await screen.findByLabelText('대상 부품')
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
  expect(client.getQueryData(['project', 11])).toBeUndefined()
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
  await screen.findByLabelText('대상 부품')
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 삭제' }))
  fireEvent.click(screen.getByRole('button', { name: '삭제 확인' }))
  fireEvent.click(screen.getByRole('button', { name: second.name }))
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  await act(async () => { deleted = true; finish(new Response(null, { status: 204 })) })
  expect(screen.getByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
})
it('shows owner mutation errors and their request IDs', async () => {
  network((path, init) => init.method === 'PATCH' ? failure('NOT_FOUND', '프로젝트를 찾을 수 없습니다.', 404) : Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first)] : first))
  openWorkbench('/app?projectId=11')
  fireEvent.change(await screen.findByLabelText('프로젝트 이름 변경'), { target: { value: '수정' } })
  fireEvent.click(screen.getByRole('button', { name: '이름 저장' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('프로젝트를 찾을 수 없습니다. (요청 ID: req-test)')
})
