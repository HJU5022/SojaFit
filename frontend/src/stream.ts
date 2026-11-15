/** SSE 프레임을 복원한다. 재전송·판정은 하지 않는다. 출처: SPEC 4절 이벤트 순서. */
export async function consumeSSE(stream: ReadableStream<Uint8Array>, onFrame: (event: string, data: any) => void) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = '', terminal = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      // [왜] 네트워크 청크는 한국어 한 글자나 CRLF 중간에서도 나뉜다.
      let boundary: RegExpExecArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
        const frame = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const lines = frame.split(/\r?\n/);
        const event = lines.find(l => l.startsWith('event:'))?.slice(6).trim() ?? 'message';
        const data = lines.filter(l => l.startsWith('data:')).map(l => l.slice(5).trimStart()).join('\n');
        if (!data) continue;
        onFrame(event, JSON.parse(data));
        if (['completed', 'requires_input', 'refused', 'failed'].includes(event)) terminal = true;
      }
      if (done) break;
    }
    if (!terminal) throw new Error('실시간 연결이 끊겼습니다. 저장된 상태를 확인해 주세요.');
  } finally { reader.releaseLock(); }
}
