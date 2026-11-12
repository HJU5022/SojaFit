import type { ReactNode } from 'react'

// 서버가 만든 답(헤더 · 표 · **굵게** · 목록 · 인용)을 읽기 좋게 보여 주는 최소 렌더러.
// [왜 직접 만들었나] 답에는 코퍼스 문서 · 사용자 입력이 섞일 수 있어(간접 프롬프트 인젝션) 안전이 우선이다.
//   React 요소만 만들고 dangerouslySetInnerHTML을 쓰지 않으므로 원시 HTML은 글자로만 나온다.
//   이미지 · 링크 문법은 해석하지 않고 글자 그대로 둔다: 화면이 외부 주소를 자동으로 불러 데이터가 새는 길과 피싱 링크를 둘 다 막는다.
//   (라이브러리를 쓰면 설정 실수 한 번이 곧 구멍이라 의존성 없이 필요한 문법만 지원한다.)
// shortcut: 중첩 목록 · 기울임 · 표 칸 안 `|` 이스케이프는 지원하지 않는다. 필요해지면 그때 늘린다.

const inline = (text: string, renderText?: (text: string) => ReactNode): ReactNode[] =>
  text.split(/(\*\*[^*\n]+\*\*|`[^`\n]+`)/).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part.startsWith('`') && part.endsWith('`') && part.length > 2 ? <code key={i}>{part.slice(1, -1)}</code>
        : renderText ? renderText(part) : part)

const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim())
const isRule = (line: string) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(line) && line.includes('-')
const isRow = (line: string) => line.trim().startsWith('|')
const bullet = /^\s*[-*]\s+/
const ordered = /^\s*\d+[.)]\s+/
const special = (line: string, next?: string) => /^#{1,6}\s/.test(line) || /^\s*```/.test(line) || /^\s*>/.test(line)
  || bullet.test(line) || ordered.test(line) || (isRow(line) && next !== undefined && isRule(next))

export default function SafeMarkdown({ text, renderText }: { text: string; renderText?: (text: string) => ReactNode }) {
  const format = (value: string) => inline(value, renderText)
  const lines = text.replace(/\r\n?/g, '\n').split('\n')
  const out: ReactNode[] = []
  for (let i = 0; i < lines.length;) {
    const line = lines[i], next = lines[i + 1], key = out.length
    if (!line.trim()) { i++; continue }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) { out.push(<p key={key} className="md-heading"><strong>{format(heading[2])}</strong></p>); i++; continue }
    if (/^\s*```/.test(line)) {
      const body: string[] = []
      for (i++; i < lines.length && !/^\s*```/.test(lines[i]); i++) body.push(lines[i])
      i++
      out.push(<pre key={key}><code>{body.join('\n')}</code></pre>); continue
    }
    if (isRow(line) && next !== undefined && isRule(next)) {
      const head = cells(line), rows: string[][] = []
      for (i += 2; i < lines.length && isRow(lines[i]); i++) rows.push(cells(lines[i]))
      out.push(<div key={key} className="md-table-wrap"><table><thead><tr>{head.map((c, j) => <th key={j}>{format(c)}</th>)}</tr></thead>
        <tbody>{rows.map((r, j) => <tr key={j}>{r.map((c, k) => <td key={k}>{format(c)}</td>)}</tr>)}</tbody></table></div>); continue
    }
    if (/^\s*>/.test(line)) {
      const body: string[] = []
      for (; i < lines.length && /^\s*>/.test(lines[i]); i++) body.push(lines[i].replace(/^\s*>\s?/, ''))
      out.push(<blockquote key={key}>{format(body.join(' '))}</blockquote>); continue
    }
    const kind = bullet.test(line) ? bullet : ordered.test(line) ? ordered : null
    if (kind) {
      const items: string[] = []
      for (; i < lines.length && kind.test(lines[i]); i++) items.push(lines[i].replace(kind, ''))
      const li = items.map((item, j) => <li key={j}>{format(item)}</li>)
      out.push(kind === bullet ? <ul key={key}>{li}</ul> : <ol key={key}>{li}</ol>); continue
    }
    const body: string[] = []
    for (; i < lines.length && lines[i].trim() && (body.length === 0 || !special(lines[i], lines[i + 1])); i++) body.push(lines[i])
    out.push(<p key={key}>{body.map((l, j) => <span key={j}>{j > 0 && <br />}{format(l)}</span>)}</p>)
  }
  return <div className="markdown-body">{out}</div>
}
