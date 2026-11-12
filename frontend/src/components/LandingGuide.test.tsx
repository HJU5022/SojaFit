import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it } from 'vitest'
import LandingGuide from './LandingGuide'

it('opens one guide, changes its scene and closes without starting a service action', () => {
  render(<LandingGuide />)
  const flow = screen.getByRole('group', { name: '회로 검토 사용 흐름' })
  expect(within(flow).getAllByRole('button')).toHaveLength(9)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  const upload = screen.getByRole('button', { name: '넷리스트 첨부' })
  upload.focus(); fireEvent.click(upload)
  const guide = screen.getByRole('dialog', { name: '넷리스트 첨부' })
  expect(upload).toHaveAttribute('aria-expanded', 'true')
  fireEvent.click(within(guide).getByRole('button', { name: '2 프로젝트 생성' }))
  expect(guide).toHaveTextContent('파일로 만들기를 누르세요.')
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(upload).toHaveFocus()
  fireEvent.click(upload)
  fireEvent.pointerDown(document.body)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('changes guides and keeps Escape in the explicit image dialog before closing the guide', () => {
  render(<LandingGuide />)
  fireEvent.click(screen.getByRole('button', { name: '넷리스트 첨부' }))
  fireEvent.click(screen.getByRole('button', { name: '문서 근거' }))
  const guide = screen.getByRole('dialog', { name: '문서 근거' })
  const enlarge = within(guide).getByRole('button', { name: '예시 화면 크게 보기' })
  enlarge.focus(); fireEvent.click(enlarge)
  expect(screen.getByRole('dialog', { name: '문서 근거 예시 화면' })).toBeInTheDocument()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog', { name: '문서 근거 예시 화면' })).not.toBeInTheDocument()
  expect(guide).toBeInTheDocument(); expect(enlarge).toHaveFocus()
  fireEvent.click(within(guide).getByRole('button', { name: '과정 설명 닫기' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: '문서 근거' })).toHaveFocus()
})
