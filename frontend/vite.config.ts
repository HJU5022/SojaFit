/** 개발·미리보기 프록시. 판정·인증은 백엔드 소유. 출처: SPEC 4절. */
import { defineConfig, type ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';

const target = process.env.SOJAFIT_API_TARGET || 'http://localhost:8000';
// [왜] 백엔드는 상태를 바꾸는 요청의 Origin이 AUTH_ORIGIN(기본 http://localhost:8000)과 같아야 한다(ORIGIN_MISMATCH).
// 브라우저는 개발 서버 주소를 Origin으로 보내므로, 프록시가 백엔드가 기대하는 값으로 바꿔 보낸다.
const origin = process.env.SOJAFIT_AUTH_ORIGIN || target;
const api: ProxyOptions = {
  target,
  changeOrigin: false,
  configure: (p) => p.on('proxyReq', (req) => req.setHeader('origin', origin)),
};
const proxy = { '/api': api, '/health': target };

export default defineConfig({ plugins: [react()], server: { proxy }, preview: { proxy } });
