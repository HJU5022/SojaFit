import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import SettingsPage from './SettingsPage'
import { failure, network, user } from '../test/network'
import { renderWithQueries } from '../test/projects'

vi.mock('../auth/AuthProvider', () => ({ useAuth: () => ({ user }) }))
afterEach(() => vi.unstubAllGlobals())

it.each([true, false])('locks profile editing until the initial response arrives (saved settings: %s)', async populated => {
  let finish!: (response: Response) => void
  const pending = new Promise<Response>(resolve => { finish = resolve })
  network(() => pending)
  renderWithQueries(<MemoryRouter><SettingsPage /></MemoryRouter>)
  const affiliation = screen.getByRole('textbox', { name: '소속' })
  const role = screen.getByRole('combobox', { name: '직무' })
  const mounting = screen.getByRole('combobox', { name: '선호 실장 방식' })
  const save = screen.getByRole('button', { name: '저장' })
  for (const control of [affiliation, role, mounting, save]) expect(control).toBeDisabled()
  expect(screen.getByRole('status')).toHaveTextContent('설정을 불러오는 중입니다.')
  await act(async () => { finish(Response.json(populated ? [
    { kind: 'affiliation', value: '기존 회로팀', text: '기존 회로팀' },
    { kind: 'job_role', value: 'design', text: '설계' },
    { kind: 'mounting_preference', value: 'smd', text: 'SMD' },
  ] : [])) })
  await waitFor(() => { for (const control of [affiliation, role, mounting, save]) expect(control).toBeEnabled() })
  expect(affiliation).toHaveValue(populated ? '기존 회로팀' : '')
  expect(role).toHaveValue(populated ? 'design' : '')
  expect(mounting).toHaveValue(populated ? 'smd' : '')
  expect(affiliation.closest('form')).toHaveAttribute('data-refresh-blocked', 'false')
  fireEvent.change(affiliation, { target: { value: '새로 입력한 회로팀' } })
  fireEvent.change(role, { target: { value: 'purchasing' } })
  fireEvent.change(mounting, { target: { value: 'through_hole' } })
  expect(affiliation).toHaveValue('새로 입력한 회로팀')
  expect(role).toHaveValue('purchasing')
  expect(mounting).toHaveValue('through_hole')
  expect(affiliation.closest('form')).toHaveAttribute('data-refresh-blocked', 'true')
})

function profileApi() {
  const server = { values: { affiliation: '초기 회로팀', job_role: 'design', mounting_preference: 'smd' } as Record<string, string>, reads: 0, writes: [] as { method: string; body?: unknown }[], failRead: false, failWrite: false, pendingRead: null as Promise<Response> | null }
  const records = () => Object.entries(server.values).map(([kind, value]) => ({ kind, value, text: value }))
  network((path, init) => {
    if (init.method === 'PATCH' || init.method === 'DELETE') {
      const body = init.method === 'PATCH' ? JSON.parse(String(init.body)) : undefined
      server.writes.push({ method: init.method, body })
      if (server.failWrite) return failure('UNAVAILABLE', '설정 변경 실패', 503)
      if (body) { Object.assign(server.values, body); return Response.json(records()) }
      const kind = new URL(path, 'http://localhost').searchParams.get('kind')
      if (kind) delete server.values[kind]; else server.values = {}
      return new Response(null, { status: 204 })
    }
    server.reads++
    if (server.pendingRead) return server.pendingRead
    return server.failRead ? failure('UNAVAILABLE', '최신 설정 조회 실패', 503) : Response.json(records())
  })
  return server
}
function settings() { return renderWithQueries(<MemoryRouter><SettingsPage /></MemoryRouter>) }
async function editAffiliation() {
  const input = await screen.findByRole('textbox', { name: '소속' })
  await waitFor(() => expect(input).toHaveValue('초기 회로팀'))
  fireEvent.change(input, { target: { value: '보존할 초안' } })
  return input
}
function mutateProfile(mode: string) {
  if (mode === 'save') fireEvent.click(screen.getByRole('button', { name: '저장' }))
  else if (mode === 'single') fireEvent.click(screen.getByRole('button', { name: '직무 지우기' }))
  else { fireEvent.click(screen.getByRole('button', { name: '모두 지우기' })); fireEvent.click(screen.getByRole('button', { name: '지우기 확인' })) }
}

it('keeps the draft on background refresh and saves only fields changed from the form baseline', async () => {
  const server = profileApi()
  const { client } = settings()
  const input = await editAffiliation()
  server.values = { ...server.values, affiliation: '다른 탭 회로팀', job_role: 'other' }
  await act(async () => { await client.refetchQueries({ queryKey: ['profile-memory'] }) })
  await screen.findByText('다른 탭 회로팀')
  expect(input).toHaveValue('보존할 초안')
  expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('design')
  mutateProfile('save')
  await waitFor(() => expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('other'))
  expect(input).toHaveValue('보존할 초안')
  expect(server.writes).toEqual([{ method: 'PATCH', body: { affiliation: '보존할 초안' } }])
  expect(screen.getByRole('status')).toHaveTextContent('저장했습니다.')
})

it.each(['single', 'all'])('synchronizes the form only after a successful %s deletion', async mode => {
  const server = profileApi()
  settings()
  const input = await editAffiliation()
  server.values.affiliation = '서버의 최신 회로팀'
  mutateProfile(mode)
  await waitFor(() => expect(input).toHaveValue(mode === 'all' ? '' : '서버의 최신 회로팀'))
  expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('')
  expect(screen.getByRole('combobox', { name: '선호 실장 방식' })).toHaveValue(mode === 'all' ? '' : 'smd')
  expect(server.writes).toEqual([{ method: 'DELETE', body: undefined }])
})

it.each(['save', 'single', 'all'])('keeps the draft and selection if %s fails', async mode => {
  const server = profileApi()
  settings()
  const input = await editAffiliation()
  server.failWrite = true
  mutateProfile(mode)
  expect(await screen.findByRole('alert')).toHaveTextContent('설정 변경 실패')
  expect(input).toHaveValue('보존할 초안')
  expect(input).toBeEnabled()
  expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('design')
  expect(server.reads).toBe(1)
})

it('retries only synchronization after a confirmed write and a failed refresh, preserving the draft meanwhile', async () => {
  const server = profileApi()
  const { client } = settings()
  const input = await editAffiliation()
  server.failRead = true
  mutateProfile('save')
  expect(await screen.findByRole('alert')).toHaveTextContent('최신 설정 조회 실패')
  await waitFor(() => expect(input).toBeEnabled())
  expect(input).toHaveValue('보존할 초안')
  server.failRead = false; server.values.job_role = 'other'
  await act(async () => { await client.refetchQueries({ queryKey: ['profile-memory'] }) })
  await screen.findByText('other')
  expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('design')
  let finish!: (response: Response) => void
  server.pendingRead = new Promise<Response>(resolve => { finish = resolve })
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
  expect(input).toBeDisabled()
  await act(async () => { finish(Response.json(Object.entries(server.values).map(([kind, value]) => ({ kind, value, text: value })))) })
  await waitFor(() => expect(screen.getByRole('combobox', { name: '직무' })).toHaveValue('other'))
  expect(server.writes).toHaveLength(1)
  expect(screen.queryByRole('alert')).toBeNull()
})

it('keeps editing locked after an initial read failure until a successful retry', async () => {
  const server = profileApi()
  server.failRead = true
  settings()
  await screen.findByRole('alert')
  expect(screen.getByRole('textbox', { name: '소속' })).toBeDisabled()
  server.failRead = false
  fireEvent.click(screen.getByRole('button', { name: '다시 불러오기' }))
  await waitFor(() => expect(screen.getByRole('textbox', { name: '소속' })).toHaveValue('초기 회로팀'))
  expect(screen.getByRole('textbox', { name: '소속' })).toBeEnabled()
})
