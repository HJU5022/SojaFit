import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { focusManager, onlineManager, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import PriceLookup from './PriceLookup'
import { failure, network, priceResult } from '../test/network'
import { renderWithQueries } from '../test/projects'

afterEach(() => { vi.unstubAllGlobals(); focusManager.setFocused(undefined); onlineManager.setOnline(true) })

it('shows a server estimate for the requested quantity and waits for another click when quantity changes', async () => {
  const result = { ...priceResult, parts: [{ ...priceResult.parts[0], estimate: { quantity: 25, break_quantity: 10, unit_price: '0.10', total: '2.50', currency: 'USD' } }] }
  const fetchPrice = vi.fn((_path: string) => Response.json(result))
  network(fetchPrice)
  const { client, rerender } = renderWithQueries(<PriceLookup parts={['SS34']} quantity={25} />)
  expect(fetchPrice).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText('2.50 USD')).toBeInTheDocument()
  expect(fetchPrice.mock.calls[0][0]).toBe('/api/prices?parts=SS34&quantity=25')
  rerender(<QueryClientProvider client={client}><PriceLookup parts={['SS34']} quantity={100} /></QueryClientProvider>)
  expect(screen.queryByText('2.50 USD')).toBeNull()
  expect(fetchPrice).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await waitFor(() => expect(fetchPrice).toHaveBeenCalledTimes(2))
  expect(fetchPrice.mock.calls[1][0]).toBe('/api/prices?parts=SS34&quantity=100')
})

it('does not query with an invalid quantity and explains an unavailable estimate', async () => {
  const fetchPrice = vi.fn(() => Response.json({ ...priceResult, parts: [{ ...priceResult.parts[0], estimate: null }] }))
  network(fetchPrice)
  const { client, rerender } = renderWithQueries(<PriceLookup parts={['SS34']} quantity={0} />)
  expect(screen.getByRole('button', { name: '가격·재고 조회' })).toBeDisabled()
  expect(fetchPrice).not.toHaveBeenCalled()
  rerender(<QueryClientProvider client={client}><PriceLookup parts={['SS34']} quantity={25} /></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByText(/계산을 보류했습니다/)).toBeInTheDocument()
})

it.each(['focus', 'reconnect', 'invalidate'])('does not query again on %s after a button-triggered lookup', async event => {
  const fetchPrice = vi.fn(() => Response.json(priceResult))
  network(fetchPrice)
  const { client } = renderWithQueries(<PriceLookup parts={['SS34']} />)
  expect(fetchPrice).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await screen.findByText('시험 재고')
  expect(fetchPrice).toHaveBeenCalledTimes(1)
  await act(async () => {
    if (event === 'focus') { focusManager.setFocused(false); focusManager.setFocused(true) }
    else if (event === 'reconnect') { onlineManager.setOnline(false); onlineManager.setOnline(true) }
    else await client.invalidateQueries({ queryKey: ['prices'] })
    await new Promise(resolve => setTimeout(resolve, 0))
  })
  expect(fetchPrice).toHaveBeenCalledTimes(1)
  expect(screen.getByText('시험 재고')).toBeInTheDocument()
})

it('queries again only when the user reopens the lookup', async () => {
  const fetchPrice = vi.fn(() => Response.json(priceResult))
  network(fetchPrice)
  renderWithQueries(<PriceLookup parts={['SS34']} />)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await screen.findByText('시험 재고')
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 닫기' }))
  expect(screen.queryByText('시험 재고')).toBeNull()
  expect(fetchPrice).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  await waitFor(() => expect(fetchPrice).toHaveBeenCalledTimes(2))
  expect(await screen.findByText('시험 재고')).toBeInTheDocument()
})

it('keeps a failure until the user clicks retry, without focus or reconnect retries', async () => {
  const fetchPrice = vi.fn(() => failure('UPSTREAM_ERROR', '판매처 응답 실패', 502))
  network(fetchPrice)
  renderWithQueries(<PriceLookup parts={['SS34']} />)
  fireEvent.click(screen.getByRole('button', { name: '가격·재고 조회' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('판매처 응답 실패')
  await act(async () => {
    focusManager.setFocused(false); focusManager.setFocused(true)
    onlineManager.setOnline(false); onlineManager.setOnline(true)
    await new Promise(resolve => setTimeout(resolve, 0))
  })
  expect(fetchPrice).toHaveBeenCalledTimes(1)
  fetchPrice.mockImplementation(() => Response.json(priceResult))
  fireEvent.click(screen.getByRole('button', { name: '다시 조회' }))
  await screen.findByText('시험 재고')
  expect(fetchPrice).toHaveBeenCalledTimes(2)
  expect(screen.queryByRole('alert')).toBeNull()
})
