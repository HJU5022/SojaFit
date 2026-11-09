import { Navigate, NavLink, Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/app">
          <svg aria-hidden="true" viewBox="0 0 48 20"><path d="M5 10h15l8-6v12l-8-6h23" /><circle cx="5" cy="10" r="3" /><circle cx="43" cy="10" r="3" /></svg>
          SojaFit
        </a>
        <nav aria-label="주요 화면">
          <NavLink to="/app">작업대</NavLink>
          <NavLink to="/login">로그인</NavLink>
          <NavLink to="/admin/users">사용자 관리</NavLink>
        </nav>
      </header>
      <main id="main">
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/login" element={<><h1>로그인</h1><p>회로 검토를 시작하는 곳입니다.</p></>} />
          <Route path="/app" element={<><h1>회로 작업대</h1><p>회로의 역할과 부품 대체 근거를 함께 검토합니다.</p></>} />
          <Route path="/admin/users" element={<><h1>사용자 관리</h1><p>계정 접근 권한을 관리하는 공간입니다.</p></>} />
        </Routes>
      </main>
    </div>
  )
}
