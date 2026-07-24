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
  console.log('Loading empty shell...');
  await page.goto('http://localhost:3000/', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({
    path: path.join(EVIDENCE_DIR, '01-shell-empty.png'),
    fullPage: false,
  });
  console.log('  -> 01-shell-empty.png');

  // Then, load each public room and screenshot the composed desktop.
  for (const room of ROOMS) {
    console.log(`Loading room ${room.id}...`);
    // Use 'domcontentloaded' instead of 'networkidle' because the OpenRoom
    // shell has persistent background activity (LFM config fetch, vibe
    // container, etc.) that never reaches idle. 3s wait after DOM ready
    // gives the room adapter time to fetch the manifest, register apps,
    // and open the windows.
    await page.goto(`http://localhost:3000/?room=${room.id}`, {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    });
    await page.waitForTimeout(4000);
    const filename = `02-room-${room.label}.png`;
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, filename),
      fullPage: false,
    });
    console.log(`  -> ${filename}`);
  }

  // Write the console log so we can see what the adapter reported.
  fs.writeFileSync(
    path.join(EVIDENCE_DIR, 'console.log'),
    consoleLog.join('\n'),
  );

  await browser.close();
  console.log(`Done. ${consoleLog.length} console messages captured.`);
})();
