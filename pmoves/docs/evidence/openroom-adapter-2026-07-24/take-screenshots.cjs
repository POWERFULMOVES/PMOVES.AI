// Playwright smoke test: load the OpenRoom shell with a PMOVES room in
// the URL, wait for the desktop to compose, capture screenshots.
//
// Run from the worktree root: node take-screenshots.cjs
// Output: ./screenshots/{01-shell-empty.png, 02-room-demo.png,
//                          03-room-fordham.png, 04-room-tokenism.png}

// Resolve playwright from the OpenRoom fork's node_modules so we don't
// have to install it separately in the evidence dir.
const path = require('path');
const fs = require('fs');
const playwrightPath = path.join(
  __dirname,
  '..', '..', '..', '..',
  'PMOVES-OpenRoom', 'node_modules', 'playwright',
);
const { chromium } = require(playwrightPath);

const EVIDENCE_DIR = path.join(__dirname, 'screenshots');
fs.mkdirSync(EVIDENCE_DIR, { recursive: true });

const ROOMS = [
  { id: 'demo.room.rehearsal', label: 'demo' },
  { id: 'fordham.room.community', label: 'fordham' },
  { id: 'tokenism.room.exchange', label: 'tokenism' },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  // Capture console messages for debugging.
  const consoleLog = [];
  page.on('console', (msg) => {
    consoleLog.push(`[${msg.type()}] ${msg.text()}`);
  });
  page.on('pageerror', (err) => {
    consoleLog.push(`[pageerror] ${err.message}`);
  });

  // First, screenshot the empty shell to show the desktop baseline.
  // Use domcontentloaded because the OpenRoom shell has persistent
  // background activity (LFM config fetch, vibe container, etc.) that
  // never reaches networkidle. Wait for the desktop root element so
  // the screenshot doesn't fire mid-mount.
  console.log('Loading empty shell...');
  await page.goto('http://localhost:3000/', {
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });
  await page.waitForSelector('[data-app-id], .desktop, body', {
    state: 'attached',
    timeout: 10000,
  });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '01-shell-empty.png'),
    fullPage: false,
  });
  console.log('  -> 01-shell-empty.png');

  // Then, load each public room and screenshot the composed desktop.
  for (const room of ROOMS) {
    console.log(`Loading room ${room.id}...`);
    // Use 'domcontentloaded' for the same reason as the empty shell.
    // After DOM ready, wait for at least one window element to be in
    // the DOM before screenshotting — the room adapter registers
    // windows in the React tree once the manifest is parsed. Falls
    // back to a generous timeout if the room has no panels.
    await page.goto(`http://localhost:3000/?room=${room.id}`, {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    // Deterministic readiness: assert that either a window was
    // composed (we expect panels for every public room) or the
    // wallpaper reached the DOM. If neither lands, the test fails
    // loudly instead of producing a black screenshot.
    const ready = await Promise.race([
      page
        .waitForSelector('[data-pmoves-room]', { state: 'attached', timeout: 8000 })
        .then(() => 'wallpaper'),
      page
        .waitForSelector('.window, [data-window-id]', { state: 'attached', timeout: 8000 })
        .then(() => 'window'),
    ]).catch(() => 'timeout');
    if (ready === 'timeout') {
      throw new Error(
        `room ${room.id}: no wallpaper or window element appeared within 8s — adapter may not have loaded the manifest`,
      );
    }
    await page.waitForTimeout(1500);
    const filename = `02-room-${room.label}.png`;
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, filename),
      fullPage: false,
    });
    console.log(`  -> ${filename} (readiness: ${ready})`);
  }

  // Write the console log so we can see what the adapter reported.
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'console.log'),
    consoleLog.join('\n'),
  );

  await browser.close();
  console.log(`Done. ${consoleLog.length} console messages captured.`);
})();
