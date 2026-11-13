import { useCallback, useEffect, useRef, useState } from 'react'
import type { Dispatch, RefObject, SetStateAction } from 'react'

// 드롭과 파일 선택은 같은 검사와 초안 목록을 쓴다. 서버가 KiCad 내용을 다시 검증한다.
export function useNetlistFiles(files: File[], setFiles: Dispatch<SetStateAction<File[]>>, input: RefObject<HTMLTextAreaElement | null>, disabled: boolean, context: string, question: string, onAttach: (file: File, question: string, signal: AbortSignal) => Promise<void>) {
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const upload = useNetlistImport(files, question, onAttach, setError, context)
  const blocked = disabled || upload.busy
  const attach = useCallback((incoming: File[]) => {
    const valid = incoming.filter(file => /\.(net|txt)$/i.test(file.name) && file.size > 0 && file.size <= 5 * 1024 * 1024)
    setError(valid.length !== incoming.length || !incoming.length ? new Error('.net·.txt 형식의 비어 있지 않은 5 MiB 이하 파일만 첨부할 수 있습니다.') : null)
    setFiles(current => {
      const next = [...current]
      for (const file of valid) if (!next.some(item => item.name === file.name && item.size === file.size && item.lastModified === file.lastModified)) next.push(file)
      return next
    })
    if (valid.length) input.current?.focus({ preventScroll: true })
  }, [setFiles, input])
  useEffect(() => { setError(null) }, [context])
  useEffect(() => {
    let depth = 0
    const reset = () => { depth = 0; setDragging(false) }
    const fileDrag = (event: DragEvent) => Array.from(event.dataTransfer?.types ?? []).includes('Files')
    const dialogOpen = () => Boolean(document.querySelector('dialog[open]'))
    const nativePicker = (event: DragEvent) => event.target instanceof HTMLInputElement && event.target.type === 'file' && !event.target.disabled
    function enter(event: DragEvent) {
      if (!fileDrag(event)) return
      if (nativePicker(event)) { reset(); return }
      event.preventDefault()
      if (dialogOpen()) { reset(); return }
      if (!blocked) { depth++; setDragging(true) }
    }
    function over(event: DragEvent) {
      if (!fileDrag(event) || nativePicker(event)) return
      event.preventDefault()
      if (event.dataTransfer) event.dataTransfer.dropEffect = blocked || dialogOpen() ? 'none' : 'copy'
    }
    function leave() { if (depth > 0 && --depth === 0) setDragging(false) }
    function drop(event: DragEvent) {
      if (!fileDrag(event)) return
      reset()
      if (nativePicker(event)) return
      event.preventDefault()
      if (dialogOpen()) return
      if (blocked) { setError(new Error('검토 기록 복원이나 진행 중인 응답이 끝난 뒤 파일을 첨부해 주세요.')); return }
      attach(Array.from(event.dataTransfer?.files ?? []))
    }
    reset()
    window.addEventListener('dragenter', enter)
    window.addEventListener('dragover', over)
    window.addEventListener('dragleave', leave)
    window.addEventListener('drop', drop)
    window.addEventListener('dragend', reset)
    window.addEventListener('blur', reset)
    return () => {
      window.removeEventListener('dragenter', enter); window.removeEventListener('dragover', over)
      window.removeEventListener('dragleave', leave); window.removeEventListener('drop', drop)
      window.removeEventListener('dragend', reset); window.removeEventListener('blur', reset)
    }
  }, [attach, blocked, context])
  return { files, dragging, error, setError, attach, ...upload }
}

function useNetlistImport(files: File[], question: string, onAttach: (file: File, question: string, signal: AbortSignal) => Promise<void>, setError: (error: unknown) => void, context: string) {
  const [busy, setBusy] = useState(false)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => {
    setBusy(false)
    return () => { controller.current?.abort(); controller.current = null }
  }, [context])
  async function send() {
    if (controller.current) return
    if (files.length !== 1) { setError(new Error('넷리스트는 한 번에 하나만 전송해 주세요.')); return }
    const active = new AbortController()
    controller.current = active; setBusy(true); setError(null)
    try { await onAttach(files[0], question.trim(), active.signal) }
    catch (reason) { if (!active.signal.aborted) setError(reason) }
    finally { if (!active.signal.aborted) setBusy(false); if (controller.current === active) controller.current = null }
  }
  return { busy, send }
}
