import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import PricePanel from './PricePanel'
import { failure, network, priceResult, unavailable } from '../test/network'

afterEach(() => vi.unstubAllGlobals())
it('fetches on opening, renders prices and discards them on close or part changes', async () => {
  let calls = 0
  network(() => { calls++; return Response.json(priceResult) })
  const write = vi.spyOn(Storage.prototype, 'setItem')
  const view = render(<PricePanel parts={['SS34']} />)
  expect(calls).toBe(0)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('7.77 XXX')).toBeInTheDocument()
  expect(screen.getByText('시험 재고')).toBeInTheDocument()
  expect(screen.getByText('2026-11-09T00:00:00Z')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '판매처에서 확인' })).toHaveAttribute('href', 'https://example.test/p/2')
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 닫기' }))
  expect(screen.queryByText('7.77 XXX')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await screen.findByText('7.77 XXX'); expect(calls).toBe(2)
  view.rerender(<PricePanel parts={['1N4148']} />)
  expect(screen.queryByText('7.77 XXX')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '가격·재고 조회' })).toBeInTheDocument()
  expect(write).not.toHaveBeenCalled(); write.mockRestore()
})
it('ignores pending responses after the part list changes', async () => {
  let finish!: (response: Response) => void
  network(() => new Promise((resolve) => { finish = resolve }))
  const view = render(<PricePanel parts={['SS34']} />)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await waitFor(() => expect(finish).toBeTypeOf('function'))
  view.rerender(<PricePanel parts={['1N4148']} />)
  await act(async () => { finish(Response.json(priceResult)) })
  expect(screen.queryByText('7.77 XXX')).not.toBeInTheDocument()
})
it('shows unavailable and common errors without fabricated prices', async () => {
  let failed = false
  network(() => failed ? failure('VALIDATION_ERROR', '품번을 확인해 주세요.', 422) : Response.json(unavailable))
  render(<PricePanel parts={['SS34']} />)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText(unavailable.message)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 닫기' })); failed = true
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('품번을 확인해 주세요.')
  expect(screen.getByRole('alert')).toHaveTextContent('req-test')
})
it('handles supplier fields that are null in the canonical price response', async () => {
  network(() => Response.json({ available: true, source: 'Mouser Electronics', fetched_at: '2026-11-09T00:00:00Z', parts: [{ part_number: 'SS34', manufacturer: null, price_breaks: [{ quantity: null, price: null, currency: null }], availability: null, product_url: null }] }))
  render(<PricePanel parts={['SS34']} />)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('제조사 정보 없음')).toBeInTheDocument()
  expect(screen.getByText('재고 정보 없음')).toBeInTheDocument()
  expect(screen.getByText('가격 정보 없음')).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: '판매처에서 확인' })).not.toBeInTheDocument()
})
