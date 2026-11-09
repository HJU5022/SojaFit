import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import App from '../App'
import { accounts, administrator, failure, network, user } from '../test/network'

afterEach(() => vi.unstubAllGlobals())
function open() { render(<MemoryRouter initialEntries={['/admin/users']}><App /></MemoryRouter>) }
it('blocks ordinary users before requesting or rendering account data', async () => {
  const paths: string[] = []
  network((path) => { paths.push(path); return Response.json(path.endsWith('/me') ? user : { users: accounts }) })
  open()
  expect(await screen.findByRole('alert')).toHaveTextContent('관리자 권한이 필요합니다.')
  expect(screen.queryByText('u***@example.test')).not.toBeInTheDocument()
  expect(paths).not.toContain('/api/admin/users')
})
it('lists masked users, protects admin accounts and updates account activation', async () => {
  let active = true; let patch: RequestInit | undefined
  network((path, init) => {
    if (path.endsWith('/me')) return Response.json(administrator)
    if (init.method === 'PATCH') { patch = init; active = false; return Response.json({ ok: true }) }
    return Response.json({ users: [accounts[0], { ...accounts[1], is_active: active }] })
  })
  open()
  const row = (await screen.findByText('u***@example.test')).closest('tr')!
  expect(within(screen.getByText('a***@example.test').closest('tr')!).queryByRole('button')).not.toBeInTheDocument()
  fireEvent.click(within(row).getByRole('button', { name: '비활성화' }))
  expect(await within(row).findByRole('button', { name: '활성화' })).toBeEnabled()
  expect(patch).toMatchObject({ method: 'PATCH', body: '{"is_active":false}' })
})
it('clears displayed account data when an update is forbidden', async () => {
  network((path, init) => path.endsWith('/me') ? Response.json(administrator) : init.method === 'PATCH' ? failure('FORBIDDEN', '관리자 권한이 필요합니다.', 403) : Response.json({ users: accounts }))
  open(); await screen.findByText('u***@example.test')
  fireEvent.click(screen.getByRole('button', { name: '비활성화' }))
  await waitFor(() => expect(screen.queryByText('u***@example.test')).not.toBeInTheDocument())
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
})
it('redirects to login and removes account data when the session expires during an update', async () => {
  network((path, init) => path.endsWith('/me') ? Response.json(administrator) : path.endsWith('/status') ? Response.json({ enabled: false }) : init.method === 'PATCH' ? failure() : Response.json({ users: accounts }))
  open(); await screen.findByText('u***@example.test')
  fireEvent.click(screen.getByRole('button', { name: '비활성화' }))
  expect(await screen.findByRole('heading', { name: '로그인' })).toBeInTheDocument()
  expect(screen.queryByText('u***@example.test')).not.toBeInTheDocument()
})
