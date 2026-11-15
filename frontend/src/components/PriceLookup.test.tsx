import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import { focusManager, onlineManager } from '@tanstack/react-query'
import { afterEach, expect, it, vi } from 'vitest'
import PriceLookup from './PriceLookup'
import { failure, network, priceResult } from '../test/network'
import { renderWithQueries } from '../test/projects'

afterEach(() => { vi.unstubAllGlobals(); focusManager.setFocused(undefined); onlineManager.setOnline(true) })

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
