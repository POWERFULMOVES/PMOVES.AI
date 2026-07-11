// app.js — UI wiring + D3 force graph + Three.js Poincaré disk
import * as THREE from './vendor/three.module.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
const sourceUrl = (key) => `https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/${SOURCES[key]}`;

// ---------- Theme ----------
const themeBtn = $('#theme-toggle');
const themeLbl = $('#theme-label');
themeBtn?.addEventListener('click', () => {
  const cur = document.documentElement.getAttribute('data-theme');
  const next = cur === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  themeLbl.textContent = next === 'dark' ? 'Light theme' : 'Dark theme';
  // re-render charts that bake in theme colors
  drawPoincare();
});

// ---------- Source link helper ----------
function fillSourceLinks() {
  $$('a.src[data-src]').forEach((a) => {
    const key = a.dataset.src;
    const path = SOURCES[key];
    if (!path) return;
    a.href = sourceUrl(key);
    a.textContent = path;
  });
  $$('a[data-src]').forEach((a) => {
    if (a.classList.contains('src')) return;
    const key = a.dataset.src;
    if (!SOURCES[key]) return;
    a.href = sourceUrl(key);
  });
}

// ---------- Pillar grid ----------
function renderPillars() {
  const wrap = $('#pillars-grid');
  wrap.innerHTML = PILLARS.map((p, i) => `
    <div class="pillar">
      <div class="ring"></div>
      <div class="role">Pillar ${i + 1}</div>
      <h3>${p.name}</h3>
      <p>${p.summary}</p>
      <div class="file mono">▸ ${p.file}</div>
    </div>`).join('');
}

// ---------- NATS table ----------
function renderNatsTable() {
  $('#nats-table tbody').innerHTML = NATS_SUBJECTS.map(n => `
    <tr><td><span class="mono">${n.subject}</span></td><td>${n.dir}</td><td>${n.purpose}</td></tr>`).join('');
}

// ---------- MOF stack ----------
function renderMof() {
  $('#mof-stack').innerHTML = MOF_COMPONENTS.map(c => `
    <div class="mof-row">
      <div class="a">${c.component}</div>
      <div class="b">${c.description}</div>
      <div class="c"><div class="label">MOF role</div><div>${c.mofRole}</div></div>
    </div>`).join('');

  $('#principles-grid').innerHTML = PRINCIPLES.map(p => `
    <div class="card">
      <div class="meta">${p.id}</div>
      <h3>${p.name}</h3>
      <p>${p.body}</p>
    </div>`).join('');
}

// ---------- Classes / types / roster / planes ----------
function renderTaxonomy() {
  $('#classes-grid').innerHTML = AGENT_CLASSES.map(c => `
    <div class="card">
      <div class="meta">${c.cls.toUpperCase()}</div>
      <h3 style="font-family:'JetBrains Mono', monospace; font-size:14px;">${c.prefix}</h3>
      <p>${c.role}</p>
      <p style="font-size:12px;color:var(--text-faint);margin-top:6px">e.g. ${c.examples.slice(0,3).join(' · ')}</p>
    </div>`).join('');

  $('#types-grid').innerHTML = AGENT_TYPES.map(t => `
    <div class="card" style="border-left:3px solid ${t.color};">
      <div class="meta">Tier ${t.tier} · ${t.element}</div>
      <h3>${t.type}</h3>
      <p><b>Strengths:</b> ${t.strengths}<br/><b>Weak:</b> ${t.weaknesses}</p>
    </div>`).join('');

  const colorOf = (typeName) => {
    const t = AGENT_TYPES.find(x => x.type === typeName);
    return t ? t.color : 'var(--text-faint)';
  };
  $('#roster-table tbody').innerHTML = AGENT_ROSTER.map(a => `
    <tr>
      <td><b>${a.name}</b></td>
      <td>${a.cls}</td>
      <td><span class="type-chip"><span class="swatch" style="background:${colorOf(a.primary)}"></span>${a.primary}</span></td>
      <td>${a.secondary ? `<span class="type-chip"><span class="swatch" style="background:${colorOf(a.secondary)}"></span>${a.secondary}</span>` : '—'}</td>
      <td class="mono">${a.tier}</td>
      <td>${a.stage}</td>
      <td class="mono">${a.layers}</td>
    </tr>`).join('');

  $('#planes-table tbody').innerHTML = PLANES.map(p => `
    <tr><td><b>${p.plane}</b></td><td>${p.function}</td><td>${p.agents}</td><td class="mono">${p.layers}</td></tr>`).join('');
}

// ---------- Layers + stages ----------
function renderEvolution() {
  $('#layers-table tbody').innerHTML = LAYERS.map(l => `
    <tr><td class="mono"><b>${l.id}</b></td><td>${l.name}</td><td>${l.desc}<br/><span style="color:var(--text-faint);font-size:12px">${l.agents}</span></td></tr>`).join('');
  $('#stages-table tbody').innerHTML = EVOLUTION_STAGES.map(s => `
    <tr><td><b>${s.stage}</b></td><td>${s.req}</td><td><span class="mono">${s.example}</span><br/><span style="color:var(--text-faint);font-size:12px">${s.analogy}</span></td></tr>`).join('');
}

// ---------- Skills ----------
function renderSkills() {
  $('#skills-grid').innerHTML = SKILLS.map(s => `
    <div class="card">
      <div class="meta">SKILL BUNDLE</div>
      <h3 class="mono" style="font-family:'JetBrains Mono', monospace;font-size:14px;">${s.id}</h3>
      <p><b>Purpose:</b> ${s.purpose}</p>
      <p style="font-size:12.5px;"><b>In:</b> ${s.input}<br/><b>Out:</b> ${s.output}</p>
    </div>`).join('');
}

// ---------- Tour ----------
function renderTour() {
  $('#tour-list').innerHTML = TOUR_STEPS.map(s => `
    <div class="tour-step">
      <div class="num">${String(s.n).padStart(2,'0')}</div>
      <div>
        <h3>${s.title}</h3>
        <p>${s.body}</p>
        <a class="src" href="${'https://github.com/POWERFULMOVES/PMOVES.AI/blob/main/' + s.src}" target="_blank" rel="noopener">${s.src}</a>
      </div>
    </div>`).join('');
}

// ---------- Coverage ----------
function renderCoverage() {
  $('#coverage-list').innerHTML = COVERAGE_NOTES.map(n => {
    // bold any path-like tokens
    const html = n.replace(/(pmoves\/[^\s,)]+|PMOVESCHIT\/\*|AGENTS\/\*|chit\.cgp\.v1\.0)/g, '<b>$1</b>');
    return `<li>${html}</li>`;
  }).join('');
}

// ---------- Sidebar nav: scrollspy ----------
function setupNav() {
  const navLinks = $$('#nav a');
  navLinks.forEach(a => a.addEventListener('click', (e) => {
    e.preventDefault();
    const id = a.dataset.target;
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));

  const targets = navLinks.map(a => document.getElementById(a.dataset.target)).filter(Boolean);
  const io = new IntersectionObserver((entries) => {
    entries.forEach(en => {
      if (en.isIntersecting && en.intersectionRatio > 0.18) {
        const id = en.target.id;
        navLinks.forEach(a => a.classList.toggle('active', a.dataset.target === id));
      }
    });
  }, { rootMargin: '-30% 0px -55% 0px', threshold: [0, 0.2, 0.5, 1] });
  targets.forEach(t => io.observe(t));
}

// ---------- D3 force graph (Geometry Bus) ----------
function renderBusGraph() {
  const svg = d3.select('#bus-graph');
  const W = 1200, H = 560;
  svg.attr('viewBox', `0 0 ${W} ${H}`);

  const colorByGroup = {
    node: '#0D9488',          // Agent Zero (lattice)
    linker: '#7C3AED',        // CHIT
    bus: '#d4a83a',           // NATS
    producer: '#9a6fdf',
    consumer: '#A78BFA',
    both: '#bce2e7',
    surface: '#6daa45',
    gap: '#c47a8a',
    matcher: '#67645e',
  };

  // legend
  const legendEl = $('#bus-legend');
  legendEl.innerHTML = [
    ['Lattice (Agent Zero)', colorByGroup.node],
    ['CHIT linker', colorByGroup.linker],
    ['NATS bus', colorByGroup.bus],
    ['Producer', colorByGroup.producer],
    ['Consumer', colorByGroup.consumer],
    ['Persistence', colorByGroup.both],
    ['Surface (Neo4j)', colorByGroup.surface],
    ['Gap (CH/Prom)', colorByGroup.gap],
  ].map(([n,c]) => `<span style="color:${c}">${n}</span>`).join('');

  const nodes = BUS_NODES.map(n => ({...n}));
  const links = BUS_LINKS.map(l => ({...l}));

  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id).distance(d => d.source === 'nats' || d.target === 'nats' ? 110 : 140).strength(0.6))
    .force('charge', d3.forceManyBody().strength(-360))
    .force('center', d3.forceCenter(W/2, H/2))
    .force('collide', d3.forceCollide(38))
    .alpha(1).alphaDecay(0.03);

  const linkSel = svg.append('g').selectAll('line').data(links).join('line').attr('class','link').attr('stroke-width', 1);
  const subjLabels = svg.append('g').selectAll('text.subjlabel').data(links).join('text').attr('class','subjlabel').text(d => d.subject);

  const node = svg.append('g').selectAll('g.node').data(nodes).join('g').attr('class','node').call(d3.drag()
    .on('start', (e,d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on('drag',  (e,d) => { d.fx = e.x; d.fy = e.y; })
    .on('end',   (e,d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; })
  );

  const radii = { node: 22, linker: 22, bus: 26 };
  node.append('circle')
    .attr('r', d => radii[d.group] || 16)
    .attr('fill', d => colorByGroup[d.group] || '#888');

  node.append('text')
    .attr('text-anchor','middle')
    .attr('dy', d => (radii[d.group] || 16) + 14)
    .text(d => d.name);

  // tooltip
  const tip = $('#tooltip');
  node.on('mouseenter', (e, d) => {
      tip.innerHTML = `<strong>${d.name}</strong><span class="role">${d.role} · ${d.layer}</span>`;
      tip.style.opacity = 1;
      // highlight links
      linkSel.classed('hl', l => l.source.id === d.id || l.target.id === d.id);
    })
    .on('mousemove', (e) => {
      tip.style.left = (e.clientX + 14) + 'px';
      tip.style.top = (e.clientY + 14) + 'px';
    })
    .on('mouseleave', () => { tip.style.opacity = 0; linkSel.classed('hl', false); });

  sim.on('tick', () => {
    nodes.forEach(n => { n.x = Math.max(40, Math.min(W-40, n.x)); n.y = Math.max(30, Math.min(H-30, n.y)); });
    linkSel
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    subjLabels
      .attr('x', d => (d.source.x + d.target.x)/2)
      .attr('y', d => (d.source.y + d.target.y)/2 - 4);
    node.attr('transform', d => `translate(${d.x},${d.y})`);
  });
}

// ---------- Three.js Poincaré disk ----------
let renderer, scene, camera, animationId;
function drawPoincare() {
  const canvas = $('#poincare-canvas');
  if (!canvas) return;
  if (animationId) cancelAnimationFrame(animationId);

  const cs = getComputedStyle(document.documentElement);
  const isDark = document.documentElement.getAttribute('data-theme') !== 'light';

  const dpr = Math.min(window.devicePixelRatio, 2);
  const rect = canvas.getBoundingClientRect();
  const W = rect.width, H = rect.height;

  if (!renderer) {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  }
  renderer.setPixelRatio(dpr);
  renderer.setSize(W, H, false);
  renderer.setClearColor(0x000000, 0);

  scene = new THREE.Scene();
  camera = new THREE.OrthographicCamera(-W/2, W/2, H/2, -H/2, -1000, 1000);
  camera.position.set(0,0,10);

  const R = Math.min(W, H) * 0.42;

  // Disk boundary + concentric circles
  const rings = isDark ? 0x2a2f2c : 0xd8d4cb;
  const ringStrong = isDark ? 0x3a4040 : 0xb9b4a8;
  for (let i = 1; i <= 6; i++) {
    const ringR = R * (i / 6);
    const geo = new THREE.RingGeometry(ringR - 0.4, ringR + 0.4, 256);
    const mat = new THREE.MeshBasicMaterial({ color: i === 6 ? ringStrong : rings, side: THREE.DoubleSide, transparent: true, opacity: i === 6 ? 0.75 : 0.4 });
    scene.add(new THREE.Mesh(geo, mat));
  }
  // radial spokes
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const pts = [new THREE.Vector3(0,0,0), new THREE.Vector3(Math.cos(a)*R, Math.sin(a)*R, 0)];
    const lg = new THREE.BufferGeometry().setFromPoints(pts);
    scene.add(new THREE.Line(lg, new THREE.LineBasicMaterial({ color: rings, transparent: true, opacity: 0.25 })));
  }

  // Build 76 agents grouped by class with hyperbolic-ish placement.
  // Class counts derived from the registry: Standard ~ 38, Specialized ~ 14, Utility ~ 22, Legendary 2.
  const groups = [
    { cls: 'Legendary', n: 2,  color: 0x0D9488, baseR: 0.05 }, // center
    { cls: 'Standard', n: 38, color: 0x7C3AED, baseR: 0.40 },
    { cls: 'Specialized', n: 14, color: 0x9a6fdf, baseR: 0.65 },
    { cls: 'Utility', n: 22, color: 0xbce2e7, baseR: 0.85 },
  ];

  const seed = (k) => { let x = Math.sin(k * 9301 + 49297) * 233280; return x - Math.floor(x); };
  const points = [];

  groups.forEach((g, gi) => {
    for (let i = 0; i < g.n; i++) {
      const idx = i + gi * 100;
      // mostly evenly spread in angle, slight jitter; radius sampled with hyperbolic-style stretch
      const ang = (i / g.n) * Math.PI * 2 + seed(idx) * 0.1;
      const radial = g.baseR + (seed(idx + 7) - 0.5) * 0.06;
      // Map euclidean radial to Poincaré radial (just normalised here): place at radial * R within the disk
      const r = Math.min(0.96, radial) * R;
      points.push({ x: Math.cos(ang) * r, y: Math.sin(ang) * r, color: g.color, cls: g.cls });
    }
  });

  // Connect Legendary->everything as faint links to suggest hierarchy
  const center = points.slice(0, 2);
  const linkMat = new THREE.LineBasicMaterial({ color: rings, transparent: true, opacity: 0.18 });
  const linkGeo = new THREE.BufferGeometry();
  const linkPos = [];
  points.slice(2).forEach((p, i) => {
    if (i % 3 !== 0) return;
    const c = center[i % 2];
    linkPos.push(c.x, c.y, 0, p.x, p.y, 0);
  });
  linkGeo.setAttribute('position', new THREE.Float32BufferAttribute(linkPos, 3));
  scene.add(new THREE.LineSegments(linkGeo, linkMat));

  // Draw points as Three.js Points
  const sphereGeo = new THREE.CircleGeometry(1, 18);
  points.forEach((p) => {
    const mat = new THREE.MeshBasicMaterial({ color: p.color });
    const m = new THREE.Mesh(sphereGeo, mat);
    // points farther from center get smaller (hyperbolic visual)
    const dist = Math.hypot(p.x, p.y) / R;
    const size = Math.max(2.4, 7 - dist * 6);
    m.scale.setScalar(size);
    m.position.set(p.x, p.y, 1);
    scene.add(m);
  });

  // Boundary glow ring
  const boundary = new THREE.Mesh(
    new THREE.RingGeometry(R - 1, R + 1, 256),
    new THREE.MeshBasicMaterial({ color: 0x7C3AED, transparent: true, opacity: 0.55 })
  );
  scene.add(boundary);

  // Labels via DOM overlay? Skip: keep it clean.
  let t = 0;
  function animate() {
    t += 0.0025;
    scene.rotation.z = Math.sin(t) * 0.04;
    renderer.render(scene, camera);
    animationId = requestAnimationFrame(animate);
  }
  animate();
}

// resize handler for canvas
let resizeT;
window.addEventListener('resize', () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(drawPoincare, 120);
});

// ---------- Init ----------
function init() {
  fillSourceLinks();
  renderPillars();
  renderNatsTable();
  renderMof();
  renderTaxonomy();
  renderEvolution();
  renderSkills();
  renderTour();
  renderCoverage();
  renderBusGraph();
  drawPoincare();
  setupNav();
  // refill source links inside dynamically rendered cards
  fillSourceLinks();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// =============================================================================
// TOKENOMICS LAYER
// All charts read from the constants in data.js. SVG via D3, no external deps.
// Colors are pulled from CSS custom properties so theme-toggle re-renders them.
// =============================================================================

// Stable color assignment for the four business archetypes.
// We use accent (amber) for the strongest performer, then teal variants;
// cool palette to avoid red/green confusion and meet the colorblind target.
const TOKE_COLORS = {
  'AI-Enhanced Local Service Business': '#0D9488', // accent
  'Sustainable Energy AI Consulting':   '#7C3AED', // primary teal
  'Community Token Pre-Order System':   '#9a6fdf', // purple
  'Creative Content + Token Rewards':   '#c47a8a', // mauve — legible in both themes, distinct from the teal/purple/amber trio
};
const TOKE_SHORT = {
  'AI-Enhanced Local Service Business': 'AI Local Service',
  'Sustainable Energy AI Consulting':   'Sustainable Energy',
  'Community Token Pre-Order System':   'Community Pre-Order',
  'Creative Content + Token Rewards':   'Creative + Tokens',
};

const fmtUSD = (v) => {
  if (Math.abs(v) >= 1e9) return '$' + (v / 1e9).toFixed(1) + 'B';
  if (Math.abs(v) >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return '$' + (v / 1e3).toFixed(0) + 'K';
  return '$' + Math.round(v).toLocaleString();
};
const fmtCount = (v) => {
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(1) + 'M';
  if (Math.abs(v) >= 1e3) return (v / 1e3).toFixed(1) + 'K';
  return Math.round(v).toLocaleString();
};

function renderTokenomicsKpis() {
  // Roll-ups grounded in the constants above
  const totalCumProfit2029 = TOKENOMICS_PROJECTIONS.reduce((s, p) => s + p.cumulative[4], 0);
  const totalInvest = TOKENOMICS_PROJECTIONS.reduce((s, p) => s + p.investment, 0);
  const moderateImpact = COMMUNITY_IMPACT[1].totalImpact;
  const fastestBreakeven = Math.min(...BREAKEVEN.map(b => b.optimistic));
  const fastestModel = BREAKEVEN.find(b => b.optimistic === fastestBreakeven);
  const items = [
    { label: '5Y cumul. profit', value: fmtUSD(totalCumProfit2029), small: 'four archetypes' },
    { label: 'Capital required', value: fmtUSD(totalInvest), small: 'to seed all four' },
    { label: 'Fastest breakeven', value: fastestBreakeven.toFixed(1) + ' mo', small: fastestModel.model },
    { label: 'Community impact', value: fmtUSD(moderateImpact), small: '@ 25% participation' },
  ];
  $('#toke-kpis').innerHTML = items.map(i => `
    <div class="kpi"><div class="label">${i.label}</div><div class="value">${i.value}<small>${i.small}</small></div></div>`).join('');
}

// ---- Cumulative profit (line chart with success-prob band) ----
function renderTokeCumulative() {
  const svg = d3.select('#toke-cumulative').classed('toke-chart', true);
  svg.selectAll('*').remove();
  const W = 1200, H = 460, m = { t: 24, r: 170, b: 44, l: 72 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);

  const x = d3.scaleLinear().domain([2025, 2029]).range([0, iw]);
  const yMax = d3.max(TOKENOMICS_PROJECTIONS, p => p.cumulative[4]);
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([ih, 0]);

  // grid + axes
  g.append('g').attr('class', 'grid')
    .call(d3.axisLeft(y).tickSize(-iw).tickFormat('').ticks(6));
  g.append('g').attr('class', 'axis').attr('transform', `translate(0,${ih})`)
    .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format('d')));
  g.append('g').attr('class', 'axis')
    .call(d3.axisLeft(y).ticks(6).tickFormat(d => fmtUSD(d)));
  g.append('text').attr('class','axis-title').attr('x', -8).attr('y', -10).attr('text-anchor','start')
    .text('Cumulative net profit (USD, nominal)');

  const line = d3.line()
    .x((_, i) => x(2025 + i))
    .y(v => y(v))
    .curve(d3.curveMonotoneX);

  // For each model: dashed envelope (cum × successProb to cum) + solid line
  TOKENOMICS_PROJECTIONS.forEach((p) => {
    const color = TOKE_COLORS[p.model];
    const lo = p.cumulative.map(v => v * p.successProb);
    const hi = p.cumulative;
    const area = d3.area()
      .x((_, i) => x(2025 + i))
      .y0((_, i) => y(lo[i]))
      .y1((_, i) => y(hi[i]))
      .curve(d3.curveMonotoneX);
    g.append('path').attr('class','series-band')
      .attr('d', area(lo)).attr('fill', color);
    g.append('path').attr('class','series-line')
      .attr('d', line(lo)).attr('stroke', color)
      .attr('stroke-dasharray','3 4').attr('opacity', .55).attr('stroke-width', 1.2);
    g.append('path').attr('class','series-line')
      .attr('d', line(hi)).attr('stroke', color);
    g.selectAll(null).data(hi).enter().append('circle')
      .attr('class','series-dot').attr('r', 3.5)
      .attr('cx', (_, i) => x(2025 + i)).attr('cy', d => y(d)).attr('fill', color);
  });

  // De-collide end labels by sorting endpoints and reflowing y-positions.
  const labelData = TOKENOMICS_PROJECTIONS.map(p => ({
    color: TOKE_COLORS[p.model],
    label: `${TOKE_SHORT[p.model]} · ${fmtUSD(p.cumulative[4])}`,
    sub: `p(success) = ${(p.successProb * 100).toFixed(0)}%`,
    yReal: y(p.cumulative[4]),
  })).sort((a, b) => a.yReal - b.yReal);
  const minGap = 32; // pixels between two stacked labels
  for (let i = 1; i < labelData.length; i++) {
    if (labelData[i].yReal - labelData[i-1].yReal < minGap) {
      labelData[i].yReal = labelData[i-1].yReal + minGap;
    }
  }
  labelData.forEach((d) => {
    g.append('text').attr('class','end-label')
      .attr('x', x(2029) + 10).attr('y', d.yReal + 4)
      .attr('fill', d.color).text(d.label);
    g.append('text').attr('class','axis-label')
      .attr('x', x(2029) + 10).attr('y', d.yReal + 18)
      .text(d.sub);
  });

  // legend
  $('#toke-cum-legend').innerHTML = TOKENOMICS_PROJECTIONS.map(p =>
    `<span style="color:${TOKE_COLORS[p.model]}">${TOKE_SHORT[p.model]}</span>`).join('');
}

// ---- Breakeven range bars ----
function renderTokeBreakeven() {
  const svg = d3.select('#toke-breakeven').classed('toke-chart', true);
  svg.selectAll('*').remove();
  const W = 600, H = 320, m = { t: 24, r: 24, b: 40, l: 200 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);

  const xMax = d3.max(BREAKEVEN, b => b.conservative);
  const x = d3.scaleLinear().domain([0, xMax]).nice().range([0, iw]);
  const y = d3.scaleBand().domain(BREAKEVEN.map(b => b.model)).range([0, ih]).padding(0.35);

  g.append('g').attr('class','grid')
    .attr('transform', `translate(0,${ih})`)
    .call(d3.axisBottom(x).tickSize(-ih).tickFormat('').ticks(6));
  g.append('g').attr('class','axis').attr('transform', `translate(0,${ih})`)
    .call(d3.axisBottom(x).ticks(6).tickFormat(d => d + ' mo'));

  BREAKEVEN.forEach((b) => {
    const yc = y(b.model) + y.bandwidth() / 2;
    const color = '#7C3AED';
    // background track (full chart width)
    g.append('line').attr('class','range-track')
      .attr('x1', 0).attr('x2', iw).attr('y1', yc).attr('y2', yc);
    // colored fill from optimistic → conservative
    g.append('line').attr('class','range-fill')
      .attr('x1', x(b.optimistic)).attr('x2', x(b.conservative))
      .attr('y1', yc).attr('y2', yc)
      .attr('stroke', color).attr('opacity', 0.45);
    // realistic marker
    g.append('circle').attr('class','range-marker')
      .attr('cx', x(b.realistic)).attr('cy', yc).attr('r', 5)
      .attr('fill', '#0D9488');

    // labels
    g.append('text').attr('class','row-label')
      .attr('x', -10).attr('y', yc - 4).attr('text-anchor','end')
      .text(b.model);
    g.append('text').attr('class','row-meta')
      .attr('x', -10).attr('y', yc + 10).attr('text-anchor','end')
      .text(`invest ${fmtUSD(b.investment)} · p=${(b.p*100).toFixed(0)}%`);

    // realistic value at point
    g.append('text').attr('class','axis-label')
      .attr('x', x(b.realistic)).attr('y', yc - 10).attr('text-anchor','middle')
      .attr('fill', '#0D9488')
      .text(b.realistic.toFixed(1));
  });

  // sub-legend at top right
  g.append('text').attr('class','axis-label').attr('x', iw).attr('y', -8).attr('text-anchor','end')
    .text('● realistic (amber) · | range = optimistic→conservative');
}

// ---- Scenario expected-value (small multiples horizontal bars per model) ----
function renderTokeScenarios() {
  const svg = d3.select('#toke-scenarios').classed('toke-chart', true);
  svg.selectAll('*').remove();
  const W = 600, H = 320, m = { t: 12, r: 12, b: 18, l: 12 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);

  const cellW = iw / 2, cellH = ih / 2;
  const padX = 10, padY = 36;
  const allEv = SCENARIOS.flatMap(s => s.rows.map(r => r.ev));
  const xMax = d3.max(allEv);

  const scenColors = ['#6daa45', '#7C3AED', '#0D9488', '#c47a8a']; // bull → crypto-winter
  const scenShort  = ['Bull mkt', 'Normal',   'Downturn', 'Crypto wntr'];

  SCENARIOS.forEach((s, idx) => {
    const cx = (idx % 2) * cellW;
    const cy = Math.floor(idx / 2) * cellH;
    const cell = g.append('g').attr('transform', `translate(${cx},${cy})`);
    cell.append('text').attr('class','row-label').attr('x', padX).attr('y', 14)
      .text(s.model);
    cell.append('text').attr('class','row-meta').attr('x', padX).attr('y', 28)
      .text(`invest ${fmtUSD(s.investment)} · Σ EV = ${s.rows.reduce((a,r)=>a+r.ev,0).toFixed(0)}× ROI`);

    const innerH = cellH - padY - 6;
    const rowGap = 5;
    const barH = (innerH - rowGap * (s.rows.length - 1)) / s.rows.length;
    const labelW = 78;
    const x = d3.scaleLinear().domain([0, xMax]).range([0, cellW - labelW - 50]);

    s.rows.forEach((r, i) => {
      const yy = padY + i * (barH + rowGap);
      cell.append('rect')
        .attr('x', labelW).attr('y', yy)
        .attr('width', Math.max(1, x(r.ev))).attr('height', barH)
        .attr('fill', scenColors[i]).attr('rx', 2);
      cell.append('text').attr('class','axis-label')
        .attr('x', labelW - 6).attr('y', yy + barH * 0.7).attr('text-anchor','end')
        .text(scenShort[i]);
      cell.append('text').attr('class','axis-label')
        .attr('x', labelW + x(r.ev) + 4).attr('y', yy + barH * 0.7)
        .attr('fill', scenColors[i]).style('font-weight', 600)
        .text(r.ev.toFixed(0));
    });
  });
}

// ---- Container ROI vs scale ----
function renderTokeContainers() {
  const svg = d3.select('#toke-containers').classed('toke-chart', true);
  svg.selectAll('*').remove();
  const W = 1200, H = 380, m = { t: 24, r: 250, b: 44, l: 64 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const g = svg.append('g').attr('transform', `translate(${m.l},${m.t})`);

  const scales = [1, 3, 5, 10];
  const x = d3.scaleLog().domain([1, 10]).range([0, iw]);
  const yMax = d3.max(CONTAINER_SCALING, c => c.roi[3]);
  const y = d3.scaleLinear().domain([0, yMax]).nice().range([ih, 0]);

  g.append('g').attr('class','grid')
    .call(d3.axisLeft(y).tickSize(-iw).tickFormat('').ticks(6));
  g.append('g').attr('class','axis').attr('transform', `translate(0,${ih})`)
    .call(d3.axisBottom(x).tickValues(scales).tickFormat(d => d + '×'));
  g.append('g').attr('class','axis')
    .call(d3.axisLeft(y).ticks(6).tickFormat(d => d + '%'));
  g.append('text').attr('class','axis-title').attr('x', -8).attr('y', -10).attr('text-anchor','start')
    .text('ROI (year 1, %) — higher is better');
  g.append('text').attr('class','axis-title').attr('x', iw/2).attr('y', ih + 36).attr('text-anchor','middle')
    .text('Replication scale (containers)');

  const containerColors = ['#0D9488', '#7C3AED', '#9a6fdf', '#6daa45', '#c47a8a'];
  const line = d3.line()
    .x((_, i) => x(scales[i]))
    .y(v => y(v))
    .curve(d3.curveMonotoneX);

  CONTAINER_SCALING.forEach((c, idx) => {
    const color = containerColors[idx % containerColors.length];
    g.append('path').attr('class','series-line')
      .attr('d', line(c.roi)).attr('stroke', color);
    c.roi.forEach((v, i) => {
      g.append('circle').attr('class','series-dot').attr('r', 4)
        .attr('cx', x(scales[i])).attr('cy', y(v)).attr('fill', color);
    });
  });

  // De-collide end labels for container lines (same algorithm as cumulative).
  const cLabels = CONTAINER_SCALING.map((c, i) => ({
    color: containerColors[i % containerColors.length],
    label: c.container,
    sub: `10× → ${c.roi[3].toFixed(0)}% ROI · payback ${c.payback[3].toFixed(1)} mo`,
    yReal: y(c.roi[3]),
  })).sort((a, b) => a.yReal - b.yReal);
  const minGapC = 30;
  for (let i = 1; i < cLabels.length; i++) {
    if (cLabels[i].yReal - cLabels[i-1].yReal < minGapC) {
      cLabels[i].yReal = cLabels[i-1].yReal + minGapC;
    }
  }
  cLabels.forEach((d) => {
    g.append('text').attr('class','end-label')
      .attr('x', x(10) + 10).attr('y', d.yReal + 4)
      .attr('fill', d.color).text(d.label);
    g.append('text').attr('class','axis-label')
      .attr('x', x(10) + 10).attr('y', d.yReal + 17)
      .text(d.sub);
  });

  // legend
  $('#toke-container-legend').innerHTML = CONTAINER_SCALING.map((c, i) =>
    `<span style="color:${containerColors[i]}">${c.container}</span>`).join('');
}

// ---- Community / link / phase tables ----
function renderTokeTables() {
  $('#toke-community-table tbody').innerHTML = COMMUNITY_IMPACT.map(s => `
    <tr>
      <td><b>${s.scenario}</b></td>
      <td class="num">${s.participants.toLocaleString()}</td>
      <td class="num">${fmtUSD(s.totalInvest)}</td>
      <td class="num">${fmtUSD(s.incomeIncrease)}</td>
      <td class="num">${s.multiplier.toFixed(2)}×</td>
      <td class="num">${fmtUSD(s.totalImpact)}</td>
      <td class="num">${s.communityROI.toFixed(0)}%</td>
    </tr>`).join('');

  $('#toke-link-table tbody').innerHTML = CHIT_TOKENOMICS_LINK.map(l => `
    <tr>
      <td><b>${l.primitive}</b></td>
      <td>${l.chitRole}</td>
      <td><span class="mono">${l.agent}</span></td>
    </tr>`).join('');

  $('#toke-phases-table tbody').innerHTML = ROLLOUT_PHASES.map(p => `
    <tr>
      <td><b>${p.phase}</b></td>
      <td><span class="mono">${p.container}</span></td>
      <td class="num">${fmtUSD(p.invest)}</td>
      <td class="num">${fmtUSD(p.cumulative)}</td>
      <td class="num">${p.residents.toLocaleString()}</td>
    </tr>`).join('');
}

function renderTokenomics() {
  if (!document.getElementById('tokenomics')) return;
  renderTokenomicsKpis();
  renderTokeCumulative();
  renderTokeBreakeven();
  renderTokeScenarios();
  renderTokeContainers();
  renderTokeTables();
}

// Run tokenomics after the original init pipeline. The original `init()` is
// scheduled higher up in this file (either on DOMContentLoaded or immediately
// if the document is already parsed). Either way, scheduling these on
// DOMContentLoaded is a no-op when DOM is ready, and a queued listener when
// it isn't — both safely run *after* the original init.
function __runTokenomics() {
  renderTokenomics();
  fillSourceLinks();
}
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', __runTokenomics);
} else {
  __runTokenomics();
}

// re-render charts on resize so the SVGs reflow viewport correctly
let __tokeResizeT;
window.addEventListener('resize', () => {
  clearTimeout(__tokeResizeT);
  __tokeResizeT = setTimeout(renderTokenomics, 150);
});
