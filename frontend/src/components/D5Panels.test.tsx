import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import EvidencePanel from './EvidencePanel'
import InterruptForm from './InterruptForm'
import JudgementTable from './JudgementTable'
import RunStatus from './RunStatus'
import ProfileHints from './ProfileHints'
import ConversationPanel from './ConversationPanel'

const officialCitation = { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'MAXIMUM RATINGS', row: 'VRRM',
  source_url: 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf', outline_page: 4 }

it('opens deduplicated official datasheet and outline pages with a conservative package boundary', () => {
  render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: true,
    checks: [{ code: 'VRRM', citation: officialCitation }, { code: 'IF', citation: { ...officialCitation, row: 'IF' } }],
    package_citation: { ...officialCitation, page: 4 },
  }} />)
  const documentLink = screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })
  expect(documentLink).toHaveAttribute('href', `${officialCitation.source_url}#page=1`)
  expect(documentLink).toHaveAttribute('target', '_blank')
  expect(documentLink).toHaveAttribute('rel', 'noreferrer noopener')
  expect(screen.getByRole('link', { name: '패키지 외형 4쪽 열기' })).toHaveAttribute('href', `${officialCitation.source_url}#page=4`)
  expect(screen.getByText('기판 변경 가능성 있음')).toBeInTheDocument()
  expect(screen.getByText('패키지가 달라질 수 있다는 뜻이며 납땜·재배선 방법을 뜻하지 않습니다.')).toBeInTheDocument()
})

it.each([undefined, 'javascript:alert(1)', 'file:///tmp/SS34.pdf', 'http://example.com/SS34.pdf'])(
  'keeps citation coordinates without a fake link for unsafe or missing source %s', source_url => {
    render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'NOT_VERIFIED',
      checks: [{ code: 'VRRM', citation: { ...officialCitation, source_url } }],
    }} />)
    expect(screen.getByText('SS34L SERIES_C2103.pdf')).toBeInTheDocument()
    expect(screen.getByText('1쪽 · MAXIMUM RATINGS · VRRM')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText('패키지 변경 여부 확인 필요')).toBeInTheDocument()
  },
)

it('keeps the official document link when an outline page is missing and never promises direct replacement', () => {
  render(<EvidencePanel evidence={[]} candidate={{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', board_change: false,
    checks: [{ code: 'VRRM', citation: { ...officialCitation, outline_page: null } }],
  }} />)
  expect(screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /패키지 외형/ })).not.toBeInTheDocument()
  expect(screen.getByText('동일 패키지 가능성')).toBeInTheDocument()
  expect(screen.getByText('데이터시트 패키지 기준이며 직접 교체 보증이 아닙니다.')).toBeInTheDocument()
})

const startRun = vi.fn()
let mockedRunState: any = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
vi.mock('../api/conversations', async () => {
  const actual = await vi.importActual<typeof import('../api/conversations')>('../api/conversations')
  return { ...actual, listThreads: vi.fn().mockResolvedValue([]), createThread: vi.fn().mockResolvedValue({ id: 'thread-1' }) }
})
vi.mock('../hooks/useRunStream', () => ({
  useRunStream: () => ({
    state: mockedRunState,
    start: startRun, resume: vi.fn(), cancel: vi.fn(), reset: vi.fn(),
  }),
}))

function renderConversation(props: Partial<React.ComponentProps<typeof ConversationPanel>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><ConversationPanel projectId={1} targetRef="D1" onResult={vi.fn()} {...props} /></QueryClientProvider>)
}

it('renders evidence coordinates exactly without inventing text', () => {
  render(<EvidencePanel evidence={[{ document: 'sheet.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: '', citation_number: '7' }]} />)
  expect(screen.getByText('sheet.pdf')).toBeInTheDocument()
  expect(screen.getByText('2쪽 · RATINGS · VRRM')).toBeInTheDocument()
  expect(screen.getByText('인용 7')).toBeInTheDocument()
})

it('opens evidence details from supplied citation fields without fabricating a PDF', () => {
  render(<EvidencePanel evidence={[{ document: 'sheet.pdf', page: 2, table: 'RATINGS', row: 'VRRM', section: 'Absolute maximum', citation_number: '7' }]} />)
  const trigger = screen.getByRole('button', { name: /sheet\.pdf/ })
  trigger.focus()
  fireEvent.click(trigger)
  const dialog = screen.getByRole('dialog', { name: '데이터시트 근거 상세' })
  expect(within(dialog).getByText('Absolute maximum')).toBeInTheDocument()
  expect(within(dialog).getByText('저장소에 원문이 제공되지 않은 경우 PDF 내용을 대신 표시하지 않습니다.')).toBeInTheDocument()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(trigger).toHaveFocus()
})

it('maps only backend verdict codes and always shows the disclaimer', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34', verdict: 'ROLE_SUFFICIENT', board_change: true }] }} />)
  expect(screen.getByText('역할상 충분')).toBeInTheDocument()
  expect(screen.getByText('필요')).toBeInTheDocument()
  expect(screen.getByText('같은 동작은 보장하지 않습니다.')).toBeInTheDocument()
})

it('shows candidate details with explicit missing values', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34', verdict: 'NOT_VERIFIED', checks: [{ code: 'IF', value: null, unit: 'A' }] }] }} />)
  fireEvent.click(screen.getByRole('button', { name: 'SS34 상세' }))
  const dialog = screen.getByRole('dialog', { name: '후보 상세' })
  expect(within(dialog).getAllByText('MISSING')).toHaveLength(2)
  expect(within(dialog).getByText('문서로 확인 안 됨')).toBeInTheDocument()
})

it('shows the requirement, calculation, candidate value, result, and citation together', () => {
  render(<JudgementTable judgement={{ kind: 'judge', roles: ['R01'], role_evidence: [], shown: [], unverified: [], capped: false,
    results: [{ part: 'SS34L', verdict: 'ROLE_SUFFICIENT', checks: [{ code: 'VRRM', tier: 'required', op: '>=',
      basis: '입력 최대 전압 12 V × 안전 여유 1.25', threshold: 15, value: 40, unit: 'V', condition: 'TA=25°C',
      result: 'pass', why: '후보 정격이 요구 기준 이상입니다.', citation: officialCitation }] }] }} />)
  fireEvent.click(screen.getByRole('button', { name: 'SS34L 상세' }))
  const dialog = screen.getByRole('dialog', { name: '후보 상세' })
  expect(within(dialog).getByRole('table', { name: 'SS34L 판정 조건표' })).toBeInTheDocument()
  expect(within(dialog).getByText('입력 최대 전압 12 V × 안전 여유 1.25')).toBeInTheDocument()
  expect(within(dialog).getByText('≥ 15 V')).toBeInTheDocument()
  expect(within(dialog).getByText('40 V')).toBeInTheDocument()
  expect(within(dialog).getByText('통과')).toBeInTheDocument()
  expect(within(dialog).getByRole('link', { name: 'VRRM 근거 열기' })).toHaveAttribute('href', `${officialCitation.source_url}#page=1`)
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
  render(<InterruptForm interrupt={{ missing: ['v_in_max'], role_choices: ['R01', 'R02'], question: '값을 알려 주세요.' }} busy={false} onSubmit={submit} />)
  const button = screen.getByRole('button', { name: '같은 실행 계속하기' })
  expect(button).toBeDisabled()
  fireEvent.change(screen.getByLabelText('회로 역할'), { target: { value: 'R02' } })
  fireEvent.change(screen.getByLabelText('입력 전원 최대 전압'), { target: { value: '5 V' } })
  fireEvent.click(button)
  expect(submit).toHaveBeenCalledWith({ v_in_max: '5 V' }, 'R02')
})

it('translates condition keys into Korean labels', () => {
  render(<InterruptForm interrupt={{ missing: ['v_in_max'], question: '값을 알려 주세요.' }} busy={false} onSubmit={vi.fn()} />)
  expect(screen.getByLabelText('입력 전원 최대 전압')).toBeInTheDocument()
})

it('uses user-facing analysis wording and offers a retry with the submitted inputs', async () => {
  startRun.mockClear()
  renderConversation()
  expect(screen.queryByText('분석 대화')).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '대체 가능성 분석 흐름' })).not.toBeInTheDocument()
  expect(screen.queryByText('회로 입력 확인')).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'D1 분석 준비' })).not.toBeInTheDocument()
  expect(screen.queryByText('질문과 실제 사용 조건을 입력하면 대체 가능성 분석을 시작합니다.')).not.toBeInTheDocument()
  expect(screen.queryByText('대상 D1')).not.toBeInTheDocument()
  expect(screen.queryByText('질문과 확인된 조건만 전송합니다.')).not.toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toHaveAttribute('rows', '1')
  expect(screen.queryByText('먼저 대상 부품을 선택하세요.')).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '교체 가능한가요?' } })
  expect(screen.queryByLabelText('사용 조건 (선택)')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '사용 조건 추가(선택)' }))
  const conditionsInput = screen.getByLabelText('사용 조건 (선택)')
  const conditionsPanel = conditionsInput.closest('.optional-conditions')
  const composer = conditionsInput.closest('.composer')
  const closeConditions = screen.getByRole('button', { name: '사용 조건 닫기' })
  expect(conditionsPanel?.previousElementSibling).toHaveClass('composer-entry')
  expect(closeConditions.previousElementSibling).toBe(conditionsPanel)
  expect(composer?.lastElementChild).toBe(closeConditions)
  fireEvent.change(conditionsInput, { target: { value: '5 V' } })
  expect(within(screen.getByRole('group', { name: '분석 입력 도구' })).getByRole('button', { name: '분석하기' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '분석 취소' })).not.toBeInTheDocument()
  expect(screen.queryByText('D5 실행 흐름')).not.toBeInTheDocument()
  expect(screen.queryByText('우측 회로 탭에서 교체할 부품을 선택하세요.')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '분석하기' }))
  await waitFor(() => expect(screen.getByRole('button', { name: '다시 분석하기' })).toBeInTheDocument())
  fireEvent.click(screen.getByRole('button', { name: '다시 분석하기' }))
  await waitFor(() => expect(startRun).toHaveBeenCalledTimes(2))
})

it('replaces the analysis action with cancel only while analysis is running', () => {
  mockedRunState = { status: 'running', runId: 'run-1', stage: '검색' }
  renderConversation()
  expect(within(screen.getByRole('group', { name: '분석 입력 도구' })).getByRole('button', { name: '분석 취소' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '분석하기' })).not.toBeInTheDocument()
  mockedRunState = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
})

it('submits with Enter and keeps Shift+Enter for a line break', async () => {
  startRun.mockClear()
  renderConversation()
  const question = screen.getByLabelText('질문')
  fireEvent.change(question, { target: { value: '교체 가능한가요?' } })
  fireEvent.keyDown(question, { key: 'Enter', shiftKey: true })
  expect(startRun).not.toHaveBeenCalled()
  fireEvent.keyDown(question, { key: 'Enter' })
  await waitFor(() => expect(startRun).toHaveBeenCalledTimes(1))
})

it('shows a scrollbar only after the question grows beyond six lines', () => {
  renderConversation()
  const question = screen.getByLabelText('질문')
  Object.defineProperty(question, 'scrollHeight', { configurable: true, value: 180 })
  fireEvent.input(question)
  expect(question).toHaveStyle({ height: '156px', overflowY: 'auto' })
  Object.defineProperty(question, 'scrollHeight', { configurable: true, value: 90 })
  fireEvent.input(question)
  expect(question).toHaveStyle({ height: '90px', overflowY: 'hidden' })
})

it('exposes evidence and candidate comparison callbacks in the final answer', () => {
  const showEvidence = vi.fn()
  const showJudgement = vi.fn()
  mockedRunState = { status: 'completed', runId: 'run-1', result: { answer: '교체 가능합니다.', evidence: [], judgement: { kind: 'find', shown: [], unverified: [] } } }
  renderConversation({ onShowEvidence: showEvidence, onShowJudgement: showJudgement })
  fireEvent.click(screen.getByRole('button', { name: '근거 보기' }))
  fireEvent.click(screen.getByRole('button', { name: '후보 비교 결과 보기' }))
  expect(showEvidence).toHaveBeenCalledTimes(1)
  expect(showJudgement).toHaveBeenCalledTimes(1)
  mockedRunState = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
})

it('preserves the structured answer line breaks from the backend', () => {
  mockedRunState = { status: 'completed', runId: 'run-1', result: { answer: '판정\n| 조건 | 결과 |\n| VRRM | 통과 |', evidence: [], judgement: {} } }
  renderConversation()
  expect(screen.getByText(/판정\s+\| 조건 \| 결과 \|/)).toHaveClass('answer-text')
  mockedRunState = { status: 'failed', runId: 'run-1', error: { code: 'FAIL', message: '분석 연결 오류', requestId: '' } }
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
