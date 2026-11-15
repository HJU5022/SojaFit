import { StrictMode, useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import DeploymentUpdate from './DeploymentUpdate'

const html = (version: string) => `<div id="root"></div><script type="module" src="/assets/index-${version}.js"></script><link rel="stylesheet" href="/assets/index-${version}.css">`
const reload = vi.fn()
const fetcher = vi.fn()
let entry: HTMLDivElement
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', fetcher.mockReset().mockImplementation(async () => new Response(html('new'), { headers: { 'Content-Type': 'text/html' } })))
  reload.mockReset()
  vi.stubGlobal('window', Object.create(window, { location: { value: { ...window.location, reload } } }))
  entry = document.createElement('div'); entry.innerHTML = html('old'); document.body.append(entry)
})
afterEach(() => { cleanup(); entry.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })
async function check() { await act(async () => { await vi.advanceTimersByTimeAsync(60_000) }) }

it('detects changed assets without reloading, then applies explicitly at the current address', async () => {
  render(<DeploymentUpdate />)
  await check()
  expect(screen.getByRole('status', { name: '화면 업데이트' })).toHaveTextContent('새 버전')
  expect(reload).not.toHaveBeenCalled()
  expect(fetcher).toHaveBeenCalledWith('/index.html', expect.objectContaining({ cache: 'no-store', credentials: 'omit' }))
  fireEvent.click(screen.getByRole('button', { name: '새 버전 적용' }))
  expect(reload).toHaveBeenCalledTimes(1)
})

function Drafts() {
  const [text, setText] = useState('질문 초안')
  const [files, setFiles] = useState([new File(['netlist'], 'test.net')])
  const [busy, setBusy] = useState(true)
  return <section data-refresh-blocked={Boolean(text || files.length || busy)}>
    <textarea aria-label="질문" value={text} onChange={event => setText(event.target.value)} />
    {files.map(file => <span key={file.name}>{file.name}</span>)}
    <button onClick={() => setFiles([])}>첨부 해제</button><button onClick={() => setBusy(false)}>작업 완료</button>
  </section>
}
it('keeps controlled text, selected files and work intact, and unlocks only after all are cleared', async () => {
  render(<><DeploymentUpdate /><Drafts /></>)
  await check()
  const apply = screen.getByRole('button', { name: '새 버전 적용' })
  expect(apply).toBeDisabled()
  expect(screen.getByLabelText('질문')).toHaveValue('질문 초안')
  expect(screen.getByText('test.net')).toBeVisible()
  fireEvent.change(screen.getByLabelText('질문'), { target: { value: '' } })
  fireEvent.click(screen.getByText('첨부 해제'))
  await act(async () => {})
  expect(apply).toBeDisabled()
  fireEvent.click(screen.getByText('작업 완료'))
  await act(async () => {})
  expect(apply).toBeEnabled()
  fireEvent.click(apply)
  expect(reload).toHaveBeenCalledTimes(1)
})

it('rechecks autofilled credentials at click time and never writes input to browser storage', async () => {
  const local = vi.spyOn(Storage.prototype, 'setItem')
  render(<><DeploymentUpdate /><input aria-label="비밀번호" type="password" /></>)
  await check()
  const password = screen.getByLabelText('비밀번호') as HTMLInputElement
  password.value = 'test-password-only'
  fireEvent.click(screen.getByRole('button', { name: '새 버전 적용' }))
  expect(reload).not.toHaveBeenCalled()
  expect(password.value).toBe('test-password-only')
  expect(local).not.toHaveBeenCalled()
})

it('blocks open dialogs and ordinary edited forms, and clears the block after closing/resetting', async () => {
  render(<><DeploymentUpdate /><dialog open>생성 창</dialog><input aria-label="수량" defaultValue="1" /></>)
  await check()
  const apply = screen.getByRole('button', { name: '새 버전 적용' })
  expect(apply).toBeDisabled()
  document.querySelector('dialog')!.removeAttribute('open')
  fireEvent.change(screen.getByLabelText('수량'), { target: { value: '10' } })
  await act(async () => {})
  expect(apply).toBeDisabled()
  fireEvent.change(screen.getByLabelText('수량'), { target: { value: '1' } })
  await act(async () => {})
  expect(apply).toBeEnabled()
})

it('ignores cancelled dialog inputs and saved controlled settings, but respects the settings dirty marker', async () => {
  const view = render(<><DeploymentUpdate /><dialog><input type="file" /><input type="email" defaultValue="cancelled@example.test" /></dialog>
    <form data-refresh-managed data-refresh-blocked={false}><select defaultValue="saved"><option value="">빈 값</option><option value="saved">저장된 설정</option></select></form></>)
  await check()
  expect(screen.getByRole('button', { name: '새 버전 적용' })).toBeEnabled()
  view.rerender(<><DeploymentUpdate /><form data-refresh-managed data-refresh-blocked={true}><input value="수정한 설정" readOnly /></form></>)
  await act(async () => {})
  expect(screen.getByRole('button', { name: '새 버전 적용' })).toBeDisabled()
})

it('detects stylesheet-only deployment changes and does not run on the Vite development entry', async () => {
  fetcher.mockResolvedValue(new Response(html('old').replace('index-old.css', 'index-new.css')))
  const view = render(<DeploymentUpdate />)
  await check()
  expect(screen.getByRole('button', { name: '새 버전 적용' })).toBeEnabled()
  view.unmount(); fetcher.mockClear()
  entry.querySelector('script')!.setAttribute('src', '/src/main.tsx')
  render(<DeploymentUpdate />)
  await check()
  expect(fetcher).not.toHaveBeenCalled()
})

it('detects a new build even when only public assets changed and bundle paths stayed identical', async () => {
  const meta = document.createElement('meta'); meta.name = 'sojafit-build'; meta.content = 'build-before'; entry.append(meta)
  fetcher.mockResolvedValue(new Response(`<meta name="sojafit-build" content="build-after">${html('old')}`))
  render(<DeploymentUpdate />)
  await check()
  expect(screen.getByRole('button', { name: '새 버전 적용' })).toBeEnabled()
})

it.each(['unchanged', 'bad-html', 'http-error', 'offline'])('leaves the screen alone on %s', async kind => {
  if (kind === 'offline') fetcher.mockRejectedValue(new Error('offline'))
  else fetcher.mockResolvedValue(new Response(kind === 'unchanged' ? html('old') : '<div>proxy error</div>', { status: kind === 'http-error' ? 503 : 200 }))
  render(<DeploymentUpdate />)
  await check()
  expect(screen.queryByRole('status', { name: '화면 업데이트' })).not.toBeInTheDocument()
  expect(reload).not.toHaveBeenCalled()
})

it('bounds requests on focus/reconnect and skips hidden tabs', async () => {
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
  render(<StrictMode><DeploymentUpdate /></StrictMode>)
  await check()
  expect(fetcher).not.toHaveBeenCalled()
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
  expect(fetcher).toHaveBeenCalledTimes(1)
  fireEvent.focus(window); fireEvent.online(window); fireEvent.focus(window)
  expect(fetcher).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); fireEvent.focus(window) })
  expect(fetcher).toHaveBeenCalledTimes(2)
})

it('aborts stalled requests after five seconds and cleans up on unmount', async () => {
  fetcher.mockReturnValue(new Promise(() => {}))
  const view = render(<DeploymentUpdate />)
  await check()
  const signal = fetcher.mock.calls[0][1].signal as AbortSignal
  expect(signal.aborted).toBe(false)
  fireEvent.focus(window); fireEvent.online(window)
  expect(fetcher).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000) })
  expect(signal.aborted).toBe(true)
  view.unmount()
  await check()
  expect(fetcher).toHaveBeenCalledTimes(1)
})

it('checks within sixty seconds even when focus checks occur between periodic checks', async () => {
  render(<DeploymentUpdate />)
  await check()
  expect(fetcher).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(50_000); fireEvent.focus(window) })
  expect(fetcher).toHaveBeenCalledTimes(2)
  await check()
  expect(fetcher).toHaveBeenCalledTimes(3)
})

it('aborts an active check on unmount and ignores its late response', async () => {
  let finish!: (value: Response) => void
  fetcher.mockImplementation(() => new Promise<Response>(resolve => { finish = resolve }))
  const view = render(<StrictMode><DeploymentUpdate /></StrictMode>)
  await check()
  const signal = fetcher.mock.calls[0][1].signal as AbortSignal
  view.unmount()
  expect(signal.aborted).toBe(true)
  await act(async () => { finish(new Response(html('new'))) })
  expect(screen.queryByRole('status', { name: '화면 업데이트' })).not.toBeInTheDocument()
  expect(reload).not.toHaveBeenCalled()
})
