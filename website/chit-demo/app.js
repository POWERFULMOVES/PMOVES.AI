// app.js — CHIT Playground: real WebCrypto HMAC-SHA256 signing + verification

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

let currentScenario = 'consciousness';
let currentCGP = null;
let signedCGP = null;
let tampered = false;

// ─── Navigation ───
const sections = ['fundamentals', 'encode', 'sign', 'bus', 'verify'];
$$('.nav a').forEach(a => {
  a.addEventListener('click', () => {
    const target = a.dataset.target;
    sections.forEach(s => $(`#${s}`).style.display = s === target ? '' : 'none');
    $$('.nav a').forEach(n => n.classList.toggle('active', n === a));
  });
});

// ─── JSON helpers ───
function canonicalize(obj) {
  if (Array.isArray(obj)) return '[' + obj.map(canonicalize).join(',') + ']';
  if (obj && typeof obj === 'object') {
    const keys = Object.keys(obj).sort();
    return '{' + keys.map(k => JSON.stringify(k) + ':' + canonicalize(obj[k])).join(',') + '}';
  }
  return JSON.stringify(obj);
}

function stripSig(cgp) {
  const copy = structuredClone(cgp);
  delete copy.sig;
  return copy;
}

async function computeShapeId(cgp) {
  const canon = canonicalize(stripSig(cgp));
  const data = new TextEncoder().encode(canon);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
}

// ─── WebCrypto HMAC-SHA256 ───
async function deriveKey(passphrase) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw', enc.encode(passphrase), 'PBKDF2', false, ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: enc.encode('pmoves-chit-salt'), iterations: 10000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign', 'verify']
  );
}

async function signCGP(cgp, passphrase) {
  const canon = canonicalize(stripSig(cgp));
  const key = await deriveKey(passphrase);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(canon));
  const b64 = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return {
    ...structuredClone(cgp),
    sig: { alg: 'HMAC-SHA256', hmac: b64, key_id: 'demo-passphrase' }
  };
}

async function verifyCGP(signed, passphrase) {
  if (!signed.sig || !signed.sig.hmac) return false;
  const expectedSig = signed.sig.hmac;
  const canon = canonicalize(stripSig(signed));
  const key = await deriveKey(passphrase);
  const sigBytes = Uint8Array.from(atob(expectedSig), c => c.charCodeAt(0));
  return crypto.subtle.verify('HMAC', key, sigBytes, new TextEncoder().encode(canon));
}

// ─── Scenario rendering ───
function loadScenario(name) {
  currentScenario = name;
  const scenario = SCENARIOS[name];
  currentCGP = structuredClone(scenario.cgp);
  signedCGP = null;
  tampered = false;

  $$('.scenario-btn').forEach(b => b.classList.toggle('active', b.dataset.scenario === name));
  $('#scenario-desc').innerHTML = `<p>${scenario.desc}</p><p class="u-caption">▸ source: <a class="src" target="_blank" rel="noopener" href="https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/${scenario.source}">${scenario.source}</a></p>`;

  renderCGPTemplate();
  renderEncode();
  renderSign();
  renderVerify();
}

function renderCGPTemplate() {
  const minimal = {
    spec: "chit.cgp.v1.0",
    meta: { source: "text|audio|video|economic", K: 1, bins: 4, backend: "model-name" },
    super_nodes: [{
      id: "domain_id",
      constellations: [{
        id: "concept_id",
        anchor: [0.4, -0.2, 0.7],
        spectrum: [0.1, 0.35, 0.4, 0.15],
        points: [
          { id: "pt_0", proj: 0.5, conf: 0.9, text: "A sentence or record." }
        ]
      }]
    }],
    sig: { alg: "HMAC-SHA256", hmac: "base64-signature", key_id: "CHIT_SIGNING_KEY" }
  };
  $('#cgp-template').textContent = JSON.stringify(minimal, null, 2);
}

// ─── Encode section ───
function renderEncode() {
  const cgp = currentCGP;
  if (!cgp || !cgp.super_nodes) return;

  // Units
  const allPoints = cgp.super_nodes.flatMap(sn =>
    (sn.constellations || []).flatMap(c => (c.points || []).map(p => ({ ...p, constellation: c.id })))
  );
  $('#encode-units').innerHTML = `
    <p><strong>${allPoints.length} units</strong> from ${(cgp.super_nodes[0].constellations || []).length} constellation(s):</p>
    <table class="table">
      <thead><tr><th>ID</th><th>Text / Summary</th><th class="num">Proj</th><th class="num">Conf</th><th>Constellation</th></tr></thead>
      <tbody>
        ${allPoints.map(p => `<tr><td class="mono">${p.id}</td><td>${p.text || p.summary || ''}</td><td class="num">${p.proj?.toFixed(2) || '—'}</td><td class="num">${p.conf?.toFixed(2) || '—'}</td><td class="mono">${p.constellation}</td></tr>`).join('')}
      </tbody>
    </table>`;

  // Anchors
  const consts = cgp.super_nodes[0].constellations || [];
  $('#encode-anchors').innerHTML = `
    <table class="table">
      <thead><tr><th>Constellation</th><th>Anchor vector</th><th>Summary</th></tr></thead>
      <tbody>
        ${consts.map(c => `<tr><td class="mono">${c.id}</td><td class="anchor-viz">[${(c.anchor || []).map(v => v.toFixed(2)).join(', ')}]</td><td>${c.summary || ''}</td></tr>`).join('')}
      </tbody>
    </table>`;

  // Spectra
  $('#encode-spectra').innerHTML = consts.map(c => {
    const max = Math.max(...(c.spectrum || [1]));
    return `
      <div style="margin-bottom:16px">
        <div class="mono" style="font-size:13px;margin-bottom:4px">${c.id}</div>
        <div class="spectrum-row">
          ${(c.spectrum || []).map(v => `<div class="spectrum-bar" style="height:${(v / max * 70).toFixed(0)}px" title="${v.toFixed(2)}"></div>`).join('')}
        </div>
        <div class="anchor-viz">spectrum: [${(c.spectrum || []).map(v => v.toFixed(2)).join(', ')}]</div>
      </div>`;
  }).join('');

  // Full CGP
  $('#encode-cgp').textContent = JSON.stringify(cgp, null, 2);
}

// ─── Sign section ───
function renderSign() {
  const canon = canonicalize(stripSig(currentCGP));
  $('#sign-canonical').textContent = canon;
  $('#sign-result-card').style.display = signedCGP ? '' : 'none';
  if (signedCGP) {
    $('#sign-result').textContent = JSON.stringify(signedCGP, null, 2);
  }
}

$('#do-sign')?.addEventListener('click', async () => {
  const pass = $('#passphrase').value || 'pmoves-chit-demo-key';
  ['sign-step-1','sign-step-2','sign-step-3','sign-step-4'].forEach((id, i) => {
    setTimeout(() => { $('#' + id).classList.add('active'); }, i * 300);
  });
  signedCGP = await signCGP(currentCGP, pass);
  setTimeout(() => {
    renderSign();
    $('#sign-badge').textContent = 'SIGNED';
    $('#sign-badge').className = 'badge-ok';
  }, 1200);
});

$('#go-verify')?.addEventListener('click', () => {
  $$('.nav a').forEach(a => {
    if (a.dataset.target === 'verify') a.click();
  });
});

// ─── Shape ID ───
$('#compute-shape-id')?.addEventListener('click', async () => {
  const id = await computeShapeId(currentCGP);
  const canon = canonicalize(stripSig(currentCGP));
  const data = new TextEncoder().encode(canon);
  const hash = await crypto.subtle.digest('SHA-256', data);
  const fullHash = Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, '0')).join('');
  $('#shape-id-out').textContent = `canonical JSON length: ${canon.length} bytes\nSHA-256: ${fullHash}\nShape ID (first 16 hex): ${id}`;
});

// ─── Verify section ───
function renderVerify() {
  const cgpToShow = tampered && signedCGP ? tamperWith(signedCGP) : (signedCGP || currentCGP);
  $('#verify-cgp').textContent = JSON.stringify(cgpToShow, null, 2);
  $('#verify-status').innerHTML = '';
  $('#verify-explanation').innerHTML = '';
}

function tamperWith(cgp) {
  const copy = structuredClone(cgp);
  for (const sn of (copy.super_nodes || [])) {
    for (const c of (sn.constellations || [])) {
      for (const p of (c.points || [])) {
        if (p.text) {
          p.text = p.text.replace(/\$[\d,.]+/, '$9,999.99')
                         .replace(/\d+/, '9999')
                         .replace(/less water/i, 'MORE water');
          return copy;
        }
      }
    }
  }
  return copy;
}

$('#do-verify')?.addEventListener('click', async () => {
  const pass = $('#passphrase').value || 'pmoves-chit-demo-key';
  const cgpToCheck = tampered && signedCGP ? tamperWith(signedCGP) : (signedCGP || currentCGP);

  if (!cgpToCheck.sig) {
    $('#verify-status').innerHTML = '<span class="cross">✗</span> No signature found — sign the CGP first (§03).';
    $('#verify-explanation').innerHTML = '<p>The CGP has no <span class="mono">sig</span> field. Go to §03 Sign to create one.</p>';
    return;
  }

  const isValid = await verifyCGP(cgpToCheck, pass);

  if (isValid) {
    $('#verify-status').innerHTML = '<span class="check">✓</span> <span class="badge-ok">VERIFIED</span> — signature is valid. The CGP has not been tampered with.';
    $('#verify-explanation').innerHTML = `
      <p>The verification re-canonicalized the JSON (stripping <span class="mono">sig</span>), re-derived the HMAC key from your passphrase using PBKDF2 (10000 iterations), and checked the signature. It matched — the packet is intact.</p>
      <p><strong>This is what every consumer on the Geometry Bus does</strong> before accepting a CGP. If the signature doesn't verify, the packet is rejected.</p>`;
  } else {
    $('#verify-status').innerHTML = '<span class="cross">✗</span> <span class="badge-fail">TAMPERED</span> — signature verification FAILED. The content has been modified after signing.';
    $('#verify-explanation').innerHTML = `
      <p>The verification re-canonicalized the JSON and the HMAC didn't match. Someone (you!) changed the content after it was signed. Even a single character difference in the canonical JSON produces a completely different SHA-256 hash.</p>
      <p><strong>This is the tamper-evidence guarantee:</strong> any modification to a signed CGP — whether by a corrupt operator, a network error, or a malicious actor — is immediately detectable by anyone with the passphrase.</p>`;
  }
});

$('#do-tamper')?.addEventListener('click', () => {
  if (!signedCGP) {
    $('#verify-status').innerHTML = '<span class="cross">✗</span> Sign the CGP first (§03), then tamper.';
    return;
  }
  tampered = true;
  const tamperedCGP = tamperWith(signedCGP);
  $('#verify-cgp').textContent = JSON.stringify(tamperedCGP, null, 2);
  $('#verify-status').innerHTML = '<span style="color:#f0a020">⚠ Tampered — click Verify to see it fail.</span>';
});

$('#do-reset')?.addEventListener('click', () => {
  tampered = false;
  renderVerify();
});

// ─── Init ───
$$('.scenario-btn').forEach(btn => {
  btn.addEventListener('click', () => loadScenario(btn.dataset.scenario));
});

loadScenario('consciousness');
