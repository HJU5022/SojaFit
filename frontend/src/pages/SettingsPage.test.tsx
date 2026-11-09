import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import SettingsPage from './SettingsPage'
import { renderWithQueries as render } from '../test/projects'
import { failure, network } from '../test/network'

afterEach(() => vi.unstubAllGlobals())
const fact = (kind: string, value: string, text: string, version = 1) => ({ kind, value, text, version, updated_at: '2026-11-09T00:00:00Z', source: 'user_settings' })

it('loads saved facts and sends only changed fields without any user id', async () => {
  let facts = [fact('affiliation', '한빛전자', '이 사용자의 소속은 한빛전자이다.'), fact('mounting_preference', 'smd', '이 사용자는 SMD 실장을 선호한다.')]
  const sent: { method: string; body?: string }[] = []
  network((path, init) => {
    const method = init.method ?? 'GET'
    if (path === '/api/me/memory' && method === 'GET') return Response.json(facts)
    if (path === '/api/me/memory' && method === 'PATCH') {
      sent.push({ method, body: String(init.body) })
      facts = [facts[0], fact('mounting_preference', 'through_hole', '이 사용자는 스루홀 실장을 선호한다.', 2), fact('job_role', 'purchasing', '이 사용자의 직무는 구매이다.')]
      return Response.json(facts)
    }
    throw new Error(`unexpected ${method} ${path}`)
  })
  render(<SettingsPage />)
  expect(await screen.findByText('이 사용자는 SMD 실장을 선호한다.')).toBeInTheDocument()
  expect(screen.getByLabelText('소속')).toHaveValue('한빛전자')
  expect(screen.getByLabelText('소속')).toHaveAttribute('maxLength', '100')
  fireEvent.click(screen.getByRole('button', { name: '저장' }))
  expect(await screen.findByText('바뀐 칸이 없습니다.')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('직무'), { target: { value: 'purchasing' } })
  fireEvent.change(screen.getByLabelText('선호 실장 방식'), { target: { value: 'through_hole' } })
  fireEvent.click(screen.getByRole('button', { name: '저장' }))
  expect(await screen.findByText('저장했습니다.')).toBeInTheDocument()
  expect(JSON.parse(sent[0].body!)).toEqual({ job_role: 'purchasing', mounting_preference: 'through_hole' })
  expect(await screen.findByText('이 사용자는 스루홀 실장을 선호한다.')).toBeInTheDocument()
})

it('deletes one field directly and all fields only after confirmation', async () => {
  let facts = [fact('affiliation', '한빛전자', '이 사용자의 소속은 한빛전자이다.'), fact('job_role', 'student', '이 사용자의 직무는 학생이다.')]
  const deleted: string[] = []
  network((path, init) => {
    if ((init.method ?? 'GET') === 'GET') return Response.json(facts)
    if (init.method === 'DELETE') {
      deleted.push(path)
      facts = path.endsWith('?kind=job_role') ? facts.filter(item => item.kind !== 'job_role') : []
      return new Response(null, { status: 204 })
    }
    throw new Error(`unexpected ${path}`)
  })
  render(<SettingsPage />)
  fireEvent.click(await screen.findByRole('button', { name: '직무 지우기' }))
  await waitFor(() => expect(screen.queryByText('이 사용자의 직무는 학생이다.')).not.toBeInTheDocument())
  expect(deleted).toEqual(['/api/me/memory?kind=job_role'])
  fireEvent.click(screen.getByRole('button', { name: '모두 지우기' }))
  expect(deleted).toHaveLength(1)
  fireEvent.click(screen.getByRole('button', { name: '지우기 확인' }))
  expect(await screen.findByText('모두 지웠습니다.')).toBeInTheDocument()
  expect(deleted).toEqual(['/api/me/memory?kind=job_role', '/api/me/memory'])
  await waitFor(() => expect(screen.queryByText('이 사용자의 소속은 한빛전자이다.')).not.toBeInTheDocument())
})

it('shows the server validation message with its request id', async () => {
  network((_path, init) => (init.method ?? 'GET') === 'GET' ? Response.json([])
    : failure('VALIDATION_ERROR', '요청 형식이 올바르지 않습니다.', 422))
  render(<SettingsPage />)
  await waitFor(() => expect(screen.queryByText('설정을 불러오는 중입니다.')).not.toBeInTheDocument())
  fireEvent.change(screen.getByLabelText('소속'), { target: { value: '한빛전자' } })
  fireEvent.click(screen.getByRole('button', { name: '저장' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('요청 형식이 올바르지 않습니다. (요청 ID: req-test)')
})
