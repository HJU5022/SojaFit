import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import WorkbenchPage from '../pages/WorkbenchPage'

export const demo = { id: 'breadboard_supply', name: '시험 전원 회로' }
export const first = {
  id: 11, name: '내 전원 회로', source_kind: 'demo' as const, demo_id: demo.id,
  created_at: '2026-11-09T00:00:00Z', updated_at: '2026-11-09T00:00:00Z',
  connections: { sample_id: demo.id, status: 'verified_connectivity', components: [
    { ref: 'D1', value: '1N4001', footprint: 'Diode:THT' },
    { ref: 'C1', value: '100uF', footprint: 'Capacitor:THT' },
  ], nets: [{ name: 'GND', nodes: [{ ref: 'D1', pin: '2', pinfunction: 'K' }, { ref: 'C1', pin: '2', pinfunction: '-' }] }] },
}
export const second = {
  id: 12, name: '업로드 회로', source_kind: 'upload' as const, demo_id: null,
  created_at: '2026-11-09T01:00:00Z', updated_at: '2026-11-09T01:00:00Z',
  connections: { parts: [{ ref: 'D2', value: 'SS34', footprint: 'Diode:SMA' }],
    nets: [{ code: '1', name: 'GND', nodes: [{ ref: 'D2', pin: '2' }] }] },
}
export const summary = ({ connections: _connections, ...project }: typeof first | typeof second) => project
export function renderWithQueries(element: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return { ...render(<QueryClientProvider client={client}>{element}</QueryClientProvider>), client }
}
export function openWorkbench(path = '/app') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  function Location() { return <output aria-label="현재 경로">{useLocation().search}</output> }
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><WorkbenchPage /><Location /></MemoryRouter></QueryClientProvider>)
  return client
}
