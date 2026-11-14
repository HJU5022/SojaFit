import { useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ArrowUp, FileText, Paperclip, X } from 'lucide-react'
import { errorMessage, requestIdProps } from '../api/client'
import { useNetlistFiles } from '../hooks/useNetlistFiles'
import ChatPane from './ChatPane'

export default function NetlistIntake({ question, setQuestion, hasCircuit, onAsk, onAttach, children }: {
  question: string; setQuestion: (text: string) => void; hasCircuit: boolean; onAsk: (text: string) => void;
  onAttach: (file: File, question: string, signal: AbortSignal) => Promise<void>; children: ReactNode
}) {
  const input = useRef<HTMLTextAreaElement>(null)
  const picker = useRef<HTMLInputElement>(null)
  const [files, setFiles] = useState<File[]>([])
  const attachments = useNetlistFiles(files, setFiles, input, false, 'intake', question, onAttach)
  function send() {
    if (attachments.busy) return
    if (files.length) void attachments.send()
    else if (hasCircuit) onAsk(question)
    else attachments.setError(new Error('회로 검토를 시작하려면 넷리스트를 첨부해 주세요.'))
  }
  return <section className="review netlist-intake" aria-label="프로젝트 채팅">
    {attachments.dragging && <div className="attachment-drop-guide" role="status" aria-label="파일 놓기"><Paperclip aria-hidden="true" /><p>.net·.txt 파일 하나를 놓으면 채팅에 첨부됩니다.</p></div>}
    <ChatPane context="intake" input={input} composer={<>
      {attachments.error ? <div className="notice notice-dismissible" role="alert" {...requestIdProps(attachments.error)}><p>{errorMessage(attachments.error)}</p><button type="button" className="icon-btn" aria-label="첨부 안내 닫기" onClick={() => attachments.setError(null)}><X aria-hidden="true" /></button></div> : null}
      <form className="composer" onSubmit={event => { event.preventDefault(); send() }}>
        <label className="sr-only" htmlFor="part-question">질문</label>
        <textarea id="part-question" ref={input} rows={2} readOnly={attachments.busy} value={question} onChange={event => setQuestion(event.target.value)} placeholder={hasCircuit ? '예: D1을 SS34로 바꿔도 되나요? 입력 최대 12V, 전류 최대 1A' : '넷리스트를 첨부하고 검토할 내용을 적어 주세요.'} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send() } }} />
        <input ref={picker} type="file" accept=".net,.txt" hidden onChange={event => { attachments.attach(Array.from(event.target.files ?? [])); event.target.value = '' }} />
        <button type="button" className="btn btn-icon" disabled={attachments.busy} aria-label="파일 첨부 (.net, .txt)" onClick={() => picker.current?.click()}><Paperclip aria-hidden="true" /></button>
        <button className="btn btn-icon" disabled={attachments.busy || (!files.length && !question.trim())} aria-label="질문 보내기"><ArrowUp aria-hidden="true" /></button>
      </form>
      {files.length > 0 && <ul className="chips" aria-label="첨부한 파일">{files.map((file, index) => <li key={`${file.name}-${index}`}><FileText aria-hidden="true" /><span>{file.name}</span><button type="button" className="icon-btn" disabled={attachments.busy} aria-label={`${file.name} 첨부 취소`} onClick={() => setFiles(current => current.filter((_, at) => at !== index))}><X aria-hidden="true" /></button></li>)}</ul>}
      <p className="composer-hint">{attachments.busy ? '넷리스트를 읽는 중입니다…' : '파일 하나만 보내도 됩니다. 새 회로 버전·새 대화로 이어집니다.'}</p>
    </>}>
      <div className="activity-reply"><div className="activity-body"><p>{hasCircuit ? '어느 부품을 검토할까요? 부품 번호와 사용 조건을 적거나 아래에서 골라 주세요.' : '넷리스트를 첨부해 주세요. 회로를 읽은 뒤 검토할 부품과 사용 조건을 함께 확인하겠습니다.'}</p></div></div>
      {children}
    </ChatPane>
  </section>
}
