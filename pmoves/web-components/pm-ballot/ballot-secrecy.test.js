// Ballot secrecy conformance — A2UI v0.2 spec §5.4 (receipt model) + §5.5
// (secrecy & coercion resistance).
//
// These are the security properties the spec asserts. They are executable here
// because the conformance harness checks a11y/tokens/shadow but never casts a
// vote, so nothing enforced §5.4/§5.5 until now.
//
// Threat model (spec §5.5): a co-op recall ballot where the board being voted
// on can retaliate against residents. The board is assumed to be able to read
// anything published to shared state and to know the voter roster and options.
//
// Run:  node pmoves/web-components/pm-ballot/ballot-secrecy.test.js
// Needs: a static server on 127.0.0.1:8765 at repo root (see runner below).

const { chromium } = require('playwright');
const http = require('http');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '../../..');
const PORT = 8765;

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css' };

function serve() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const rel = decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/, '');
      const file = path.join(REPO_ROOT, rel);
      if (!file.startsWith(REPO_ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        res.writeHead(404); res.end('nf'); return;
      }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' });
      fs.createReadStream(file).pipe(res);
    });
    server.listen(PORT, '127.0.0.1', () => resolve(server));
  });
}

const OPTIONS = [
  { id: 'retain-board', label: 'Retain board' },
  { id: 'no-confidence', label: 'No confidence' },
  { id: 'abstain', label: 'Abstain' },
];

const PAGE = `<!doctype html><html><body>
<pm-ballot id="b" ballot-id="fordham-recall-2026" title="Recall"
  options='${JSON.stringify(OPTIONS)}' eligible-voters="47" quorum="0.5"></pm-ballot>
<script type="module" src="/pmoves/web-components/pm-ballot/pm-ballot.js"></script>
</body></html>`;

const results = [];
function check(name, pass, detail) {
  results.push({ name, pass, detail });
  console.log(`  ${pass ? 'PASS' : 'FAIL'}  ${name}`);
  if (!pass && detail) console.log(`          ${detail}`);
}

(async () => {
  const server = await serve();
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.route('**/ballot-fixture.html', (r) =>
    r.fulfill({ status: 200, contentType: 'text/html', body: PAGE }));
  await page.goto(`http://127.0.0.1:${PORT}/ballot-fixture.html`);
  await page.waitForFunction(() => customElements.get('pm-ballot'));

  const SECRET = 'no-confidence';

  // Cast a vote as a known resident.
  const cast = await page.evaluate(async (choice) => {
    const b = document.getElementById('b');
    const receipt = await b.castVote(choice, 'apt-4B');
    return { receipt, state: b.state };
  }, SECRET);

  console.log('\n§5.5 rule 1 — public state never carries (voterId, choice) in any form\n');

  // --- 1. Published RECEIPTS must not carry the choice --------------------
  // Scoped to receipts, not the whole state: `tally` legitimately keys on
  // option ids (that IS the public aggregate + quorum bar). What must never
  // be published is a *per-voter* record of the choice.
  const receiptsJson = JSON.stringify(cast.state.receipts || []);
  check(
    'published receipts do not contain the plaintext choice',
    !receiptsJson.includes(SECRET),
    `receipts payload contains "${SECRET}" -> every client pulling state reads the vote`
  );

  // --- 2. voterId must not be linkable in published state -----------------
  const stateJson = JSON.stringify(cast.state);
  check(
    'published state does not contain the voterId',
    !stateJson.includes('apt-4B'),
    'state payload contains "apt-4B" -> votes are attributable by name'
  );

  // --- 3. Receipts stay sealed while the ballot is open -------------------
  check(
    'receipts are not published while the ballot is open',
    Array.isArray(cast.state.receipts) && cast.state.receipts.length === 0,
    `${(cast.state.receipts || []).length} receipt(s) visible mid-ballot -> live correlation with tally`
  );

  // Close the ballot; the log publishes. Everything below inspects the log a
  // resident (or the board) can read after close.
  const closed = await page.evaluate(() => {
    const b = document.getElementById('b');
    b.setAttribute('closes-at', '2020-01-01T00:00:00Z');   // in the past
    return b.state;
  });
  const published = (closed.receipts || [])[0];

  // --- 4. Published log must resist a MAXIMAL attacker --------------------
  // Assume the worst: the board knows ballotId, the roster, every option, AND
  // the exact ts (e.g. they watched the resident vote). Only the voter-held
  // nonce stands between them and the vote.
  const recovered = await page.evaluate(async ({ pub, options, ts }) => {
    if (!pub || !pub.receiptHash) return 'no-receipt';
    const enc = new TextEncoder();
    const sha = async (s) => {
      const d = await crypto.subtle.digest('SHA-256', enc.encode(s));
      return '0x' + Array.from(new Uint8Array(d)).map((b) => b.toString(16).padStart(2, '0')).join('');
    };
    const np = (...f) => f.map((x) => `${String(x).length}:${x}`).join('');
    for (const opt of options) {
      if (await sha(`fordham-recall-2026|apt-4B|${opt.id}|${ts}`) === pub.receiptHash) return opt.id;
      if (await sha(np('fordham-recall-2026', 'apt-4B', opt.id, ts)) === pub.receiptHash) return opt.id;
    }
    return null;
  }, { pub: published, options: OPTIONS, ts: cast.receipt.ts });

  check(
    'published receipt resists enumeration even when ts and voterId are known',
    recovered === null,
    `recovered vote "${recovered}" from the published log + roster + options + exact ts`
  );

  // --- 4. Voter must receive a nonce to keep (§5.4) -----------------------
  check(
    'voter receives a nonce as part of their kept receipt',
    typeof cast.receipt?.nonce === 'string' && /^[0-9a-f]{32}$/.test(cast.receipt.nonce),
    `receipt.nonce = ${JSON.stringify(cast.receipt?.nonce)} (want 128-bit hex, voter-held)`
  );

  // --- 5. Published receipt carries only {receiptHash, status} ------------
  // No `ts`: an observer who logged the live tally timeline could otherwise
  // re-link a receipt to the moment its option incremented. The voter keeps
  // the exact ts privately; presence-in-log is what verification needs.
  const pubKeys = published ? Object.keys(published).sort() : [];
  check(
    'published receipt exposes only receiptHash/status (no ts)',
    JSON.stringify(pubKeys) === JSON.stringify(['receiptHash', 'status']),
    `published receipt keys = ${JSON.stringify(pubKeys)}`
  );

  // --- 6. §5.4 delimiter canonicalization ---------------------------------
  // "distinct input tuples can never concatenate to the same string"
  const collide = await page.evaluate(async () => {
    const b = document.getElementById('b');
    if (typeof b._preimage !== 'function') return 'no-_preimage-fn';
    const a = b._preimage('ballot', 'apt-4B|yes', 'no', 'T', 'n');
    const c = b._preimage('ballot', 'apt-4B', 'yes|no', 'T', 'n');
    return a === c ? 'COLLIDE' : 'distinct';
  });
  check(
    'distinct (voterId, choice) tuples cannot produce the same preimage',
    collide === 'distinct',
    `pipe-injected tuples -> ${collide}`
  );

  // --- 7. Timing correlation: the nonce is useless if a receipt and its
  // tally increment publish in the same state update. An observer polling
  // data-state-source diffs consecutive snapshots and re-links them without
  // touching the hash. Not covered by the spec — found while implementing §5.4.
  const correlated = await page.evaluate(async () => {
    const b = document.getElementById('b');
    const snap = () => JSON.parse(JSON.stringify(b.state));
    const before = snap();
    await b.castVote('abstain', 'apt-9C');
    const after = snap();
    const fresh = (after.receipts || []).filter(
      (r) => !(before.receipts || []).some((x) => x.receiptHash === r.receiptHash));
    let bumped = null;
    for (const k of Object.keys(after.tally || {})) {
      if (k !== '_total' && (after.tally[k] || 0) > (before.tally[k] || 0)) bumped = k;
    }
    // Linkable only if exactly one receipt appeared alongside exactly one bump.
    return fresh.length === 1 && bumped ? bumped : null;
  });
  check(
    'a state-polling observer cannot link a receipt to a tally increment',
    correlated === null,
    `observer recovered "${correlated}" by diffing two state snapshots — nonce bypassed entirely`
  );

  await browser.close();
  server.close();

  const failed = results.filter((r) => !r.pass);
  console.log(`\n${results.length - failed.length}/${results.length} passed`);
  process.exit(failed.length ? 1 : 0);
})();
