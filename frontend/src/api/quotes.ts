import { apiFetch } from './client'

export type ApprovalDto = { id: number; message_id: number; candidate_part: string; verdict: string; case_id: number; created_at?: string }
export type QuoteDto = { id: number; approval_id: number; part_number: string; quantity: number; created_at?: string; thread_id?: string }
export type ApprovedCaseDto = { id: number; approval_id: number; candidate_part: string; verdict: string; created_at?: string }
export type MessageApprovalDto = { approval: (Omit<ApprovalDto, 'case_id'> & { case_id: number | null }) | null; quotes: QuoteDto[] }

export const approveMessage = (messageId: number, candidatePart: string, verdict: string, signal?: AbortSignal) => apiFetch<ApprovalDto>(`/api/messages/${messageId}/approvals`, {
  method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ candidate_part: candidatePart, verdict }),
})
export const createQuote = (approvalId: number, quantity: number, signal?: AbortSignal) => apiFetch<QuoteDto>(`/api/approvals/${approvalId}/quotes`, {
  method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quantity }),
})
// 새로고침 뒤 승인·견적 상태를 서버에서 복원한다. 읽기만 하고 가격은 어디에도 없다.
export const getMessageApproval = (messageId: number, signal?: AbortSignal) => apiFetch<MessageApprovalDto>(`/api/messages/${messageId}/approval`, { signal })
export const listQuotes = (projectId: number, signal?: AbortSignal) => apiFetch<QuoteDto[]>(`/api/projects/${projectId}/quotes`, { signal })
export const listApprovedCases = (signal?: AbortSignal) => apiFetch<ApprovedCaseDto[]>('/api/approved-cases', { signal })
export const deleteApprovedCase = (caseId: number, signal?: AbortSignal) => apiFetch<void>(`/api/approved-cases/${caseId}`, { method: 'DELETE', signal })
