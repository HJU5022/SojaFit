import { fireEvent, screen, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('selects a server reference in the URL and clears it on project switching', async () => {
  network((path) => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first), summary(second)] : path.endsWith('/11') ? first : second))
  openWorkbench('/app?projectId=11')
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  const select = await screen.findByLabelText('대상 부품')
  expect(within(select).getByRole('option', { name: 'D1 · 1N4001' })).toBeInTheDocument()
  fireEvent.change(select, { target: { value: 'D1' } })
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=11&targetRef=D1')
  expect(screen.getByText('선택한 대상: D1')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^프로젝트 선택:/ }))
  fireEvent.click(within(screen.getByRole('dialog', { name: '내 프로젝트' })).getByRole('button', { name: second.name }))
  expect(await screen.findByRole('heading', { name: second.name })).toBeInTheDocument()
  expect(screen.getByLabelText('대상 부품')).toHaveValue('')
  expect(screen.getByLabelText('현재 경로')).toHaveTextContent('projectId=12')
  expect(screen.getByLabelText('현재 경로')).not.toHaveTextContent('targetRef')
  expect(screen.queryByRole('option', { name: 'D1 · 1N4001' })).not.toBeInTheDocument()
})
it('does not treat a URL reference absent from the server DTO as a target', async () => {
  network((path) => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects' ? [summary(first)] : first))
  openWorkbench('/app?projectId=11&targetRef=FOREIGN')
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 펼치기' }))
  expect(await screen.findByLabelText('대상 부품')).toHaveValue('')
  expect(screen.queryByText('선택한 대상: FOREIGN')).not.toBeInTheDocument()
})
