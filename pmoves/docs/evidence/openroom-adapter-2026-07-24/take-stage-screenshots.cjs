// /stage/ page screenshots — the new Enter button is the visual proof
// of slice 1. Captures the full rooms-on-a-stage surface at 1440x900.

const path = require('path');
const fs = require('fs');
const playwrightPath = path.join(
  __dirname, '..', '..', '..', '..',
  'PMOVES-OpenRoom', 'node_modules', 'playwright',
);
const { chromium } = require(playwrightPath);

const EVIDENCE_DIR = path.join(__dirname, 'screenshots');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  const consoleLog = [];
  page.on('console', (msg) => consoleLog.push(`[${msg.type()}] ${msg.text()}`));
  page.on('pageerror', (err) => consoleLog.push(`[pageerror] ${err.message}`));

  // Screenshot the /stage/ page with the new Enter buttons.
  // Use domcontentloaded; the /stage/ page itself doesn't have
  // persistent background fetches but networkidle still waits for
  // font loading + analytics pings that don't matter for the visual
  // capture. Wait for at least one Enter button to render so we
  // don't screenshot the page mid-mount.
  console.log('Loading /stage/ ...');
  await page.goto('http://localhost:8080/stage/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  // Deterministic readiness: wait for at least one Enter button to
  // appear. If none renders within 10s, the stage data didn't bake
  // any rooms and the test fails loudly.
  await page
    .waitForFunction(
      () => document.querySelectorAll('a2ui-button').length > 0,
      null,
      { timeout: 10000 },
    )
    .catch(() => {
      throw new Error(
        '/stage/: no <a2ui-button> elements appeared within 10s — stage_data.py may not have baked any rooms',
      );
    });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '03-stage-with-enter-buttons.png'),
    fullPage: false,
  });
  console.log('  -> 03-stage-with-enter-buttons.png');

  // Also screenshot a single public room card with the Enter button
  // hovered (visual proof the button is interactive). Use a2ui-button
  // with an "Enter \u2192" text child to make sure we're hovering the
  // right control rather than some other button on the page.
  const enterButtons = await page.locator('a2ui-button').all();
  if (enterButtons.length === 0) {
    throw new Error('/stage/: expected at least one <a2ui-button> for hover capture');
  }
  let hoveredOne = false;
  for (const btn of enterButtons) {
    const txt = (await btn.innerText().catch(() => '')) || '';
    if (txt.includes('Enter')) {
      await btn.hover();
      hoveredOne = true;
      break;
    }
  }
  if (!hoveredOne) {
    throw new Error('/stage/: no <a2ui-button> with "Enter" text found for hover capture');
  }
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '04-stage-enter-hover.png'),
    fullPage: false,
  });
  console.log('  -> 04-stage-enter-hover.png');

  // Full-page screenshot of the entire /stage/ surface.
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '05-stage-full.png'),
    fullPage: true,
  });
  console.log('  -> 05-stage-full.png');

  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'stage-console.log'),
    consoleLog.join('\n'),
  );

  await browser.close();
  console.log(`Done. ${consoleLog.length} console messages captured.`);
})();
