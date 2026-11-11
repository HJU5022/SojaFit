import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { failure, network } from '../test/network'
import { demo, first, second, summary, openWorkbench } from '../test/projects'

afterEach(() => vi.unstubAllGlobals())
it('wires the selected demo original and removes it when an uploaded project is selected', async () => {
  const proMicro = { ...demo, id: 'pro_micro', name: 'SparkFun Pro Micro v13', schematic: {
    image_url: '/circuit-schematics/pro_micro.png', original_url: 'https://cdn.sparkfun.com/pro-micro.pdf',
    source_repo: 'https://github.com/sparkfun/Pro_Micro', source_commit: 'a'.repeat(40),
    license: 'CC BY-SA 4.0', license_evidence_url: 'https://github.com/sparkfun/Pro_Micro', attribution: 'SparkFun Electronics',
  } }
  const selected = { ...first, demo_id: 'pro_micro' }
  network(path => Response.json(path === '/api/demo-circuits' ? [demo, proMicro] : path === '/api/projects' ? [summary(selected), summary(second)] : path === '/api/projects/11' ? selected : path === '/api/projects/12' ? second : []))
  openWorkbench('/app?projectId=11&targetRef=D1')
  expect(await screen.findByRole('img', { name: 'SparkFun Pro Micro v13 원본 회로도' })).toHaveAttribute('src', '/circuit-schematics/pro_micro.png')
  fireEvent.click(screen.getByRole('tab', { name: '연결 개념도' }))
  expect(screen.getByRole('img', { name: 'D1 주변 연결 개념도' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /^프로젝트$/ }))
  fireEvent.click(await screen.findByRole('button', { name: second.name }))
  expect(await screen.findByText('업로드한 넷리스트에는 원본 회로도 이미지와 부품 좌표가 포함되지 않습니다.')).toBeInTheDocument()
  expect(screen.queryByRole('tab', { name: '원본 회로도' })).not.toBeInTheDocument()
})
it('프로젝트 선택 전에도 검증된 데모 원본 회로도를 보여준다', async () => {
  const previewDemo = { ...demo, schematic: {
    image_url: '/circuit-schematics/breadboard_supply.png', original_url: 'https://example.com/original.pdf',
    source_repo: 'https://example.com/repository', source_commit: 'a'.repeat(40),
    license: 'CC BY 4.0', license_evidence_url: 'https://example.com/license', attribution: 'Example Author',
  } }
  network(path => Response.json(path === '/api/demo-circuits' ? [previewDemo] : []))
  openWorkbench()
  expect(await screen.findByRole('img', { name: '시험 전원 회로 원본 회로도' })).toHaveAttribute('src', '/circuit-schematics/breadboard_supply.png')
  expect(screen.getByRole('button', { name: '정보 패널 접기' })).toBeInTheDocument()
})
it('shows a focused analysis landing before a project is selected', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.getByRole('heading', { name: '회로에 맞는 대체 부품을 찾아보세요' })).toBeInTheDocument()
  expect(screen.queryByText('빠른 시작', { selector: 'span' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '회로 작업대' })).not.toBeInTheDocument()
  expect(screen.queryByRole('list', { name: '분석 진행 단계' })).not.toBeInTheDocument()
  expect(screen.getByRole('textbox', { name: '질문' })).toBeEnabled()
  expect(screen.queryByRole('textbox', { name: '사용 조건 (선택)' })).not.toBeInTheDocument()
  const conditionsToggle = screen.getByRole('button', { name: '사용 조건 추가(선택)' })
  expect(conditionsToggle).toHaveAttribute('aria-expanded', 'false')
  fireEvent.click(conditionsToggle)
  const conditions = screen.getByRole('textbox', { name: '사용 조건 (선택)' })
  expect(conditions).toBeEnabled()
  expect(screen.getByText('사용 조건 (선택)', { selector: 'label' })).toHaveClass('sr-only')
  expect(screen.getByRole('button', { name: '기존 프로젝트 열기' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '분석 시작' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '가격·재고 조회' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '정보 패널 접기' })).toBeInTheDocument()
  const suggestion = screen.getByRole('button', { name: 'D1을 SS34로 바꿔도 되나요?' })
  fireEvent.click(suggestion)
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('D1을 SS34로 바꿔도 되나요?')
  fireEvent.click(screen.getByRole('button', { name: '기존 프로젝트 열기' }))
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
})

it('introduces the implemented service flow and returns focus to the landing question', () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const serviceHeadings = within(screen.getByRole('main', { name: '분석 대화 작업면' })).getAllByRole('heading', { level: 2 }).map(heading => heading.textContent)
  expect(serviceHeadings).toEqual([
    '회로 안에서 역할을 먼저 봅니다',
    '후보와 근거를 한 화면에서 비교합니다',
    '마지막 결정은 사람이 내립니다',
    '회로에서 시작해, 근거로 결정하세요',
  ])
  fireEvent.click(screen.getByRole('button', { name: '질문 입력하기' }))
  expect(screen.getByRole('textbox', { name: '질문' })).toHaveFocus()
})

it('keeps the service introduction out of a selected project workbench', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : path === '/api/projects' ? [summary(first)] : []))
  openWorkbench('/app?projectId=11')
  expect(await screen.findByRole('list', { name: '분석 진행 단계' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '회로 작업대' })).not.toBeInTheDocument()
  expect(screen.queryByText('부품 대체 분석')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '결과 보기' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '프로젝트 만들기' })).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: '회로 안에서 역할을 먼저 봅니다' })).not.toBeInTheDocument()
})

it('keeps the landing draft through project creation and restores it in the workbench composer', async () => {
  network((path, init) => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects' && init.method === 'POST') return Response.json(first, { status: 201 })
    if (path === '/api/projects/11') return Response.json(first)
    if (path === '/api/projects') return Response.json([summary(first)])
    return Response.json([])
  })
  openWorkbench()
  const question = screen.getByRole('textbox', { name: '질문' })
  fireEvent.click(screen.getByRole('button', { name: '사용 조건 추가(선택)' }))
  const conditions = screen.getByRole('textbox', { name: '사용 조건 (선택)' })
  fireEvent.change(question, { target: { value: 'D1을 SS34로 바꿔도 되나요?' } })
  fireEvent.change(conditions, { target: { value: '12V, 1A' } })
  fireEvent.click(screen.getByRole('button', { name: '분석 시작' }))
  expect(screen.getByRole('dialog', { name: '프로젝트 만들기' })).toBeInTheDocument()
  expect(question).toHaveValue('D1을 SS34로 바꿔도 되나요?')
  expect(conditions).toHaveValue('12V, 1A')
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '내 전원 회로' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  expect(await screen.findByRole('list', { name: '분석 진행 단계' })).toBeInTheDocument()
  await waitFor(() => expect(screen.getByRole('textbox', { name: '질문' })).toHaveValue('D1을 SS34로 바꿔도 되나요?'))
  expect(screen.getByRole('textbox', { name: '사용 조건 (선택)' })).toHaveValue('12V, 1A')
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
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' }))
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
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' }))
  fireEvent.click(await screen.findByRole('button', { name: '새 프로젝트 만들기' }))
  fireEvent.change(screen.getByLabelText('새 프로젝트 이름'), { target: { value: '늦은 생성' } })
  await screen.findByRole('option', { name: demo.name })
  fireEvent.change(screen.getByLabelText('데모 회로'), { target: { value: demo.id } })
  fireEvent.click(screen.getByRole('button', { name: '데모로 만들기' }))
  await waitFor(() => expect(finish).toBeDefined())
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  fireEvent.click(screen.getByRole('button', { name: '프로젝트 열기' }))
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
  toggle.focus()
  fireEvent.click(toggle)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '닫기' }))
  await waitFor(() => expect(toggle).toHaveFocus())
  const judgement = screen.getByRole('tab', { name: '후보 비교' })
  fireEvent.click(judgement)
  expect(judgement).toHaveAttribute('aria-selected', 'true')
})

it('organizes the workbench as a functional rail, analysis surface, and adjustable information console', async () => {
  vi.stubGlobal('innerWidth', 1440)
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : path === '/api/projects' ? [summary(first)] : []))
  openWorkbench('/app?projectId=11')
  expect(screen.getByRole('navigation', { name: '작업 메뉴' })).toBeInTheDocument()
  expect(screen.getByRole('main', { name: '분석 대화 작업면' })).toBeInTheDocument()
  expect(screen.getByRole('complementary', { name: '회로와 분석 정보' })).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '회로' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByRole('tab', { name: '진행 기록' })).toBeInTheDocument()
  expect(screen.queryByRole('slider', { name: '정보 패널 너비' })).not.toBeInTheDocument()
  const handle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  expect(handle).toHaveAttribute('aria-valuemax', '720')
  fireEvent.pointerDown(handle, { clientX: 900, pointerId: 3 })
  fireEvent.pointerMove(handle, { clientX: 500, pointerId: 3 })
  fireEvent.pointerUp(handle, { pointerId: 3 })
  expect(handle).toHaveAttribute('aria-valuenow', '720')
  fireEvent.click(screen.getByRole('button', { name: '정보 패널 접기' }))
  expect(screen.getByRole('button', { name: '정보 패널 펼치기' })).toBeInTheDocument()
})

it('shows the left rail as a named work menu by default', () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const rail = screen.getByRole('navigation', { name: '작업 메뉴' })
  expect(rail).toHaveClass('expanded')
  expect(within(rail).getByText('작업 메뉴')).toBeVisible()
  expect(within(rail).getByText('프로젝트')).toBeVisible()
  expect(within(rail).queryByRole('button', { name: '분석 대화' })).not.toBeInTheDocument()
  expect(within(rail).getByText('승인·견적')).toBeVisible()
  expect(within(rail).queryByRole('button', { name: '계정' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '계정' }))
  expect(screen.getByRole('menu', { name: '계정 메뉴' })).toBeInTheDocument()
  expect(screen.getByRole('menuitem', { name: '로그인' })).toBeInTheDocument()
})

it('opens the project picker from the current project name', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : path === '/api/projects/11' ? first : path === '/api/projects' ? [summary(first)] : []))
  openWorkbench('/app?projectId=11')
  const projectName = await screen.findByRole('button', { name: `프로젝트 선택: ${first.name}` })
  fireEvent.click(projectName)
  expect(screen.getByRole('dialog', { name: '내 프로젝트' })).toBeInTheDocument()
})

it('resizes both desktop side panels by dragging their borders', () => {
  vi.stubGlobal('innerWidth', 1440)
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  const leftHandle = screen.getByRole('separator', { name: '작업 메뉴 너비 조절' })
  fireEvent.pointerDown(leftHandle, { clientX: 220, pointerId: 1 })
  fireEvent.pointerMove(leftHandle, { clientX: 280, pointerId: 1 })
  fireEvent.pointerUp(leftHandle, { pointerId: 1 })
  expect(leftHandle).toHaveAttribute('aria-valuenow', '280')

  const rightHandle = screen.getByRole('separator', { name: '회로 및 분석 정보 너비 조절' })
  fireEvent.pointerDown(rightHandle, { clientX: 900, pointerId: 2 })
  fireEvent.pointerMove(rightHandle, { clientX: 850, pointerId: 2 })
  fireEvent.pointerUp(rightHandle, { pointerId: 2 })
  expect(rightHandle).toHaveAttribute('aria-valuenow', '480')
})

it('searches only loaded projects and current circuit parts', async () => {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json(second)
  })
  openWorkbench('/app?projectId=11')
  const search = await screen.findByRole('searchbox', { name: '프로젝트 또는 부품 찾기' })
  fireEvent.change(search, { target: { value: 'D1' } })
  fireEvent.click(within(screen.getByRole('listbox', { name: '검색 결과' })).getByRole('option', { name: /D1.*1N4001/ }))
  expect(screen.getByText('선택한 대상: D1')).toBeInTheDocument()
})

it('guides the user from project selection to approval and exposes a mobile target picker', async () => {
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first)])
    if (path === '/api/projects/11') return Response.json(first)
    return Response.json([])
  })
  openWorkbench('/app?projectId=11')
  expect(await screen.findByRole('heading', { name: first.name })).toBeInTheDocument()
  expect(screen.getByText('대상 선택')).toBeInTheDocument()
  expect(screen.getByLabelText('질문')).toBeInTheDocument()
  expect(screen.getByText('결과 검토')).toBeInTheDocument()
  expect(screen.getByRole('tab', { name: '승인·견적' })).toBeInTheDocument()
  expect(screen.getByLabelText('질문 영역의 대상 부품')).toBeInTheDocument()
})

it('uses a single actions destination and accessible tab relationships', async () => {
  network(path => Response.json(path === '/api/demo-circuits' ? [demo] : []))
  openWorkbench()
  expect(screen.getByRole('button', { name: '승인·견적' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '승인 사례·이력' })).not.toBeInTheDocument()
  const tabs = screen.getAllByRole('tab')
  expect(tabs[0]).toHaveAttribute('aria-controls', 'panel-circuit')
  expect(screen.getByRole('tabpanel', { name: '회로' })).toHaveAttribute('aria-labelledby', tabs[0].id)
  fireEvent.keyDown(tabs[0], { key: 'ArrowRight' })
  expect(tabs[1]).toHaveFocus()
})

it('exposes search results as a keyboard-operable listbox', async () => {
  network(path => {
    if (path === '/api/demo-circuits') return Response.json([demo])
    if (path === '/api/projects') return Response.json([summary(first), summary(second)])
    return Response.json(first)
  })
  openWorkbench('/app?projectId=11')
  const search = await screen.findByRole('searchbox', { name: '프로젝트 또는 부품 찾기' })
  fireEvent.change(search, { target: { value: '회로' } })
  expect(screen.getByRole('listbox', { name: '검색 결과' })).toBeInTheDocument()
  const options = within(screen.getByRole('listbox', { name: '검색 결과' })).getAllByRole('option')
  expect(options[0]).toHaveAttribute('tabIndex', '0')
  fireEvent.keyDown(search, { key: 'ArrowDown' })
  expect(options[0]).toHaveFocus()
  fireEvent.keyDown(options[0], { key: 'ArrowDown' })
  expect(options[1]).toHaveFocus()
  fireEvent.keyDown(options[1], { key: 'ArrowUp' })
  expect(options[0]).toHaveFocus()
  fireEvent.keyDown(options[0], { key: 'Escape' })
  expect(search).toHaveFocus()
  expect(screen.queryByRole('listbox', { name: '검색 결과' })).not.toBeInTheDocument()
})

it('connects project, role, run, candidate, and citation API data without a fixture fallback', async () => {
  const result = {
    answer: '판정 완료', status: 'completed', stage: '완료', question_type: 'judge', evidence: [], price_parts: [], refusal: '', interrupt: {}, request_id: 'req-run',
    judgement: { kind: 'judge', roles: ['R01'], role_evidence: ['D1.K → GND'], shown: [], unverified: [], capped: false,
      results: [
        { part: 'SS34L', role: 'R01', verdict: 'ROLE_SUFFICIENT', checks: [{ code: 'VRRM', value: 40, unit: 'V', condition: '입력 최대 전압', citation: { document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'Ratings', row: 'VRRM', source_url: 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf', outline_page: 4 } }] },
        { part: 'OTHER', verdict: 'NOT_VERIFIED', checks: [{ code: 'VRRM', citation: { document: 'other.pdf', page: 1, source_url: 'https://services.taiwansemi.com/storage/resources/datasheet/other.pdf', outline_page: 2 } }] },
      ] },
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
  fireEvent.click(screen.getByRole('button', { name: '사용 조건 추가(선택)' }))
  fireEvent.change(screen.getByLabelText('사용 조건 (선택)'), { target: { value: '입력 최대 12 V' } })
  fireEvent.click(screen.getByRole('button', { name: '분석하기' }))
  expect(await screen.findByText('역극성 보호(직렬)')).toBeInTheDocument()
  expect(within(screen.getByLabelText('개념도 사용 조건')).getByText('입력 최대 12 V')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: '후보 비교' }))
  fireEvent.click(await screen.findByRole('button', { name: 'SS34L 후보 선택' }))
  fireEvent.click(screen.getByRole('tab', { name: '근거' }))
  expect(screen.getByText('SS34L 데이터시트 근거')).toBeInTheDocument()
  expect(screen.getByText('SS34L SERIES_C2103.pdf')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })).toHaveAttribute('href', 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf#page=1')
  expect(screen.getByRole('link', { name: '패키지 외형 4쪽 열기' })).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: 'OTHER 공식 데이터시트 열기' })).not.toBeInTheDocument()
})
