import { expect, test } from 'vitest'
import type { Project } from '../api/projects'
import type { ResultDto } from '../api/conversations'
import { contextOf, isDiode } from './circuit'
import { candidatesOf, citationHref, formatValue } from './judgement'

const project = { id: 1, name: 'p', source_kind: 'upload', demo_id: null, created_at: '', updated_at: '', connections: {
  parts: [{ ref: 'D1', value: '1N4001', footprint: '' }, { ref: 'D2', value: 'LED', footprint: '' }, { ref: 'C1', value: '100uF', footprint: '' }],
  nets: [{ name: 'VIN', nodes: [{ ref: 'D1', pin: '1', pinfunction: 'A' }, { ref: 'C1', pin: '1' }, { ref: 'C1', pin: '3' }] }, { name: 'GND', nodes: [{ ref: 'C1', pin: '2' }] }],
} } as Project

test('대상 부품이 닿는 넷과 이웃만 뽑고 같은 이웃은 한 번만 센다', () => {
  expect(contextOf(project, 'D1')).toEqual([{ name: 'VIN', pin: 'A', neighbors: [{ ref: 'C1', value: '100uF' }], more: 0 }])
  expect(contextOf(project, 'X9')).toEqual([])
})
test('LED는 다이오드 목록에 넣지 않는다', () => {
  expect(project.connections.parts!.filter(isDiode).map(part => part.ref)).toEqual(['D1'])
})
test('판정이 없는 결과와 위험한 출처 주소를 걸러 낸다', () => {
  expect(candidatesOf({ judgement: {} } as ResultDto)).toEqual([])
  expect(citationHref({ source_url: 'javascript:alert(1)' })).toBe('')
  expect(citationHref({ source_url: 'https://a.test/d.pdf', page: 1, outline_page: 4 })).toBe('https://a.test/d.pdf#page=4')
  expect(formatValue(40, 'V')).toBe('40 V')
})
