import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createDemo, listDemos, uploadProject } from '../api/projects'
import { getDemoStatus } from '../api/auth'
import type { Project } from '../api/projects'
import { errorMessage } from '../api/client'

export default function CircuitSetup({ onCreated }: { onCreated: (project: Project) => void }) {
  const client = useQueryClient()
  const mode = useQuery({ queryKey: ['demo-mode'], queryFn: () => getDemoStatus(), retry: false, refetchOnWindowFocus: false })
  const demoEnabled = mode.isSuccess && mode.data.enabled === true
  const demos = useQuery({ queryKey: ['demo-circuits'], queryFn: ({ signal }) => listDemos(signal), enabled: demoEnabled, retry: false })
  const [name, setName] = useState('')
  const [demoId, setDemoId] = useState('')
  const [hasFile, setHasFile] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const requests = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    requests.current = controller
    return () => { controller.abort() }
  }, [])
  async function create(kind: 'demo' | 'upload') {
    const controller = requests.current
    if (busy || !controller || controller.signal.aborted) return
    if (kind === 'demo' && !demoEnabled) return
    const input = fileInput.current
    const file = kind === 'upload' ? input?.files?.[0] : undefined
    if (!name.trim() || (kind === 'demo' ? !demoId : !file)) return
    setBusy(true); setError(null)
    try {
      const project = kind === 'demo' ? await createDemo(demoId, name, controller.signal) : await uploadProject(name, file!, controller.signal)
      if (controller.signal.aborted) return
      void client.invalidateQueries({ queryKey: ['projects'], exact: true })
      void client.invalidateQueries({ queryKey: ['project', project.id], exact: true })
      onCreated(project)
    } catch (error) { if (!controller.signal.aborted) setError(error) }
    finally { if (kind === 'upload' && input) input.value = ''; if (kind === 'upload') setHasFile(false); if (!controller.signal.aborted) setBusy(false) }
  }
  return <section className="panel" aria-label="새 회로 프로젝트">
    <h2>회로로 시작하기</h2><p>{demoEnabled ? '공개 데모 또는 UTF-8 KiCad 넷리스트(.net, 최대 5 MiB)를 선택하세요.' : 'UTF-8 KiCad 넷리스트(.net, 최대 5 MiB)를 업로드하세요.'}</p>
    <label htmlFor="project-name">새 프로젝트 이름</label>
    <input id="project-name" maxLength={200} value={name} onChange={event => setName(event.target.value)} disabled={busy} />
    {error ? <p role="alert">{errorMessage(error)}</p> : null}
    {demoEnabled && <form aria-label="데모 회로로 시작" onSubmit={event => { event.preventDefault(); void create('demo') }}>
      <h3>데모 회로로 시작</h3>
      <label htmlFor="demo-circuit">데모 회로</label>
      <select id="demo-circuit" value={demoId} onChange={event => setDemoId(event.target.value)} disabled={busy || !demos.data}>
        <option value="">데모를 선택하세요</option>
        {demos.data?.map(demo => <option key={demo.id} value={demo.id}>{demo.name}</option>)}
      </select>
      {demos.isPending && <p role="status">데모 목록을 불러오는 중입니다.</p>}
      {demos.error && <><p role="alert">{errorMessage(demos.error)}</p><button type="button" onClick={() => void demos.refetch()} disabled={demos.isFetching}>다시 불러오기</button></>}
      <button disabled={busy || !name.trim() || !demoId}>데모로 만들기</button>
    </form>}
    <form aria-label="넷리스트 첨부" onSubmit={event => { event.preventDefault(); void create('upload') }}>
      <h3>넷리스트 첨부</h3>
      <label htmlFor="netlist-file">KiCad 넷리스트</label>
      <input id="netlist-file" type="file" accept=".net" ref={fileInput} disabled={busy} required onChange={event => setHasFile(Boolean(event.target.files?.[0]))} />
      <button disabled={busy || !name.trim() || !hasFile}>파일로 만들기</button>
    </form>
    {busy && <p role="status">프로젝트를 만드는 중입니다.</p>}
  </section>
}
