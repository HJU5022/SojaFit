import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // Windows에서 병렬 worker의 trace 임시 파일이 먼저 정리되어 ENOENT가 나는 환경 오류를 피한다.
  workers: 1,
  use: { trace: 'off' },
  projects: [
    { name: 'http-mocks', testMatch: ['**/workbench.spec.ts', '**/full-flow.spec.ts'], use: { baseURL: 'http://127.0.0.1:4190' } },
    { name: 'dummy', testMatch: ['**/dummy-mode.spec.ts', '**/circuit-layout.spec.ts'], use: { baseURL: 'http://127.0.0.1:4191' } },
  ],
  webServer: [
    { command: 'npm run build && npx --no-install vite preview --host 127.0.0.1 --port 4190 --strictPort', url: 'http://127.0.0.1:4190', reuseExistingServer: false },
    { command: 'npm run dev:dummy -- --host 127.0.0.1 --port 4191 --strictPort', url: 'http://127.0.0.1:4191', reuseExistingServer: false },
  ],
})
