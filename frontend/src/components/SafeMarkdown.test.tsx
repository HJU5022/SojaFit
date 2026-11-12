import { render, screen } from '@testing-library/react'
import { expect, it } from 'vitest'
import SafeMarkdown from './SafeMarkdown'

const real = '**D1 판정: 조건부**\n\n| 조건 | 기준 | 후보 값 |\n|---|---|---|\n| VR | ≥ 40 V | 45 V |\n| IF | ≥ 1 A | **문서로 확인 안 됨** |\n\n- 첫째 항목\n- 둘째 항목\n\n> 인용 문장\n\n1. 하나\n2. 둘\n\n# 제목\n\n`code` 줄1\n줄2'

it('renders table, bold, lists, quote, heading and code as elements', () => {
  const { container } = render(<SafeMarkdown text={real} />)
  expect(container.querySelectorAll('thead th')).toHaveLength(3)
  expect(container.querySelectorAll('tbody tr')).toHaveLength(2)
  expect(screen.getByRole('columnheader', { name: '기준' })).toBeInTheDocument()
  expect(container.querySelector('tbody strong')?.textContent).toBe('문서로 확인 안 됨')
  expect(container.querySelectorAll('ul > li')).toHaveLength(2)
  expect(container.querySelectorAll('ol > li')).toHaveLength(2)
  expect(container.querySelector('blockquote')?.textContent).toBe('인용 문장')
  expect(container.querySelector('code')?.textContent).toBe('code')
  expect(container.querySelector('br')).not.toBeNull()
  expect(container.textContent).not.toContain('**')
  expect(container.textContent).not.toContain('|---')
})

it('does not create img, a, script or event handlers from hostile markdown or HTML', () => {
  const evil = '![x](http://evil.invalid/p.png) [click](javascript:alert(1)) <script>alert(1)</script> <img src=x onerror="alert(1)"> <a href="http://evil.invalid">z</a>'
  const { container } = render(<SafeMarkdown text={evil} />)
  expect(container.querySelector('img, a, script, [onerror], [href], [src]')).toBeNull()
  expect(container.textContent).toContain('<script>alert(1)</script>')
  expect(container.textContent).toContain('[click](javascript:alert(1))')
})

it('keeps a pipe table with hostile cells safe', () => {
  const { container } = render(<SafeMarkdown text={'| a | b |\n|---|---|\n| ![i](http://evil.invalid/x) | <img src=x onerror=alert(1)> |'} />)
  expect(container.querySelectorAll('td')).toHaveLength(2)
  expect(container.querySelector('img, a, [onerror]')).toBeNull()
})

it('preserves safe formatting when a caller renders citation text', () => {
  const { container } = render(<SafeMarkdown text={'**근거** [1]\n\n| 값 | 문서 |\n|---|---|\n| 40 V | [1] |\n\n[외부](https://evil.invalid) <img src=x>'}
    renderText={text => text.split(/(\[1\])/).map((part, index) => part === '[1]' ? <button key={index}>문서 근거 [1] 보기</button> : part)} />)
  expect(screen.getAllByRole('button', { name: '문서 근거 [1] 보기' })).toHaveLength(2)
  expect(container.querySelector('strong')).toHaveTextContent('근거')
  expect(screen.getByRole('table')).toBeInTheDocument()
  expect(container.querySelector('a, img, script')).toBeNull()
})
