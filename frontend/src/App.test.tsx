import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('SojaFit 화면 셸', () => {
  it.each([
    ['/', '로그인'],
    ['/login', '로그인'],
    ['/app', '회로 작업대'],
    ['/admin/users', '사용자 관리'],
  ])('%s 경로를 직접 열면 해당 화면을 표시한다', (path, title) => {
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: title })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '주요 화면' })).toBeInTheDocument()
  })

  it('화면 탐색으로 작업대를 연다', () => {
    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)
    fireEvent.click(screen.getByRole('link', { name: '작업대' }))
    expect(screen.getByRole('heading', { name: '회로 작업대' })).toBeInTheDocument()
  })
})
