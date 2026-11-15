import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { errorMessage, requestIdProps } from '../api/client'
import { useAuth } from './AuthProvider'

export default function RequireAuth({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { user, loading, error, resumeAfterLogin } = useAuth()
  const location = useLocation()
  if (loading) return <p role="status">로그인 상태 확인 중입니다.</p>
  if (error) return <p role="alert" {...requestIdProps(error)}>{errorMessage(error)}</p>
  if (!user) return <Navigate to="/login" replace state={resumeAfterLogin ? { returnTo: location.pathname + location.search + location.hash } : null} />
  if (admin && user.role !== 'admin') return <p role="alert">관리자 권한이 필요합니다.</p>
  return children
}
