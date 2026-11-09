// Capture all v0.2 surfaces + tenant pages
const { chromium } = require('playwright');

const TARGETS = [
  { name: 'conformance-10-components', url: 'http://127.0.0.1:8765/pmoves/contracts/a2ui-v0.1-conformance.test.html' },
  { name: 'tenant-sint-maarten', url: 'http://127.0.0.1:8765/website/tenant-template/index.html?tenant=sint-maarten' },
  { name: 'tenant-fordham-hill', url: 'http://127.0.0.1:8765/website/tenant-template/index.html?tenant=fordham-hill' },
  { name: 'demo-pm-toast', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-toast/demo.html' },
  { name: 'demo-pm-ballot', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-ballot/demo.html' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();

  for (const t of TARGETS) {
    try {
      const resp = await page.goto(t.url, { waitUntil: 'networkidle', timeout: 20000 });
      await page.waitForTimeout(2000);
      const status = resp ? resp.status() : 'no-response';
      const title = await page.title();
      const file = `pmoves/docs/evidence/website-baseline-2026-07-14/${t.name}.png`;
      await page.screenshot({ path: file, fullPage: true });
      console.log(`✓ ${t.name} (${status}) — ${title} → ${file}`);
    } catch (e) {
      console.log(`✗ ${t.name}: ${e.message}`);
    }
  }

  await browser.close();
})();
