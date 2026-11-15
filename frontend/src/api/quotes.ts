import { apiFetch } from './client'

export type ApprovalDto = { id: number; message_id: number; candidate_part: string; verdict: string; case_id: number | null; created_at?: string }
export type QuoteDto = { id: number; approval_id: number; part_number: string; quantity: number; created_at?: string }
export type ApprovedCaseDto = { id: number; approval_id: number; candidate_part: string; verdict: string; created_at?: string }

export const approveMessage = (messageId: number, candidatePart: string, verdict: string, signal?: AbortSignal) => apiFetch<ApprovalDto>(`/api/messages/${messageId}/approvals`, {
  method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ candidate_part: candidatePart, verdict }),
})
export const listMessageApprovals = (messageId: number, signal?: AbortSignal) => apiFetch<ApprovalDto[]>(`/api/messages/${messageId}/approvals`, { signal, cache: 'no-store' })
export const listProjectQuotes = (projectId: number, signal?: AbortSignal) => apiFetch<QuoteDto[]>(`/api/projects/${projectId}/quotes`, { signal, cache: 'no-store' })
export const createQuote = (approvalId: number, quantity: number, signal?: AbortSignal) => apiFetch<QuoteDto>(`/api/approvals/${approvalId}/quotes`, {
  method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ quantity }),
})
export const listApprovedCases = (signal?: AbortSignal) => apiFetch<ApprovedCaseDto[]>('/api/approved-cases', { signal })
export const deleteApprovedCase = (caseId: number, signal?: AbortSignal) => apiFetch<void>(`/api/approved-cases/${caseId}`, { method: 'DELETE', signal })
