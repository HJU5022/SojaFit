/**
 * 로컬 Chrome으로 실제 데모 API를 검증한다. 서버를 자동 시작하거나 실제 모드(DEMO_MODE=0)를 사용하지 않는다.
 * 사전 조건: 백엔드를 키 없는 데모(DEMO_MODE=1 DEMO_REPLAY=1)로 띄운다. 기본 주소는 백엔드가 화면까지 주는 http://localhost:8000이고,
 * 개발 서버(npm run dev)를 쓰려면 SOJAFIT_BASE_URL=http://localhost:5173. 데모 사용자 A·B의 프로젝트·승인·견적·설정을 만들고 지우므로 운영에는 쓰지 않는다.
 */
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: 'tests',
  testMatch: '*.spec.ts',
  timeout: 150000,
  workers: 1,
  outputDir: 'test-results',
  use: {
    actionTimeout: 10000,
    baseURL: process.env.SOJAFIT_BASE_URL || 'http://localhost:8000',
    channel: 'chrome',
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
  },
  reporter: 'list',
});
