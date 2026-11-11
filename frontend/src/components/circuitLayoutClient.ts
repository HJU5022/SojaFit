import type { LayoutGraph, LayoutResult } from './circuitLayout'

type LayoutResponse = { requestId: number; result?: LayoutResult; error?: string }
type Pending = { resolve: (result: LayoutResult) => void; reject: (error: Error) => void; timeout: ReturnType<typeof setTimeout> }

let worker: Worker | null = null
let requestId = 0
const pending = new Map<number, Pending>()

function rejectAll(message: string) {
  pending.forEach(item => {
    clearTimeout(item.timeout)
    item.reject(new Error(message))
  })
  pending.clear()
  worker = null
}

function getWorker() {
  if (typeof Worker === 'undefined') return null
  if (worker) return worker
  worker = new Worker(new URL('../workers/circuitLayout.worker.ts', import.meta.url), { type: 'module' })
  worker.addEventListener('message', (event: MessageEvent<LayoutResponse>) => {
    const item = pending.get(event.data.requestId)
    if (!item) return
    pending.delete(event.data.requestId)
    clearTimeout(item.timeout)
    if (event.data.result) item.resolve(event.data.result)
    else item.reject(new Error(event.data.error ?? '회로 배치를 계산하지 못했습니다.'))
  })
  worker.addEventListener('error', () => rejectAll('회로 배치 Web Worker가 중단되었습니다.'))
  return worker
}

export function requestCircuitLayout(graph: LayoutGraph): Promise<LayoutResult> {
  const instance = getWorker()
  if (!instance) return Promise.reject(new Error('Web Worker를 사용할 수 없습니다.'))
  const id = ++requestId
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pending.delete(id)
      reject(new Error('회로 배치 계산 시간이 초과되었습니다.'))
    }, 5000)
    pending.set(id, { resolve, reject, timeout })
    instance.postMessage({ requestId: id, graph })
  })
}
