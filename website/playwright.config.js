const {defineConfig} = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:3000/gramflux/',
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: 'npm run serve',
    url: 'http://127.0.0.1:3000/gramflux/',
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
