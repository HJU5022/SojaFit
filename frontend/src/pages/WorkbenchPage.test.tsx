import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('shows the workbench without fabricated price candidates', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.getByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '가격·재고 조회' })).toBeDisabled()
  expect(await screen.findByText('프로젝트가 없습니다. 데모 또는 파일로 시작하세요.')).toBeInTheDocument()
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
  fireEvent.click(await screen.findByRole('button', { name: second.name }))
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
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '늦은 생성' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: second.name }))
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
  fireEvent.click(toggle)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  expect(toggle).toHaveFocus()
  const judgement = screen.getByRole('tab', { name: '판정' })
  fireEvent.click(judgement)
  expect(judgement).toHaveAttribute('aria-selected', 'true')
})
