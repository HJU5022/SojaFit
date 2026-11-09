import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import EvidencePanel from './EvidencePanel'
import InterruptForm from './InterruptForm'
import JudgementTable from './JudgementTable'
import RunStatus from './RunStatus'

it('renders evidence coordinates exactly without inventing text', () => {
  render(<EvidencePanel evidence={[{ document: 'sheet.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }]} />)
  expect(screen.getByText('sheet.pdf')).toBeInTheDocument()
  expect(screen.getByText('2쪽 · RATINGS · VRRM')).toBeInTheDocument()
  expect(screen.getByText('인용 7')).toBeInTheDocument()
})

it('maps only backend verdict codes and always shows the disclaimer', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: true }] }} />)
  expect(screen.getByText('역할상 충분')).toBeInTheDocument()
  expect(screen.getByText('필요')).toBeInTheDocument()
  expect(screen.getByText('같은 동작은 보장하지 않습니다.')).toBeInTheDocument()
})

it('requires missing values and a listed role before resuming', () => {
  const submit = vi.fn()
  render(<InterruptForm interrupt={{ missing: ['v_in'], role_choices: ['R01', 'R02'], question: '값을 알려 주세요.' }} busy={false} onSubmit={submit} />)
  const button = screen.getByRole('button', { name: '같은 실행 계속하기' })
  expect(button).toBeDisabled()
  fireEvent.change(screen.getByLabelText('회로 역할'), { target: { value: 'R02' } })
  fireEvent.change(screen.getByLabelText('v_in'), { target: { value: '5 V' } })
  fireEvent.click(button)
  expect(submit).toHaveBeenCalledWith({ v_in: '5 V' }, 'R02')
})

it('announces run progress through a polite live region', () => {
  render(<RunStatus state={{ status: 'running', runId: 'run-1', stage: '판정' }} />)
  expect(screen.getByText('판정 진행 중')).toHaveAttribute('aria-live', 'polite')
})
