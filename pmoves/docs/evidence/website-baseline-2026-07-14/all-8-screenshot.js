// Capture screenshots of:
// 1. The conformance test page (all 7 components)
// 2. Each of the 4 new component demos
// 3. The Fordham Hill tenant page (live render)
// Outputs go to pmoves/docs/evidence/website-baseline-2026-07-14/

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ART = 'pmoves/docs/evidence/website-baseline-2026-07-14';

const TARGETS = [
  { name: 'conformance-8-components', url: 'http://127.0.0.1:8765/pmoves/contracts/a2ui-v0.1-conformance.test.html' },
  { name: 'tenant-fordham-hill', url: 'http://127.0.0.1:8765/website/tenant-template/index.html?tenant=fordham-hill' },
  { name: 'demo-pm-timeline', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-timeline/demo.html' },
  { name: 'demo-pm-voice-clip', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-voice-clip/demo.html' },
  { name: 'demo-pm-image', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-image/demo.html' },
  { name: 'demo-pm-quote-block', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-quote-block/demo.html' },
  { name: 'demo-pm-haptic', url: 'http://127.0.0.1:8765/pmoves/web-components/pm-haptic/demo.html' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const results = [];

  for (const t of TARGETS) {
    try {
      const resp = await page.goto(t.url, { waitUntil: 'networkidle', timeout: 20000 });
      // Give components + A2UI a moment to render
      await page.waitForTimeout(1500);
      const status = resp ? resp.status() : 'no-response';
      const title = await page.title();
      const file = path.join(ART, `${t.name}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log(`✓ ${t.name} (${status}) — ${title} → ${file}`);
      results.push({ name: t.name, status, title, file });
    } catch (e) {
      console.log(`✗ ${t.name}: ${e.message}`);
      results.push({ name: t.name, error: e.message });
    }
  }

  fs.writeFileSync(path.join(ART, 'all-7-screenshots.json'), JSON.stringify(results, null, 2));
  await browser.close();
})();
