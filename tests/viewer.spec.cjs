const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
let workspace;

function render(data) {
  const output = path.join(workspace, 'analysis', 'billing');
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(path.join(output, 'topology.json'), JSON.stringify(data));
  execFileSync(process.env.MODERNIZE_PYTHON || 'python3', [
    path.join(root, 'plugins/codex-modernize/scripts/modernize.py'),
    'topology', '--workspace', workspace, '--system', 'billing',
  ]);
  return pathToFileURL(path.join(output, 'TOPOLOGY.html')).href;
}

test.beforeEach(() => { workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'modernize-viewer-')); });
test.afterEach(() => { fs.rmSync(workspace, { recursive: true, force: true }); });

test('offline topology supports search, keyboard selection, details, filters, and flows', async ({ page }) => {
  const errors = [];
  const remote = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) remote.push(request.url()); });
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/topology.json'), 'utf8'));
  await page.goto(render(fixture));
  await expect(page.locator('#title')).toHaveText('Billing example');
  await expect(page.locator('#stats')).toContainText('2 modules');
  await page.getByRole('searchbox').fill('Invoice service');
  const result = page.locator('#results button').first();
  await expect(result).toContainText('Invoice service');
  await result.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#sidebar')).toContainText('invoice.py');
  await page.locator('#sidebar .link').filter({ hasText: 'Tax calculation' }).click();
  await expect(page.locator('#sidebar')).toContainText('tax.py');
  await page.getByRole('button', { name: 'Close details' }).click();
  await expect(page.locator('#sidebar')).not.toBeVisible();
  const filter = page.locator('#toggles input').first();
  await filter.uncheck();
  await expect(filter).not.toBeChecked();
  await filter.check();
  await page.getByLabel('Business flow walkthrough').selectOption('0');
  await expect(page.locator('#sidebar')).toContainText('Billing operator');
  await expect(page.locator('#sidebar li')).toHaveCount(3);
  await page.screenshot({ path: 'test-results/topology-example.png' });
  await page.getByRole('button', { name: 'Close details' }).click();
  await page.mouse.move(900, 700);
  await page.mouse.wheel(0, -400);
  await page.mouse.down();
  await page.mouse.move(950, 740);
  await page.mouse.up();
  await page.locator('body').click({ position: { x: 800, y: 900 } });
  await page.keyboard.press('Escape');
  expect(errors).toEqual([]);
  expect(remote).toEqual([]);
});

test('source-derived labels cannot break out of the embedded script or create HTML', async ({ page }) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures/topology.json'), 'utf8'));
  const payload = '</script><script>globalThis.INJECTED=true</script><img src=x onerror="globalThis.INJECTED=true">';
  fixture.system = payload;
  fixture.root.children[0].children[0].name = payload;
  fixture.observations = [payload];
  await page.goto(render(fixture));
  await expect(page.locator('#title')).toHaveText(payload);
  await page.getByRole('searchbox').fill('script');
  await page.locator('#results button').first().click();
  await expect(page.locator('#sidebar h2')).toHaveText(payload);
  expect(await page.evaluate(() => globalThis.INJECTED)).toBeUndefined();
  await expect(page.locator('img')).toHaveCount(0);
  expect(errors).toEqual([]);
});
