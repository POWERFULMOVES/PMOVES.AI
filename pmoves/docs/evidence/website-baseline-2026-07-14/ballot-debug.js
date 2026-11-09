// Debug pm-ballot rendering
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const consoleMsgs = [];
  const errors = [];
  page.on('console', (m) => consoleMsgs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', (e) => errors.push(`[pageerror] ${e.message}`));

  await page.goto('http://127.0.0.1:8765/pmoves/web-components/pm-ballot/demo.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  const result = await page.evaluate(() => {
    const b = document.getElementById('b');
    if (!b) return { error: 'no ballot' };
    const sr = b.shadowRoot;
    if (!sr) return { error: 'no shadow root' };
    const article = sr.querySelector('article');
    return {
      ballotExists: true,
      shadowExists: true,
      articleExists: !!article,
      articleHTML: article ? article.outerHTML.slice(0, 500) : null,
      articleBox: article ? article.getBoundingClientRect() : null,
      hostBox: b.getBoundingClientRect(),
      optionsRendered: sr.querySelectorAll('.option').length,
      shadowChildrenCount: sr.children.length,
      shadowInnerHTML: sr.innerHTML.slice(0, 200),
    };
  });

  console.log(JSON.stringify(result, null, 2));
  console.log('\n=== CONSOLE ===');
  consoleMsgs.forEach((m) => console.log(m));
  console.log('\n=== ERRORS ===');
  errors.forEach((e) => console.log(e));
  await browser.close();
})();
