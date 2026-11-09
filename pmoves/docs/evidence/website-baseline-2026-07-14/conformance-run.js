// A2UI v0.1 conformance test runner (Playwright + axe-core)
// Opens pmoves/contracts/a2ui-v0.1-conformance.test.html, captures all
// section results, runs axe-core against the test surface, prints JSON.

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const URL = 'http://127.0.0.1:8765/pmoves/contracts/a2ui-v0.1-conformance.test.html';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  // Capture console output
  const consoleLines = [];
  page.on('console', (msg) => consoleLines.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => consoleLines.push(`[pageerror] ${err.message}`));

  await page.goto(URL, { waitUntil: 'networkidle', timeout: 15000 });

  // Wait for axe to finish
  await page.waitForFunction(() => {
    const el = document.getElementById('a11y-out');
    return el && (el.textContent.includes('PASS') || el.textContent.includes('FAIL') || el.textContent.includes('violations') || el.textContent.includes('error'));
  }, { timeout: 30000 }).catch(() => {});

  // Small extra wait
  await page.waitForTimeout(2000);

  const results = await page.evaluate(() => {
    const get = (id) => {
      const el = document.getElementById(id);
      return el ? { text: el.textContent, className: el.className } : null;
    };
    // Run axe-core again to capture detailed violations (with node targets)
    return (async () => {
      let a11yDetail = null;
      if (window.axe) {
        try {
          const result = await window.axe.run(document, {
            runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
          });
          a11yDetail = {
            violationCount: result.violations.length,
            passCount: result.passes.length,
            violations: result.violations.map((v) => ({
              id: v.id,
              impact: v.impact,
              help: v.help,
              nodes: v.nodes.map((n) => ({
                target: n.target,
                failureSummary: n.failureSummary,
                html: n.html,
              })),
            })),
          };
        } catch (e) {
          a11yDetail = { error: e.message };
        }
      }
      return {
        registry: get('registry-out'),
        tokens: get('tokens-out'),
        shadow: get('shadow-out'),
        a11y: get('a11y-out'),
        a11yDetail,
      };
    })();
  });

  await page.screenshot({
    path: 'pmoves/docs/evidence/website-baseline-2026-07-14/conformance-screenshot.png',
    fullPage: true,
  });

  console.log(JSON.stringify(results, null, 2));
  console.log('\n=== CONSOLE ===');
  consoleLines.forEach((l) => console.log(l));

  await browser.close();
})();
