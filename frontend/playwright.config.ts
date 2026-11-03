import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel: process.platform === 'win32' ? 'chrome' : undefined,
    viewport: { width: 1440, height: 960 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: [
    {
      command: `${process.platform === 'win32' ? '.venv\\Scripts\\python.exe' : './.venv/bin/python'} -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001`,
      cwd: '..',
      url: 'http://127.0.0.1:8001/api/health',
      reuseExistingServer: !process.env.CI,
      env: { AI_MODE: 'mock', DATABASE_PATH: '.local/e2e.db', PYTHONIOENCODING: 'utf-8' },
    },
    {
      command: 'npm run preview -- --port 5174 --strictPort',
      url: 'http://127.0.0.1:5174',
      reuseExistingServer: !process.env.CI,
      env: { VITE_API_PROXY_TARGET: 'http://127.0.0.1:8001' },
    },
  ],
})
