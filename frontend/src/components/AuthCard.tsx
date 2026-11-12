import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

// 로그인 · 가입 · 메일 링크 화면이 같은 틀을 쓴다.
export default function AuthCard({ title, lead, children, links }: { title: string; lead?: string; children: ReactNode; links?: ReactNode }) {
  return <main className="login"><div className="login-card">
    <Link className="brand" to="/"><img src="/assets/sojafit-icon.svg" alt="" width="24" height="24" />SojaFit</Link>
    <h1>{title}</h1>
    {lead && <p className="login-lead">{lead}</p>}
    {children}
    {links && <nav className="login-links" aria-label="다른 화면">{links}</nav>}
  </div></main>
}
