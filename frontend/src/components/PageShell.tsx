import type { ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

// 작업대 밖의 로그인 후 화면(설정 · 관리)이 같은 머리와 폭을 쓴다.
export default function PageShell({ title, lead, wide, children }: { title: string; lead?: string; wide?: boolean; children: ReactNode }) {
  return <div className="page">
    <header className="land-nav"><Link className="brand" to="/app"><img src="/assets/sojafit-icon.svg" alt="" width="24" height="24" />SojaFit</Link>
      <Link className="btn" to="/app"><ArrowLeft aria-hidden="true" />작업대로</Link></header>
    <main className={`page-main${wide ? ' page-wide' : ''}`}><header className="page-head"><h1>{title}</h1>{lead && <p>{lead}</p>}</header>{children}</main>
  </div>
}
