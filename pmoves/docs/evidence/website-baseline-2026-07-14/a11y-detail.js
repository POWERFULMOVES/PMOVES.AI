// Detailed a11y report — captures which exact components fail
const { chromium } = require('playwright');

const URL = 'http://127.0.0.1:8765/pmoves/contracts/a2ui-v0.1-conformance.test.html';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (err) => errors.push(`[pageerror] ${err.message}`));
  page.on('console', (msg) => { if (msg.type() === 'error') errors.push(`[console.error] ${msg.text()}`); });

  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const result = await page.evaluate(async () => {
    const r = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] } });
    return r.violations.map((v) => ({
      id: v.id, impact: v.impact, help: v.help,
      nodes: v.nodes.map((n) => ({ target: n.target, html: n.html.substring(0, 200), summary: n.failureSummary }))
    }));
  });

  console.log(JSON.stringify(result, null, 2));
  if (errors.length) console.log('\n=== ERRORS ===\n' + errors.join('\n'));
  await browser.close();
})();
