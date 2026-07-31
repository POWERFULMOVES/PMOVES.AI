// pillars-lab.js — interactive laboratories for Pillars 1, 3, 4, 5.
// Same standard as the Poincaré rebuild: every number on screen is computed
// here, in your browser, with the parameters the repo implementations
// actually use. Where the shipped code differs from the doc prose, the lab
// says so. No canned charts.

/* ═════════════ Pillar 1 · Dirichlet Distributions ═════════════
 * Parameters mirrored from dirichlet-weights.ts:
 *   smoothingAlpha = 0.1 (base pseudo-count — the non-zero-share guarantee)
 *   concentrationK = 1.0
 *   update rule (ts:83-89): alpha_i = smoothingAlpha + amount·concentrationK,
 *   accumulating amount·K on each recorded contribution.
 */
const DIR_SMOOTHING = 0.1;
const DIR_K = 1.0;
const dirState = { alpha: [DIR_SMOOTHING, DIR_SMOOTHING, DIR_SMOOTHING], names: ['A', 'B', 'C'] };

// Marsaglia–Tsang gamma sampler (with the alpha<1 boost); Dirichlet = normalized gammas.
function sampleGamma(alpha) {
  if (alpha < 1) {
    const u = Math.random();
    return sampleGamma(alpha + 1) * Math.pow(u, 1 / alpha);
  }
  const d = alpha - 1 / 3, c = 1 / Math.sqrt(9 * d);
  for (;;) {
    let x, v;
    do { x = gaussian(); v = 1 + c * x; } while (v <= 0);
    v = v * v * v;
    const u = Math.random();
    if (u < 1 - 0.0331 * x * x * x * x) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}
let gaussSpare = null;
function gaussian() {
  if (gaussSpare !== null) { const s = gaussSpare; gaussSpare = null; return s; }
  let u, v, s;
  do { u = Math.random() * 2 - 1; v = Math.random() * 2 - 1; s = u * u + v * v; } while (s >= 1 || s === 0);
  const m = Math.sqrt(-2 * Math.log(s) / s);
  gaussSpare = v * m;
  return u * m;
}
function sampleDirichlet(alpha) {
  const g = alpha.map(sampleGamma);
  const s = g.reduce((a, b) => a + b, 0);
  return g.map((x) => x / s);
}

function drawDirichlet() {
  const svg = document.getElementById('lab-dirichlet-svg');
  const info = document.getElementById('lab-dirichlet-info');
  if (!svg || !info) return;
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  svg.innerHTML = '';
  const W = 460, H = 400;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  // 2-simplex triangle: barycentric (w0,w1,w2) → 2D
  const V = [[W / 2, 28], [36, H - 30], [W - 36, H - 30]]; // A top, B left, C right
  const bary = (w) => [
    w[0] * V[0][0] + w[1] * V[1][0] + w[2] * V[2][0],
    w[0] * V[0][1] + w[1] * V[1][1] + w[2] * V[2][1],
  ];
  svg.appendChild(mk('path', { d: `M ${V[0]} L ${V[1]} L ${V[2]} Z`, fill: 'none', stroke: '#7C3AED', 'stroke-opacity': 0.6 }));
  ['A (w₁=1)', 'B (w₂=1)', 'C (w₃=1)'].forEach((t, i) => {
    const lbl = mk('text', { x: V[i][0], y: V[i][1] + (i === 0 ? -8 : 18), 'text-anchor': 'middle', 'font-size': 11, fill: '#9a9a9a' });
    lbl.textContent = t; svg.appendChild(lbl);
  });
  const a = dirState.alpha, S = a[0] + a[1] + a[2];
  // 700 real draws
  for (let i = 0; i < 700; i++) {
    const p = bary(sampleDirichlet(a));
    svg.appendChild(mk('circle', { cx: p[0], cy: p[1], r: 1.3, fill: '#0D9488', 'fill-opacity': 0.35 }));
  }
  // mean E[w_i] = alpha_i / sum
  const mean = a.map((x) => x / S);
  const mp = bary(mean);
  svg.appendChild(mk('circle', { cx: mp[0], cy: mp[1], r: 5, fill: '#FB7185', stroke: '#fff', 'stroke-width': 1 }));
  info.innerHTML =
    `<div class="mono">α = [${a.map((x) => x.toFixed(2)).join(', ')}] · Σα = ${S.toFixed(2)}</div>` +
    `<div class="mono">E[w] = α/Σα = [${mean.map((x) => x.toFixed(3)).join(', ')}] — the ● marker</div>` +
    `<div>700 fresh draws per render (Marsaglia–Tsang gamma → normalize). Note no draw ever hits a vertex or edge exactly: <span class="mono">smoothingAlpha = ${DIR_SMOOTHING}</span> is the non-zero-share guarantee from <span class="mono">dirichlet-weights.ts</span>.</div>`;
}

function dirContribute(i, amount) {
  // ts:83 — existing.alpha += amount * concentrationK
  dirState.alpha[i] += amount * DIR_K;
  drawDirichlet();
}
function dirReset() {
  dirState.alpha = [DIR_SMOOTHING, DIR_SMOOTHING, DIR_SMOOTHING];
  drawDirichlet();
}

/* ═════════════ Pillar 3 · Merkle Proofs ═════════════
 * Mirrors shape-attribution.ts: sha256 leaf over the attribution record,
 * pairwise parent hashing, inclusion proof {path, pathIndices}, verifyProof
 * chain. The four leaves are REAL records: the three week-1 ledger
 * transactions and the canonical result event from the measured export run
 * of 2026-07-25 (see the Tokenomics section's Verified Actuals card).
 */
const MERKLE_RECORDS = [
  { address: 'Group B Pool', action: 'transfer', amount: '1880.71', week: 1, category: 'Internal Transfer' },
  { address: 'Group A Pool', action: 'withdrawal', amount: '3864.05', week: 1, category: 'External Spending' },
  { address: 'Group B Pool', action: 'withdrawal', amount: '1513.16', week: 1, category: 'External Spending' },
  { address: 'export-service', action: 'result-event', amount: '156', week: 52, category: 'tokenism.export.result.v1' },
];
let merkleTamper = null; // {leafIdx, field, value}
let merkleSelected = 0;

async function sha256Hex(str) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(str));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function buildMerkle(records) {
  const leaves = [];
  for (const r of records) {
    leaves.push(await sha256Hex(JSON.stringify(r)));
  }
  const levels = [leaves];
  let cur = leaves;
  while (cur.length > 1) {
    const next = [];
    for (let i = 0; i < cur.length; i += 2) {
      const left = cur[i], right = cur[i + 1] !== undefined ? cur[i + 1] : cur[i];
      next.push(await sha256Hex(left + right));
    }
    levels.push(next);
    cur = next;
  }
  return { levels, root: cur[0] };
}

function merkleProof(levels, leafIdx) {
  const path = [], pathIndices = [];
  let idx = leafIdx;
  for (let l = 0; l < levels.length - 1; l++) {
    const level = levels[l];
    const sib = idx % 2 === 0 ? idx + 1 : idx - 1;
    path.push(level[sib] !== undefined ? level[sib] : level[idx]);
    pathIndices.push(idx % 2); // 0 = we are left, 1 = we are right
    idx = Math.floor(idx / 2);
  }
  return { path, pathIndices };
}

async function verifyMerkle(leafHash, proof, root) {
  let cur = leafHash;
  for (let i = 0; i < proof.path.length; i++) {
    cur = proof.pathIndices[i] === 0
      ? await sha256Hex(cur + proof.path[i])
      : await sha256Hex(proof.path[i] + cur);
  }
  return cur === root;
}

async function drawMerkle() {
  const el = document.getElementById('lab-merkle');
  if (!el || !window.crypto || !crypto.subtle) return;
  const records = MERKLE_RECORDS.map((r, i) => {
    if (merkleTamper && merkleTamper.leafIdx === i) {
      return { ...r, amount: merkleTamper.value };
    }
    return r;
  });
  const honest = await buildMerkle(MERKLE_RECORDS);
  const current = await buildMerkle(records);
  const proof = merkleProof(current.levels, merkleSelected);
  const ok = await verifyMerkle(current.levels[0][merkleSelected], proof, honest.root);
  const sh = (h) => `<span class="mono">${h.slice(0, 10)}…</span>`;
  let html = `<div><b>Committed root</b> (built from the untampered records): ${sh(honest.root)}</div>`;
  html += `<table class="table u-mt-8"><thead><tr><th>#</th><th>record (real, run 2026-07-25)</th><th>leaf = sha256(record)</th></tr></thead><tbody>`;
  records.forEach((r, i) => {
    const tampered = merkleTamper && merkleTamper.leafIdx === i;
    html += `<tr style="${i === merkleSelected ? 'outline:1px solid #7C3AED' : ''}${tampered ? ';background:rgba(251,113,133,.08)' : ''}">
      <td>${i}</td>
      <td class="mono">${r.address} · ${r.action} · $${r.amount} · wk${r.week} · ${r.category}${tampered ? ' <b style="color:#FB7185">TAMPERED</b>' : ''}</td>
      <td>${sh(current.levels[0][i])} <button data-mleaf="${i}" class="mini-btn">prove</button></td></tr>`;
  });
  html += `</tbody></table>`;
  html += `<div class="u-mt-8"><b>Inclusion proof for leaf ${merkleSelected}</b> — path: [${proof.path.map((h) => h.slice(0, 8) + '…').join(', ')}] · indices: [${proof.pathIndices.join(', ')}]</div>`;
  html += ok
    ? `<div style="color:#0D9488" class="u-mt-8"><b>verifyProof → TRUE</b> — the recomputed chain reproduces the committed root.</div>`
    : `<div style="color:#FB7185" class="u-mt-8"><b>verifyProof → FALSE</b> — the chain ends at ${sh(current.root)}, which is NOT the committed root. One edited amount broke every hash above it. This is the tamper-evidence pillar, live.</div>`;
  el.innerHTML = html;
  el.querySelectorAll('[data-mleaf]').forEach((b) => b.addEventListener('click', () => { merkleSelected = +b.dataset.mleaf; drawMerkle(); }));
}
function merkleTamperToggle() {
  merkleTamper = merkleTamper ? null : { leafIdx: 0, field: 'amount', value: '9999.99' };
  const btn = document.getElementById('lab-merkle-tamper');
  if (btn) btn.textContent = merkleTamper ? 'restore the real amount' : 'tamper: set leaf 0 amount to $9999.99';
  drawMerkle();
}

/* ═════════════ Pillar 4 · Zeta Spectral Filtering ═════════════
 * Mirrors zeta-filter.ts exactly: the first 20 non-trivial zeta zeros
 * (verbatim constants), weights w_n = decay^n / log(γ_n) (ts:120-128),
 * normalized, applied as CIRCULAR convolution over a CGP spectrum
 * (filterSpectrum, ts:176-199). Defaults: numZeros=10, decay=0.9.
 */
const ZETA_ZEROS = [
  14.134725141734693790, 21.022039638771554993, 25.010857580145688763,
  30.424876125859513210, 32.935061587739189691, 37.586178158825671257,
  40.918719012147495187, 43.327073280914999519, 48.005150881167159727,
  49.773832477672302182, 52.970321477714460644, 56.446247697063394804,
  59.347044002602353080, 60.831778524609809844, 65.112544048081606661,
  67.079810529494173714, 69.546401711173979253, 72.067157674481907582,
  75.704690699083933168, 77.144840068874805373,
];
const zetaState = { numZeros: 10, decay: 0.9 };

function zetaWeights() {
  const zeros = ZETA_ZEROS.slice(0, zetaState.numZeros);
  const w = zeros.map((g, i) => Math.pow(zetaState.decay, i) / Math.log(g));
  const s = w.reduce((a, b) => a + b, 0);
  return { zeros, weights: w, norm: w.map((x) => x / s) };
}
function zetaFilterSpectrum(spectrum, norm) {
  const out = new Array(spectrum.length).fill(0);
  for (let i = 0; i < spectrum.length; i++) {
    for (let k = 0; k < norm.length && k < spectrum.length; k++) {
      out[i] += spectrum[(i + k) % spectrum.length] * norm[k];
    }
  }
  const mx = Math.max(...out);
  return mx > 0 ? out.map((v) => v / mx) : out;
}

// The REAL 4-bin spectrum from the worked CGP example in 01_WHAT_IS_CHIT.md
const CGP_DOC_SPECTRUM = [0.10, 0.35, 0.40, 0.15];
// A longer demo spectrum, LABELED synthetic: structure + reproducible noise
function zetaDemoSpectrum() {
  const n = 32, out = [];
  for (let i = 0; i < n; i++) {
    const structure = 0.5 + 0.4 * Math.sin((i / n) * Math.PI * 3);
    const noise = 0.25 * (Math.sin(i * 12.9898) * 43758.5453 % 1);
    out.push(Math.max(0, Math.min(1, structure + noise)));
  }
  return out;
}

function drawZeta() {
  const el = document.getElementById('lab-zeta');
  if (!el) return;
  const { zeros, norm } = zetaWeights();
  const bar = (vals, color, label) => {
    const w = 420, h = 90, bw = w / vals.length;
    let s = `<div class="mono" style="font-size:11px">${label}</div><svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w}px">`;
    vals.forEach((v, i) => {
      s += `<rect x="${i * bw + 1}" y="${h - v * (h - 8)}" width="${bw - 2}" height="${v * (h - 8)}" fill="${color}" fill-opacity="0.8"><title>${v.toFixed(4)}</title></rect>`;
    });
    return s + '</svg>';
  };
  const docFiltered = zetaFilterSpectrum(CGP_DOC_SPECTRUM, norm);
  const demo = zetaDemoSpectrum();
  const demoFiltered = zetaFilterSpectrum(demo, norm);
  el.innerHTML =
    `<div class="mono">w_n = ${zetaState.decay}ⁿ / ln(γ_n), normalized · first ${zetaState.numZeros} zeros: [${zeros.slice(0, 5).map((z) => z.toFixed(2)).join(', ')}…]</div>` +
    `<div class="u-mt-8">${bar(norm.map((x) => x / Math.max(...norm)), '#7C3AED', `filter weights over γ_1…γ_${zetaState.numZeros} (each column = one zeta zero)`)}</div>` +
    `<div class="grid c2 u-mt-8">
      <div>${bar(CGP_DOC_SPECTRUM, '#9a6fdf', 'REAL input: the 4-bin CGP spectrum from the worked example in 01_WHAT_IS_CHIT.md')}
           ${bar(docFiltered, '#0D9488', `filterSpectrum(·) → [${docFiltered.map((v) => v.toFixed(3)).join(', ')}]`)}</div>
      <div>${bar(demo, '#9a6fdf', 'SYNTHETIC demo input (labeled): 32 bins, structure + deterministic noise')}
           ${bar(demoFiltered, '#0D9488', 'filterSpectrum(·) — circular convolution smooths noise, keeps structure')}</div>
    </div>`;
}
function zetaSet(n, d) {
  zetaState.numZeros = n; zetaState.decay = d; drawZeta();
  const lbl = document.getElementById('lab-zeta-params');
  if (lbl) lbl.textContent = `numZeros=${n} · decay=${d.toFixed(2)}`;
}

/* ═════════════ Pillar 5 · Swarm Optimization ═════════════
 * HONESTY FIRST: swarm-attribution.ts states (lines 196-198) that it does
 * NOT perform mutation, selection, crossover, or particle updates — the
 * shipped code is the FITNESS SCORER + population tracker on
 * tokenism.swarm.population.v1. The doc prose ("mutate with Dirichlet
 * noise, select survivors") is the target architecture, not this layer.
 * Panel A below runs the REAL scorer (exact gini_reduction weights
 * ts:143-150, targets ts:298/312). Panel B is a clearly-labeled demo of
 * the evolutionary loop the docs describe, driving the real scorer.
 */
const SWARM_WEIGHTS = { gini: 0.6, poverty: 0.2, wealth: 0.1, participation: 0.05, spending: 0.025, savings: 0.025 };
const SWARM_TARGETS = { gini: 0.3, poverty: 0.1 };

function gini(values) {
  const v = [...values].sort((a, b) => a - b);
  const n = v.length, sum = v.reduce((a, b) => a + b, 0);
  if (sum === 0) return 0;
  let acc = 0;
  for (let i = 0; i < n; i++) acc += (2 * (i + 1) - n - 1) * v[i];
  return acc / (n * sum);
}
function swarmFitness(sim) {
  // mirrors calculateFitness component structure for the gini_reduction target
  const giniScore = sim.gini <= SWARM_TARGETS.gini ? 1 : Math.max(0, 1 - (sim.gini - SWARM_TARGETS.gini) / (1 - SWARM_TARGETS.gini));
  const povScore = sim.poverty <= SWARM_TARGETS.poverty ? 1 : Math.max(0, 1 - (sim.poverty - SWARM_TARGETS.poverty) / (1 - SWARM_TARGETS.poverty));
  const wealthScore = Math.max(0, Math.min(1, sim.wealthGrowth));
  const partScore = Math.max(0, Math.min(1, sim.participation));
  const w = SWARM_WEIGHTS;
  // spending/savings components held neutral (0.5) in the lab — they need the
  // full week-simulation record the scorer normally receives.
  return w.gini * giniScore + w.poverty * povScore + w.wealth * wealthScore +
         w.participation * partScore + w.spending * 0.5 + w.savings * 0.5;
}

const swarmState = { running: false, gen: 0, pop: [], history: [] };
function swarmInit() {
  swarmState.gen = 0; swarmState.history = [];
  swarmState.pop = Array.from({ length: 32 }, () =>
    Array.from({ length: 12 }, () => Math.random())
  ).map((v) => { const s = v.reduce((a, b) => a + b, 0); return v.map((x) => x / s); });
}
function allocationSim(alloc) {
  const g = gini(alloc);
  const poverty = alloc.filter((x) => x < (1 / alloc.length) * 0.5).length / alloc.length;
  return { gini: g, poverty, wealthGrowth: 0.5, participation: alloc.filter((x) => x > 0.01).length / alloc.length };
}
function swarmStep() {
  const scored = swarmState.pop.map((a) => ({ a, f: swarmFitness(allocationSim(a)) }));
  scored.sort((x, y) => y.f - x.f);
  const survivors = scored.slice(0, 16).map((s) => s.a);
  // Dirichlet-noise mutation (the doc-described operator, demo-labeled)
  const children = survivors.map((p) => {
    const noise = sampleDirichlet(p.map(() => 6));
    const child = p.map((x, i) => 0.85 * x + 0.15 * noise[i]);
    const s = child.reduce((a, b) => a + b, 0);
    return child.map((x) => x / s);
  });
  swarmState.pop = survivors.concat(children);
  swarmState.gen++;
  swarmState.history.push({ best: scored[0].f, mean: scored.reduce((a, s) => a + s.f, 0) / scored.length, gini: allocationSim(scored[0].a).gini });
}
function drawSwarm() {
  const el = document.getElementById('lab-swarm-plot');
  const info = document.getElementById('lab-swarm-info');
  if (!el || !info) return;
  const H = swarmState.history;
  const w = 460, h = 160;
  let s = `<svg viewBox="0 0 ${w} ${h}" style="width:100%;max-width:${w}px">`;
  if (H.length > 1) {
    const px = (i) => 8 + (i / (H.length - 1)) * (w - 16);
    const py = (v) => h - 10 - v * (h - 24);
    s += `<path d="M ${H.map((p, i) => `${px(i)},${py(p.best)}`).join(' L ')}" fill="none" stroke="#0D9488" stroke-width="1.6"/>`;
    s += `<path d="M ${H.map((p, i) => `${px(i)},${py(p.mean)}`).join(' L ')}" fill="none" stroke="#7C3AED" stroke-width="1.2" stroke-dasharray="3 3"/>`;
  }
  s += '</svg>';
  el.innerHTML = s;
  const last = H[H.length - 1];
  info.innerHTML = last
    ? `<span class="mono">gen ${swarmState.gen} · best fitness ${last.best.toFixed(4)} (solid) · mean ${last.mean.toFixed(4)} (dashed) · best-allocation Gini ${last.gini.toFixed(3)} → target ${SWARM_TARGETS.gini}</span>`
    : '<em>press run</em>';
}
let swarmTimer = null;
function swarmRun() {
  if (swarmTimer) { clearInterval(swarmTimer); swarmTimer = null; return; }
  if (!swarmState.pop.length) swarmInit();
  swarmTimer = setInterval(() => {
    swarmStep(); drawSwarm();
    if (swarmState.gen >= 120) { clearInterval(swarmTimer); swarmTimer = null; }
  }, 60);
}
function swarmReset() { if (swarmTimer) { clearInterval(swarmTimer); swarmTimer = null; } swarmInit(); swarmState.history = []; drawSwarm(); }

function drawScorerPanel() {
  const el = document.getElementById('lab-swarm-scorer');
  if (!el) return;
  const g = +document.getElementById('sw-gini').value / 100;
  const p = +document.getElementById('sw-pov').value / 100;
  const wg = +document.getElementById('sw-wealth').value / 100;
  const f = swarmFitness({ gini: g, poverty: p, wealthGrowth: wg, participation: 0.8 });
  el.innerHTML = `<span class="mono">fitness = 0.6·giniScore + 0.2·povertyScore + 0.1·wealthScore + 0.05·participation + 0.05·(spend/save neutral)
  → gini=${g.toFixed(2)} poverty=${p.toFixed(2)} wealthGrowth=${wg.toFixed(2)} ⇒ <b>fitness = ${f.toFixed(4)}</b></span>`;
}

/* ═════════════ init ═════════════ */
function initPillarLabs() {
  drawDirichlet();
  drawMerkle();
  drawZeta();
  swarmInit(); drawSwarm();
  const hook = (id, fn) => { const e = document.getElementById(id); if (e) e.addEventListener('click', fn); };
  hook('lab-dir-a', () => dirContribute(0, 1));
  hook('lab-dir-b', () => dirContribute(1, 1));
  hook('lab-dir-c', () => dirContribute(2, 1));
  hook('lab-dir-reset', dirReset);
  hook('lab-merkle-tamper', merkleTamperToggle);
  hook('lab-swarm-run', swarmRun);
  hook('lab-swarm-reset', swarmReset);
  const zn = document.getElementById('lab-zeta-n'), zd = document.getElementById('lab-zeta-d');
  const zUpd = () => zetaSet(+zn.value, +zd.value / 100);
  if (zn) zn.addEventListener('input', zUpd);
  if (zd) zd.addEventListener('input', zUpd);
  ['sw-gini', 'sw-pov', 'sw-wealth'].forEach((id) => {
    const e = document.getElementById(id);
    if (e) e.addEventListener('input', drawScorerPanel);
  });
  drawScorerPanel();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPillarLabs);
} else {
  initPillarLabs();
}
