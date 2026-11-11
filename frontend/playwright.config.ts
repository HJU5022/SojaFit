import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // Windows에서 병렬 worker의 trace 임시 파일이 먼저 정리되어 ENOENT가 나는 환경 오류를 피한다.
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'off' },
  webServer: { command: 'npm run dev:dummy -- --host 127.0.0.1 --port 4173', url: 'http://127.0.0.1:4173', reuseExistingServer: true },
})
