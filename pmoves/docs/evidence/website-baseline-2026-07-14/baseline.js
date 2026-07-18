// PMOVES.AI Website/UI Baseline - DARKXSIDE 2026-07-14
// Captures: 6 screenshots (2 pages x 3 viewports), broken-link sweep, axe-core a11y pass.
// All artifacts saved under pmoves/docs/evidence/website-baseline-2026-07-14/.

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const ART_DIR = 'pmoves/docs/evidence/website-baseline-2026-07-14';
const SCREEN_DIR = path.join(ART_DIR, 'screenshots');

const PAGES = [
  { name: 'index', url: 'http://127.0.0.1:8765/' },
  { name: 'stage', url: 'http://127.0.0.1:8765/stage/' },
];

const VIEWPORTS = [
  { name: 'desktop', width: 1920, height: 1080 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 667 },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  const results = { pages: [], a11y: [], brokenLinks: [] };

  for (const target of PAGES) {
    const pageRecord = { name: target.name, url: target.url, screenshots: [] };
    console.log(`\n=== ${target.name.toUpperCase()} (${target.url}) ===`);

    // Screenshots at 3 viewports
    for (const viewport of VIEWPORTS) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      try {
        const resp = await page.goto(target.url, { waitUntil: 'networkidle', timeout: 15000 });
        const status = resp ? resp.status() : 'no-response';
        const title = await page.title();
        const file = path.join(SCREEN_DIR, `${target.name}-${viewport.name}.png`);
        await page.screenshot({ path: file, fullPage: true });
        pageRecord.screenshots.push({ viewport: viewport.name, status, title, file });
        console.log(`  ${viewport.name} (${viewport.width}x${viewport.height}): ${status} - "${title}" - ${file}`);
      } catch (e) {
        pageRecord.screenshots.push({ viewport: viewport.name, error: e.message });
        console.log(`  ${viewport.name}: ERROR ${e.message}`);
      }
    }

    // Broken-link sweep (internal links only)
    await page.setViewportSize({ width: 1920, height: 1080 });
    try {
      await page.goto(target.url, { waitUntil: 'networkidle', timeout: 15000 });
      const internalLinks = await page.$$eval('a[href]', (anchors) =>
        anchors
          .map((a) => a.getAttribute('href'))
          .filter((h) => h && !h.startsWith('http') && !h.startsWith('mailto:') && !h.startsWith('tel:'))
      );
      const seen = new Set();
      const unique = internalLinks.filter((h) => {
        if (seen.has(h)) return false;
        seen.add(h);
        return true;
      });
      console.log(`  internal links discovered: ${unique.length}`);
      for (const link of unique) {
        const absolute = new URL(link, target.url).toString();
        try {
          const r = await page.request.get(absolute, { timeout: 5000 });
          if (!r.ok() && r.status() !== 405) {
            results.brokenLinks.push({ page: target.name, link, absolute, status: r.status() });
            console.log(`    BROKEN: ${link} -> ${r.status()}`);
          }
        } catch (e) {
          results.brokenLinks.push({ page: target.name, link, absolute, error: e.message });
          console.log(`    BROKEN: ${link} -> ${e.message}`);
        }
      }
    } catch (e) {
      console.log(`  link sweep error: ${e.message}`);
    }

    // axe-core a11y audit (CDN injection)
    try {
      await page.goto(target.url, { waitUntil: 'networkidle', timeout: 15000 });
      await page.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/axe-core@4.10.2/axe.min.js' });
      const a11yResult = await page.evaluate(async () => {
        return await window.axe.run(document, {
          resultTypes: ['violations', 'incomplete'],
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa'] },
        });
      });
      const summary = {
        page: target.name,
        violations: a11yResult.violations.length,
        incomplete: a11yResult.incomplete.length,
        details: a11yResult.violations.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          helpUrl: v.helpUrl,
          nodes: v.nodes.length,
          targets: v.nodes.slice(0, 3).map((n) => n.target),
        })),
      };
      results.a11y.push(summary);
      console.log(`  a11y: ${summary.violations} violations, ${summary.incomplete} incomplete`);
      for (const v of a11yResult.violations) {
        console.log(`    [${v.impact}] ${v.id} - ${v.help} (${v.nodes.length} nodes)`);
      }
    } catch (e) {
      console.log(`  a11y error: ${e.message}`);
    }

    results.pages.push(pageRecord);
  }

  fs.writeFileSync(path.join(ART_DIR, 'baseline-results.json'), JSON.stringify(results, null, 2));
  console.log(`\n=== DONE. Results saved to ${ART_DIR}/baseline-results.json ===`);
  await browser.close();
})();
