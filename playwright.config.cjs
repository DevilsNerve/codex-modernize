const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: 'viewer.spec.cjs',
  workers: 1,
  use: { browserName: 'chromium', headless: true, viewport: { width: 1440, height: 1000 } },
  reporter: 'list',
});
