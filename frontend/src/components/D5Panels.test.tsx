import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import EvidencePanel from './EvidencePanel'
import InterruptForm from './InterruptForm'
import JudgementTable from './JudgementTable'
import RunStatus from './RunStatus'
import ProfileHints from './ProfileHints'

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

it('selects a candidate and shows only its supplied datasheet coordinates', () => {
  const select = vi.fn()
  const candidate = { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const,
    checks: [{ code: 'VRRM', value: 40, unit: 'V', citation: { document: 'ss34.pdf', page: 3, table: 'Ratings', row: 'VRRM' } }] }
  render(<><JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [candidate] }} selectedIndex={0} onSelectCandidate={select} />
    <EvidencePanel evidence={[]} candidate={candidate} /></>)
  fireEvent.click(screen.getByRole('button', { name: 'SS34 후보 선택' }))
  expect(select).toHaveBeenCalledWith(candidate, 0)
  expect(screen.getByText('SS34 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('ss34.pdf')).toBeInTheDocument()
  expect(screen.getByText('3쪽 · Ratings · VRRM')).toBeInTheDocument()
})

it('keeps duplicate part numbers distinct by candidate index', () => {
  const select = vi.fn()
  const candidates = [
    { part: 'SS34', verdict: 'ROLE_SUFFICIENT' as const },
    { part: 'SS34', verdict: 'NOT_SUFFICIENT' as const },
  ]
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: candidates }} selectedIndex={1} onSelectCandidate={select} />)
  const buttons = screen.getAllByRole('button', { name: 'SS34 후보 선택' })
  expect(buttons[0]).toHaveAttribute('aria-pressed', 'false')
  expect(buttons[1]).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(buttons[1])
  expect(select).toHaveBeenCalledWith(candidates[1], 1)
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

it('shows role names with codes and Korean value names but sends the internal keys', () => {
  const submit = vi.fn()
  render(<InterruptForm interrupt={{ missing: ['v_in_max', 'new_key'], role_choices: ['R01', 'R08'] }} busy={false} onSubmit={submit}
    roleLabels={[{ code: 'R01', name: '역극성 보호(직렬)' }]} />)
  expect(screen.getByRole('option', { name: '역극성 보호(직렬) (R01)' })).toHaveValue('R01')
  expect(screen.getByRole('option', { name: 'R08' })).toBeInTheDocument()  // 이름을 못 받은 역할은 코드 그대로
  fireEvent.change(screen.getByLabelText('회로 역할'), { target: { value: 'R01' } })
  fireEvent.change(screen.getByLabelText('입력 전원 최대 전압'), { target: { value: '12V' } })
  fireEvent.change(screen.getByLabelText('new_key'), { target: { value: '1' } })  // 모르는 이름은 내부 이름 그대로
  fireEvent.click(screen.getByRole('button', { name: '같은 실행 계속하기' }))
  expect(submit).toHaveBeenCalledWith({ v_in_max: '12V', new_key: '1' }, 'R01')
})

it('separates a system failure from a refusal answer and keeps completion neutral', () => {
  const result = { answer: '', status: 'completed', stage: '완료', question_type: 'rating', evidence: [], judgement: {}, price_parts: [], refusal: '', interrupt: {}, request_id: 'req-1' }
  const { rerender } = render(<RunStatus state={{ status: 'completed', runId: 'run-1', result }} />)
  expect(screen.getByText('분석이 끝났습니다.')).toBeInTheDocument()
  rerender(<RunStatus state={{ status: 'refused', runId: 'run-1', result: { ...result, status: 'refused' } }} />)
  expect(screen.getByText('이 질문에는 답할 수 없어 거절했습니다.')).toBeInTheDocument()
  rerender(<RunStatus state={{ status: 'failed', runId: 'run-1', error: { code: 'RUN_FAILED', message: '실행을 완료하지 못했습니다.', requestId: 'req-1' } }} />)
  expect(screen.getByText('오류로 멈췄습니다. 실행을 완료하지 못했습니다.')).toBeInTheDocument()
})

it('shows profile hints as reference apart from evidence and nothing when empty', () => {
  const { rerender } = render(<ProfileHints hints={[{ kind: 'mounting_preference', value: 'smd', text: '이 사용자는 SMD 실장을 선호한다.' }]} />)
  expect(screen.getByRole('complementary', { name: '참고(내 설정)' })).toHaveTextContent('이 사용자는 SMD 실장을 선호한다.')
  expect(screen.getByText('판정 근거가 아니라 내 설정에서 찾은 사실입니다.')).toBeInTheDocument()
  rerender(<ProfileHints hints={[]} />)
  expect(screen.queryByRole('complementary', { name: '참고(내 설정)' })).not.toBeInTheDocument()
})
