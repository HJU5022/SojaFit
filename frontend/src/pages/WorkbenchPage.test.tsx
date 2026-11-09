import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
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

it('connects project, role, run, candidate, and citation API data without a fixture fallback', async () => {
  const result = {
    answer: '판정 완료', status: 'completed', stage: '완료', question_type: 'judge', evidence: [], price_parts: [], refusal: '', interrupt: {}, request_id: 'req-run',
    profile_hints: [{ kind: 'mounting_preference', value: 'smd', text: '이 사용자는 SMD 실장을 선호한다.' }],
    judgement: { kind: 'judge', roles: ['R01'], role_evidence: ['D1.K → GND'], shown: [], unverified: [], capped: false,
      results: [{ part: 'SS34', role: 'R01', verdict: 'ROLE_SUFFICIENT', checks: [{ code: 'VRRM', value: 40, unit: 'V', condition: '입력 최대 전압', citation: { document: 'ss34.pdf', page: 3, table: 'Ratings', row: 'VRRM' } }] }] },
  }
  network((path, init) => {
    if (path === '/api/judge/roles') return Response.json([{ code: 'R01', name: '역극성 보호(직렬)' }])
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') return Response.json({ id: 'thread-1', project_id: 11 }, { status: 201 })
    if (path === '/api/projects/11/threads') return Response.json([])
    if (path === '/api/threads/thread-1/runs') return new Response([
      'event: run_started', 'data: {"run_id":"run-1","request_id":"req-run"}', '',
      'event: completed', `data: ${JSON.stringify(result)}`, '', '',
    ].join('\n'))
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await screen.findByText('D1 / 1N4001')
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: 'D1을 SS34로 바꿔도 되나요?' } })
  fireEvent.change(screen.getByLabelText('사용 조건 (선택)'), { target: { value: '입력 최대 12 V' } })
  fireEvent.click(screen.getByRole('button', { name: '질문하기' }))
  expect(await screen.findByText('역극성 보호(직렬)')).toBeInTheDocument()
  expect(within(screen.getByRole('complementary', { name: '참고(내 설정)' })).getByText('이 사용자는 SMD 실장을 선호한다.')).toBeInTheDocument()
  expect(within(screen.getByLabelText('개념도 사용 조건')).getByText('입력 최대 12 V')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '판정' }))
  fireEvent.click(await screen.findByRole('button', { name: 'SS34 후보 선택' }))
  fireEvent.click(screen.getByRole('tab', { name: '근거' }))
  expect(screen.getByText('SS34 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('ss34.pdf')).toBeInTheDocument()
})

// 키 없는 데모(DEMO_REPLAY=1)의 기록 질문 목록. 데모 회로 · 대상이 같은 것만 버튼이 된다
const recorded = [
  { id: 'v3-01', kind: '판정 + 조건 인터럽트', circuit: '시험 전원 회로', demo_id: demo.id, target: 'D1',
    question: 'D1을 TSC 1N4007G로 바꿔도 될까?', conditions: 'VIN은 최대 15V이다. ', resume: { answers: {}, role: 'R01' } },
  { id: 'demo-rating', kind: '정격 확인', circuit: '시험 전원 회로', demo_id: demo.id, target: 'C1', question: 'C1 정격은?', conditions: '', resume: null },
  { id: 'demo-find', kind: '후보 찾기', circuit: 'Franzininho DIY', demo_id: 'franzininho_diy', target: 'D1', question: 'D3 후보는?', conditions: '', resume: null },
]
const frames = (...items: [string, object][]) => new Response(items.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join(''))
const runResult = { answer: '판정 완료', status: 'completed', stage: '완료', question_type: 'candidate_judge', evidence: [], price_parts: [], refusal: '', interrupt: {}, request_id: 'req-run', judgement: {} }

it('sends a recorded demo question as a new conversation and resumes with the recorded answers', async () => {
  const sent: [string, unknown][] = []
  let threads = 0
  network((path, init) => {
    if (init.method === 'POST') sent.push([path, init.body ? JSON.parse(String(init.body)) : null])
    if (path === '/api/demo-questions') return Response.json(recorded)
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects/11/threads' && init.method === 'POST') return Response.json({ id: `thread-${++threads}`, project_id: 11 }, { status: 201 })
    if (path === '/api/projects/11/threads') return Response.json([{ id: 'old-thread', project_id: 11 }])
    if (path === '/api/threads/thread-1/runs') return frames(['run_started', { run_id: 'run-1' }],
      ['requires_input', { ...runResult, status: 'requires_input', interrupt: { missing: ['v_drop_allowed'], role_choices: ['R01', 'R02'], question: '허용 전압강하를 알려 주세요.' } }])
    if (path === '/api/runs/run-1/resume') return frames(['run_started', { run_id: 'run-1' }], ['completed', runResult])
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  const group = await screen.findByRole('group', { name: '데모 질문' })
  // 다른 데모 회로 · 다른 대상의 질문은 버튼이 없다
  expect(within(group).getAllByRole('button')).toHaveLength(1)
  fireEvent.click(within(group).getByRole('button', { name: recorded[0].question }))
  expect(await screen.findByRole('button', { name: '기록한 답으로 계속하기' })).toBeInTheDocument()
  expect(screen.getByText('기록한 답: 모름 · 역할: R01')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '같은 실행 계속하기' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('사용 조건 (선택)')).toHaveValue(recorded[0].conditions)
  fireEvent.click(screen.getByRole('button', { name: '기록한 답으로 계속하기' }))
  expect(await screen.findByText('분석이 끝났습니다.')).toBeInTheDocument()
  // 있던 대화(old-thread)가 아니라 새 대화에, 글자를 다듬지 않고 기록 그대로 보낸다
  expect(sent).toEqual([
    ['/api/projects/11/threads', null],
    ['/api/threads/thread-1/runs', { question: recorded[0].question, target_ref: 'D1', conditions: recorded[0].conditions }],
    ['/api/runs/run-1/resume', { answers: {}, role: 'R01' }],
  ])
})

it('names the demo targets when the selected part has no recorded question', async () => {
  network(path => {
    if (path === '/api/demo-questions') return Response.json(recorded.slice(0, 1))
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=C1')
  const group = await screen.findByRole('group', { name: '데모 질문' })
  expect(within(group).queryByRole('button')).not.toBeInTheDocument()
  expect(within(group).getByText('데모 질문이 있는 대상 부품: D1')).toBeInTheDocument()
})

it('hides demo questions when the server is not replaying a recording', async () => {
  const asked: string[] = []
  network(path => {
    asked.push(path)
    if (path === '/api/demo-questions') return failure('NOT_FOUND', '찾을 수 없습니다.', 404)
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json([])
  })
  openWorkbench('/app?projectId=11&targetRef=D1')
  await waitFor(() => expect(asked).toContain('/api/demo-questions'))
  await screen.findByRole('button', { name: '질문하기' })
  expect(screen.queryByRole('group', { name: '데모 질문' })).not.toBeInTheDocument()
})
