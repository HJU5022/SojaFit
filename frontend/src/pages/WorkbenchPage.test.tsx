import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import WorkbenchPage from './WorkbenchPage'

it('shows workbench without fabricated price candidates', () => {
  render(<WorkbenchPage />)
  expect(screen.getByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '가격·재고 조회' })).toBeDisabled()
})
