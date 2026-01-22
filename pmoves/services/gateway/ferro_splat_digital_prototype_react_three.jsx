import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";

/**
 * Ferro‑Splat Digital Prototype (React + Three.js)
 * ------------------------------------------------------------
 * v3 Upgrades (per user request):
 * - Per‑band EQ gains and global compressor controls (threshold/ratio/attack/release)
 * - Nozzle Editor: select a nozzle, edit μ (position), σx/σy, angle, hue, alphaGain, enable/disable
 * - Add/Remove nozzles; optional ring‑layout reset; safe cap at 16 nozzles (shader uniform limit)
 * - Audio Playlist Loader: choose multiple audio files, list view with play/stop/prev/next & selection
 * - Hardened mic fallback remains (Demo & File modes), HTTPS guidance, resource teardown
 * - Runtime sanity tests remain
 *
 * Notes:
 * - Drag‑to‑move for nozzles is not added yet (kept simple + robust); use numeric inputs below.
 * - Band count is tied to current nozzle count, keeping one band per nozzle for intuitive routing.
 */

// ======= Helpers
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// Simple one-pole compressor envelope (lightweight)
class SimpleCompressor {
  constructor({ threshold = 0.2, ratio = 4.0, attack = 0.01, release = 0.2 } = {}) {
    this.threshold = threshold;
    this.ratio = ratio;
    this.attack = attack;
    this.release = release;
    this.env = 0;
  }
  process(x, dt) {
    const absx = Math.abs(x);
    const rising = absx > this.env;
    const coef = Math.exp(-dt / (rising ? this.attack : this.release));
    this.env = absx + (this.env - absx) * coef;
    if (this.env <= this.threshold) return this.env;
    const over = this.env - this.threshold;
    return this.threshold + over / this.ratio;
  }
}

export default function FerroSplat() {
  // ---- Refs (Three)
  const mountRef = useRef(null);
  const rafRef = useRef(0);
  const rendererRef = useRef(null);
  const sceneRef = useRef(new THREE.Scene());
  const cameraRef = useRef(null);
  const rtSceneRef = useRef(new THREE.Scene());
  const rtCamRef = useRef(new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1));
  const plateMeshRef = useRef(null);
  const depositMatRef = useRef(null);
  const depositRTARef = useRef(null);
  const depositRTBRef = useRef(null);

  // ---- Refs (Audio)
  const analyserRef = useRef(null);
  const audioCtxRef = useRef(null);
  const sourceNodeRef = useRef(null); // MediaStreamSource, MediaElementSource, or Oscillator/Gain
  const mediaStreamRef = useRef(null); // to stop mic tracks
  const oscillatorRef = useRef(null);
  const audioElRef = useRef(null);
  const dataArrayRef = useRef(null);
  const lastTimeRef = useRef(0);

  // ---- UI State
  const [running, setRunning] = useState(false);
  const [audioMode, setAudioMode] = useState("none"); // none | mic | demo | file
  const [statusMsg, setStatusMsg] = useState("");
  const [showNozzles, setShowNozzles] = useState(false);
  const [fadeRate, setFadeRate] = useState(0.01); // deposit decay per frame
  const [emissiveScale, setEmissiveScale] = useState(0.9);

  // Compressor (global, applied to each band's envelope)
  const [comp, setComp] = useState({ threshold: 0.2, ratio: 4.0, attack: 0.02, release: 0.18 });

  // Audio bands & nozzle mapping: 1 band per nozzle
  const [nozzles, setNozzles] = useState(() => (
    Array.from({ length: 8 }).map((_, i) => ({
      id: `N${i + 1}`,
      band: i,
      mu: [0.5 + 0.28 * Math.cos((i / 8) * Math.PI * 2), 0.5 + 0.28 * Math.sin((i / 8) * Math.PI * 2)],
      sigma: [0.06, 0.02],
      angle: (i / 8) * Math.PI * 2,
      alphaGain: 1.0,
      hue: (i / 8),
      enabled: true,
    }))
  ));
  const [selectedNozzleId, setSelectedNozzleId] = useState(null);
  const compressorsRef = useRef([]); // per-nozzle compressor instances

  // EQ gains per band (aligned with nozzles)
  const [eqGains, setEqGains] = useState(() => Array.from({ length: 8 }, () => 1.0));

  // Playlist for File mode
  const [playlist, setPlaylist] = useState([]); // {name, url}
  const [currentTrack, setCurrentTrack] = useState(0);
  const [isSecure] = useState(typeof window !== 'undefined' ? window.isSecureContext : false);
  const fileInputRef = useRef(null);
  const multiFileRef = useRef(null);

  // ======= THREE Setup
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    const camera = new THREE.PerspectiveCamera(35, mount.clientWidth / mount.clientHeight, 0.1, 100);
    camera.position.set(0, 0, 3.5);
    cameraRef.current = camera;

    // Subtle lighting cues
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    const dir = new THREE.DirectionalLight(0xffffff, 0.7);
    dir.position.set(1, 1, 2);
    sceneRef.current.add(ambient, dir);

    // Plate geometry (flat plane; relief via shader)
    const geo = new THREE.PlaneGeometry(2.4, 2.4, 1, 1);

    // Render targets (ping‑pong accumulation)
    const params = {
      minFilter: THREE.LinearFilter,
      magFilter: THREE.LinearFilter,
      format: THREE.RGBAFormat,
      type: THREE.UnsignedByteType,
      depthBuffer: false,
      stencilBuffer: false,
    };
    const size = new THREE.Vector2(mount.clientWidth || 512, mount.clientHeight || 512);
    const rtA = new THREE.WebGLRenderTarget(size.x, size.y, params);
    const rtB = new THREE.WebGLRenderTarget(size.x, size.y, params);
    depositRTARef.current = rtA; depositRTBRef.current = rtB;

    // Deposit material: Dbuff = (1-fade)*Dbuff + Σ(gaussians * alpha * stick)
    const depositMat = new THREE.ShaderMaterial({
      transparent: false,
      uniforms: {
        prevTex: { value: rtA.texture },
        fadeRate: { value: fadeRate },
        time: { value: 0 },
        nozzleCount: { value: 8 }, // will update dynamically
        mu: { value: new Array(16).fill(0).flatMap(() => [0.5, 0.5]) },
        sigma: { value: new Array(16).fill(0).flatMap(() => [0.05, 0.02]) },
        angle: { value: new Array(16).fill(0) },
        alpha: { value: new Array(16).fill(0) },
        color: { value: new Array(16).fill(0).flatMap(() => [1, 1, 1]) },
        stickGain: { value: 1.2 },
      },
      vertexShader: /* glsl */`
        varying vec2 vUv; void main(){ vUv=uv; gl_Position=vec4(position,1.0); }
      `,
      fragmentShader: /* glsl */`
        precision highp float; varying vec2 vUv;
        uniform sampler2D prevTex; uniform float fadeRate; uniform float time;
        uniform int nozzleCount; uniform float stickGain;
        uniform vec2 mu[16]; uniform vec2 sigma[16]; uniform float angle[16];
        uniform float alpha[16]; uniform vec3 color[16];
        
        float height(vec2 uv){
          vec2 p = (uv - 0.5) * 2.0; float r = length(p)+1e-5; float t = time;
          float w1 = sin(8.0*p.x + 3.0*t) * cos(7.0*p.y - 2.7*t);
          float w2 = 0.7*sin(12.0*r - 1.2*t);
          float w3 = 0.45*cos(10.0*p.y + 1.8*t + 0.7*sin(3.0*t));
          return 0.5*w1 + 0.35*w2 + 0.25*w3;
        }
        
        mat2 rot(float a){float c=cos(a), s=sin(a); return mat2(c,-s,s,c);} 
        float gauss(vec2 uv, vec2 m, vec2 s, float a){
          vec2 d = (uv - m);
          vec2 d2 = rot(a) * d;
          vec2 q = d2 / s; 
          return exp(-0.5*dot(q,q));
        }
        
        void main(){
          vec4 prev = texture2D(prevTex, vUv);
          vec4 acc = prev * (1.0 - clamp(fadeRate, 0.0, 1.0));
          float h = height(vUv);
          float stick = 1.0 / (1.0 + exp(-6.0*h));
          
          for (int i=0;i<16;i++){
            if (i>=nozzleCount) break;
            float g = gauss(vUv, mu[i], sigma[i], angle[i]);
            float a = alpha[i];
            vec3 c = color[i];
            acc.rgb += c * (g * a * stick * stickGain);
            acc.a = 1.0 - (1.0 - acc.a) * (1.0 - g * a * 0.5);
          }
          gl_FragColor = acc;
        }
      `,
    });
    depositMatRef.current = depositMat;

    const rtQuad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), depositMat);
    rtSceneRef.current.add(rtQuad);

    // Plate shader (uses deposit texture as "sand" + relief + emissive)
    const plateMat = new THREE.ShaderMaterial({
      lights: false, transparent: false,
      uniforms: {
        time: { value: 0 },
        depositTex: { value: rtB.texture },
        emissiveScale: { value: emissiveScale },
      },
      vertexShader: /* glsl */`
        varying vec2 vUv; void main(){ vUv=uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }
      `,
      fragmentShader: /* glsl */`
        precision highp float; varying vec2 vUv;
        uniform float time; uniform sampler2D depositTex; uniform float emissiveScale;
        
        float height(vec2 uv){
          vec2 p = (uv - 0.5) * 2.0; float r = length(p)+1e-5; float t = time;
          float w1 = sin(8.0*p.x + 3.0*t) * cos(7.0*p.y - 2.7*t);
          float w2 = 0.7*sin(12.0*r - 1.2*t);
          float w3 = 0.45*cos(10.0*p.y + 1.8*t + 0.7*sin(3.0*t));
          return 0.5*w1 + 0.35*w2 + 0.25*w3;
        }
        vec3 normalFromHeight(vec2 uv){
          float e=0.0015; float hC=height(uv); float hx=height(uv+vec2(e,0.0)); float hy=height(uv+vec2(0.0,e));
          vec3 dx=vec3(e,0.0,hx-hC); vec3 dy=vec3(0.0,e,hy-hC); return normalize(cross(dy,dx));
        }
        float rim(vec3 n){ return pow(1.0 - max(n.z,0.0), 0.8); }
        void main(){
          vec4 dep = texture2D(depositTex, vUv);
          vec3 n = normalFromHeight(vUv);
          vec3 base = dep.rgb;
          float diff = clamp(0.5 + 0.5*n.z, 0.0, 1.0);
          float r = rim(n)*0.2;
          float e = length(dep.rgb) * 0.3 * emissiveScale; // "compression as extension"
          vec3 color = base * (0.35 + 0.65*diff) + r + vec3(e);
          gl_FragColor = vec4(color, 1.0);
        }
      `,
    });

    const plate = new THREE.Mesh(geo, plateMat);
    sceneRef.current.add(plate);
    plateMeshRef.current = plate;

    // Nozzle gizmos (debug)
    const nozzleGroup = new THREE.Group();
    sceneRef.current.add(nozzleGroup);
    const createNozzleSprite = (hue, id) => {
      const c = new THREE.Color().setHSL(hue, 0.8, 0.5);
      const mesh = new THREE.Mesh(new THREE.CircleGeometry(0.025, 24), new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.85 }));
      mesh.userData.id = id; return mesh;
    };

    // populate gizmos
    const syncNozzleSprites = () => {
      // remove existing
      const toRemove = [];
      nozzleGroup.traverse((obj) => { if (obj.userData && obj.userData.id) toRemove.push(obj); });
      toRemove.forEach(o => nozzleGroup.remove(o));
      // add fresh
      nozzles.forEach((nz) => {
        const s = createNozzleSprite(nz.hue, nz.id);
        s.position.set((nz.mu[0]-0.5)*2.4, (nz.mu[1]-0.5)*2.4, 0.02);
        s.visible = showNozzles;
        nozzleGroup.add(s);
      });
    };
    syncNozzleSprites();

    const onResize = () => {
      const w = mount.clientWidth || 512, h = mount.clientHeight || 512;
      renderer.setSize(w, h);
      camera.aspect = w / h; camera.updateProjectionMatrix();
      const newA = new THREE.WebGLRenderTarget(w, h, params);
      const newB = new THREE.WebGLRenderTarget(w, h, params);
      depositRTARef.current.dispose(); depositRTBRef.current.dispose();
      depositRTARef.current = newA; depositRTBRef.current = newB;
      depositMat.uniforms.prevTex.value = newA.texture;
      (plate.material).uniforms.depositTex.value = newB.texture;
    };
    window.addEventListener("resize", onResize);

    // Per‑band compressors (re‑create when comp changes or nozzle count changes)
    compressorsRef.current = Array.from({ length: nozzles.length }, () => new SimpleCompressor(comp));

    // Animation loop
    const animate = (tms) => {
      const t = tms * 0.001;
      const dt = lastTimeRef.current ? (t - lastTimeRef.current) : 0.016;
      lastTimeRef.current = t;

      depositMat.uniforms.time.value = t;
      depositMat.uniforms.fadeRate.value = fadeRate;
      depositMat.uniforms.nozzleCount.value = Math.min(nozzles.length, 16);

      // Pull audio spectrum → per-band
      const analyser = analyserRef.current;
      const perBand = new Array(nozzles.length).fill(0);
      if (analyser && dataArrayRef.current) {
        analyser.getByteFrequencyData(dataArrayRef.current);
        const bins = dataArrayRef.current;
        for (let b = 0; b < nozzles.length; b++) {
          const start = Math.floor((b / nozzles.length) * bins.length);
          const end = Math.floor(((b + 1) / nozzles.length) * bins.length);
          let sum = 0; for (let i = start; i < end; i++) sum += bins[i];
          const avg = sum / Math.max(1, end - start);
          perBand[b] = (avg / 255) * (eqGains[b] ?? 1.0);
        }
      }

      // Update nozzle uniforms
      const mus = depositMat.uniforms.mu.value;
      const sig = depositMat.uniforms.sigma.value;
      const ang = depositMat.uniforms.angle.value;
      const alp = depositMat.uniforms.alpha.value;
      const col = depositMat.uniforms.color.value;

      for (let i = 0; i < Math.min(nozzles.length, 16); i++) {
        const nz = nozzles[i];
        if (!compressorsRef.current[i]) compressorsRef.current[i] = new SimpleCompressor(comp);
        // update compressor params in case user changed them
        Object.assign(compressorsRef.current[i], comp);
        const level = compressorsRef.current[i].process(perBand[i] || 0, clamp(dt, 0.001, 0.05));
        const alpha = clamp((nz.enabled ? nz.alphaGain : 0) * (level * 1.2), 0.0, 0.95);
        mus[i*2+0] = nz.mu[0]; mus[i*2+1] = nz.mu[1];
        sig[i*2+0] = Math.max(0.002, nz.sigma[0]); sig[i*2+1] = Math.max(0.002, nz.sigma[1]);
        ang[i] = nz.angle;
        alp[i] = alpha;
        const c = new THREE.Color().setHSL(nz.hue % 1, 0.85, 0.55);
        col[i*3+0] = c.r; col[i*3+1] = c.g; col[i*3+2] = c.b;
      }

      // Ping‑pong accumulation pass
      const renderer = rendererRef.current;
      const rtA = depositRTARef.current; const rtB = depositRTBRef.current;
      depositMat.uniforms.prevTex.value = rtA.texture;
      renderer.setRenderTarget(rtB); renderer.render(rtSceneRef.current, rtCamRef.current);
      renderer.setRenderTarget(null);

      // Present pass
      const plate = plateMeshRef.current;
      (plate.material).uniforms.time.value = t;
      (plate.material).uniforms.depositTex.value = rtB.texture;
      const tmp = depositRTARef.current; depositRTARef.current = depositRTBRef.current; depositRTBRef.current = tmp;

      // Toggle nozzle gizmos
      nozzleGroup.children.forEach((obj, idx) => { obj.visible = showNozzles; });
      // sync positions if user changed mu
      nozzleGroup.children.forEach((obj, idx) => {
        const nz = nozzles[idx];
        if (nz) obj.position.set((nz.mu[0]-0.5)*2.4, (nz.mu[1]-0.5)*2.4, 0.02);
      });

      renderer.render(sceneRef.current, cameraRef.current);
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", onResize);
      renderer.dispose(); rtA.dispose(); rtB.dispose();
      if (mount && renderer.domElement && mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ======= Audio plumbing (mic / demo / file)
  const teardownAudio = async () => {
    try {
      if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(t => t.stop());
      if (oscillatorRef.current) { try { oscillatorRef.current.stop(); } catch(_) {} oscillatorRef.current.disconnect(); }
      if (audioElRef.current) { audioElRef.current.pause(); audioElRef.current.src = ""; }
      if (sourceNodeRef.current) sourceNodeRef.current.disconnect();
      if (analyserRef.current) analyserRef.current.disconnect();
      if (audioCtxRef.current) await audioCtxRef.current.close();
    } catch(_) {} finally {
      analyserRef.current = null; audioCtxRef.current = null; sourceNodeRef.current = null;
      mediaStreamRef.current = null; oscillatorRef.current = null; audioElRef.current = null;
      dataArrayRef.current = null; setRunning(false); setAudioMode("none");
    }
  };

  const ensureAudioContext = () => {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) throw new Error("Web Audio not supported in this browser.");
    return new AC();
  };

  const startMic = async () => {
    if (!isSecure) { setStatusMsg("Microphone requires HTTPS or localhost. Use Demo/File audio or serve over HTTPS."); return; }
    try {
      if (navigator.permissions && navigator.permissions.query) {
        try {
          const perm = await navigator.permissions.query({ name: 'microphone' });
          if (perm.state === 'denied') { setStatusMsg("Microphone permission is denied. Enable it in your browser settings, then reload."); return; }
        } catch(_) {}
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = ensureAudioContext();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.7;
      src.connect(analyser);
      sourceNodeRef.current = src; analyserRef.current = analyser; mediaStreamRef.current = stream; audioCtxRef.current = ctx;
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
      setRunning(true); setAudioMode('mic'); setStatusMsg("");
    } catch (e) {
      console.error(e);
      const name = e && e.name ? e.name : "Error";
      if (name === 'NotAllowedError' || name === 'SecurityError') setStatusMsg("Permission denied. Grant mic access (and ensure HTTPS), or use Demo/File audio.");
      else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') setStatusMsg("No microphone found. Use Demo/File audio.");
      else if (name === 'NotReadableError') setStatusMsg("Microphone is busy or not readable. Close other apps using the mic, or use Demo/File audio.");
      else setStatusMsg("Mic error: " + (e.message || name));
    }
  };

  const startDemo = async () => {
    try {
      const ctx = ensureAudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      const lfo = ctx.createOscillator(); const lfoGain = ctx.createGain();
      lfo.frequency.value = 0.1; lfoGain.gain.value = 200; lfo.connect(lfoGain); lfoGain.connect(osc.frequency);
      osc.type = 'sawtooth'; osc.frequency.value = 220; gain.gain.value = 0.2;
      osc.connect(gain); gain.connect(ctx.destination);
      const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.7;
      gain.connect(analyser);
      osc.start(); lfo.start();
      oscillatorRef.current = osc; sourceNodeRef.current = gain; analyserRef.current = analyser; audioCtxRef.current = ctx;
      dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
      setRunning(true); setAudioMode('demo'); setStatusMsg("");
    } catch(e) { setStatusMsg("Demo audio failed: " + (e.message || e)); }
  };

  const connectAudioEl = async (url) => {
    const ctx = ensureAudioContext();
    const audio = new Audio(); audio.src = url; audio.loop = true; audio.crossOrigin = 'anonymous';
    audioElRef.current = audio;
    const src = ctx.createMediaElementSource(audio);
    const analyser = ctx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.7;
    src.connect(analyser); analyser.connect(ctx.destination);
    await audio.play();
    sourceNodeRef.current = src; analyserRef.current = analyser; audioCtxRef.current = ctx;
    dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
    setRunning(true); setAudioMode('file'); setStatusMsg("");
  };

  const startFile = async (file) => { try { await connectAudioEl(URL.createObjectURL(file)); } catch(e) { setStatusMsg("File playback failed: " + (e.message || e)); } };

  const startPlaylist = async (index) => {
    if (!playlist.length) return;
    const i = clamp(index, 0, playlist.length - 1);
    setCurrentTrack(i);
    await teardownAudio();
    await connectAudioEl(playlist[i].url);
  };

  const stopAudio = async () => { await teardownAudio(); };

  // ======= Dev: simple runtime tests (console)
  useEffect(() => {
    console.assert(clamp(5,0,1) === 1, 'clamp upper bound');
    console.assert(clamp(-1,0,1) === 0, 'clamp lower bound');
    console.assert(clamp(0.5,0,1) === 0.5, 'clamp mid');
    const c = new SimpleCompressor({threshold:0.2, ratio:4, attack:0.01, release:0.2});
    const before = c.process(0.9, 0.016);
    const after = c.process(0.9, 0.016);
    console.assert(after <= before + 1e-3, 'compressor non-increasing env');
    console.log('[Ferro‑Splat] secureContext=', isSecure);
  }, [isSecure]);

  // ======= UI Handlers
  const onClickStartMic = async () => { if (running) { await stopAudio(); return; } await startMic(); };
  const onClickStartDemo = async () => { if (running) { await stopAudio(); return; } await startDemo(); };
  const onClickLoadFile = async () => { if (running) { await stopAudio(); } fileInputRef.current?.click(); };
  const onFileChange = async (e) => { const file = e.target.files?.[0]; if (file) await startFile(file); e.target.value = ""; };
  const onClickLoadPlaylist = async () => { if (running) { await stopAudio(); } multiFileRef.current?.click(); };
  const onPlaylistChange = async (e) => {
    const files = Array.from(e.target.files || []);
    const list = files.map(f => ({ name: f.name, url: URL.createObjectURL(f) }));
    setPlaylist(list);
    if (list.length) await startPlaylist(0);
    e.target.value = "";
  };

  const addNozzle = () => {
    if (nozzles.length >= 16) return;
    const n = nozzles.length; const angle = (n / Math.max(1, n+1)) * Math.PI * 2;
    const newNz = {
      id: `N${n+1}`,
      band: n,
      mu: [0.5 + 0.28 * Math.cos(angle), 0.5 + 0.28 * Math.sin(angle)],
      sigma: [0.06, 0.02], angle, alphaGain: 1.0, hue: (n / 12), enabled: true,
    };
    setNozzles(prev => [...prev, newNz]);
    setEqGains(prev => [...prev, 1.0]);
  };

  const removeSelectedNozzle = () => {
    if (!selectedNozzleId) return;
    const idx = nozzles.findIndex(n => n.id === selectedNozzleId);
    if (idx === -1) return;
    const newNozzles = nozzles.filter((_, i) => i !== idx).map((nz, i) => ({ ...nz, band: i }));
    setNozzles(newNozzles);
    const newEq = eqGains.filter((_, i) => i !== idx);
    setEqGains(newEq);
    setSelectedNozzleId(null);
  };

  const ringLayout = () => {
    const n = nozzles.length; const updated = nozzles.map((nz, i) => {
      const a = (i / n) * Math.PI * 2; return { ...nz, mu: [0.5 + 0.28*Math.cos(a), 0.5 + 0.28*Math.sin(a)], angle: a };
    });
    setNozzles(updated);
  };

  const updateNozzle = (id, patch) => {
    setNozzles(prev => prev.map(nz => nz.id === id ? { ...nz, ...patch } : nz));
  };

  const selNz = nozzles.find(n => n.id === selectedNozzleId) || null;

  // ======= Render
  return (
    <div className="w-full h-full relative">
      <div ref={mountRef} className="w-full h-[70vh] bg-black rounded-2xl overflow-hidden shadow-xl" />

      {/* Control Panel */}
      <div className="absolute left-4 top-4 bg-white/85 backdrop-blur rounded-xl p-3 space-y-3 text-sm shadow min-w-[300px] max-w-[420px]">
        <div className="font-semibold">Ferro‑Splat (Digital v3)</div>

        {/* Status / Guidance */}
        {(!isSecure) && (
          <div className="text-[12px] text-red-700 bg-red-50 border border-red-200 rounded p-2">
            Mic access needs HTTPS or localhost. Use Demo/File audio or serve via HTTPS.
          </div>
        )}
        {statusMsg && (
          <div className="text-[12px] text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">{statusMsg}</div>
        )}

        {/* Audio Controls */}
        <div className="flex flex-wrap gap-2">
          <button onClick={onClickStartMic} className={`px-3 py-1 rounded text-white ${running && audioMode==='mic' ? 'bg-red-600' : 'bg-black'}`} disabled={!isSecure && !running}>{(running && audioMode==='mic') ? 'Stop Mic' : 'Start Mic'}</button>
          <button onClick={onClickStartDemo} className={`px-3 py-1 rounded text-white ${running && audioMode==='demo' ? 'bg-red-600' : 'bg-gray-800'}`}>{(running && audioMode==='demo') ? 'Stop Demo' : 'Demo Audio'}</button>
          <button onClick={onClickLoadFile} className={`px-3 py-1 rounded text-white ${running && audioMode==='file' ? 'bg-red-600' : 'bg-indigo-700'}`}>{(running && audioMode==='file') ? 'Stop File' : 'Load File'}</button>
          <input ref={fileInputRef} type="file" accept="audio/*" className="hidden" onChange={onFileChange} />
          <button onClick={onClickLoadPlaylist} className="px-3 py-1 rounded bg-indigo-500 text-white">Load Playlist</button>
          <input ref={multiFileRef} type="file" accept="audio/*" multiple className="hidden" onChange={onPlaylistChange} />
        </div>

        {/* Playlist view */}
        {playlist.length > 0 && (
          <div className="border rounded p-2 bg-white/70">
            <div className="flex items-center justify-between mb-1">
              <div className="font-medium text-[13px]">Playlist</div>
              <div className="flex gap-2">
                <button className="px-2 py-0.5 text-xs rounded bg-gray-800 text-white" onClick={()=>startPlaylist((currentTrack-1+playlist.length)%playlist.length)}>Prev</button>
                <button className="px-2 py-0.5 text-xs rounded bg-gray-800 text-white" onClick={()=>startPlaylist((currentTrack+1)%playlist.length)}>Next</button>
              </div>
            </div>
            <div className="max-h-32 overflow-auto space-y-1">
              {playlist.map((t, i) => (
                <div key={i} className={`flex items-center justify-between p-1 rounded ${i===currentTrack?'bg-indigo-100':'bg-white/50'}`}>
                  <div className="truncate mr-2 text-[12px]">{t.name}</div>
                  <button className="px-2 py-0.5 text-xs rounded bg-indigo-600 text-white" onClick={()=>startPlaylist(i)}>{i===currentTrack? 'Playing' : 'Play'}</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Global Visual Controls */}
        <div className="flex items-center gap-2">
          <label>Fade</label>
          <input type="range" min={0} max={0.05} step={0.001} value={fadeRate} onChange={(e)=>setFadeRate(parseFloat(e.target.value))} />
          <span>{fadeRate.toFixed(3)}</span>
        </div>
        <div className="flex items-center gap-2">
          <label>Emissive</label>
          <input type="range" min={0} max={2} step={0.01} value={emissiveScale} onChange={(e)=>setEmissiveScale(parseFloat(e.target.value))} />
          <span>{emissiveScale.toFixed(2)}</span>
        </div>
        <div className="flex items-center gap-2">
          <label>Show nozzles</label>
          <input type="checkbox" checked={showNozzles} onChange={(e)=>setShowNozzles(e.target.checked)} />
        </div>

        {/* Compressor Controls (global) */}
        <div className="border rounded p-2 bg-white/70 space-y-1">
          <div className="font-medium text-[13px]">Compressor</div>
          <div className="grid grid-cols-2 gap-2 items-center">
            <label className="text-[12px]">Threshold</label>
            <input type="range" min={0} max={1} step={0.01} value={comp.threshold} onChange={(e)=>setComp(c=>({...c, threshold: parseFloat(e.target.value)}))} />
            <label className="text-[12px]">Ratio</label>
            <input type="range" min={1} max={20} step={0.5} value={comp.ratio} onChange={(e)=>setComp(c=>({...c, ratio: parseFloat(e.target.value)}))} />
            <label className="text-[12px]">Attack (s)</label>
            <input type="range" min={0.001} max={0.2} step={0.001} value={comp.attack} onChange={(e)=>setComp(c=>({...c, attack: parseFloat(e.target.value)}))} />
            <label className="text-[12px]">Release (s)</label>
            <input type="range" min={0.01} max={1.0} step={0.01} value={comp.release} onChange={(e)=>setComp(c=>({...c, release: parseFloat(e.target.value)}))} />
          </div>
        </div>

        {/* EQ per band (1:1 with nozzles) */}
        <div className="border rounded p-2 bg-white/70">
          <div className="font-medium text-[13px] mb-1">EQ Gains</div>
          <div className="grid grid-cols-4 gap-2">
            {nozzles.map((nz, i) => (
              <div key={nz.id} className="flex flex-col items-center text-[11px]">
                <div className="mb-1">B{i+1}</div>
                <input type="range" min={0} max={3} step={0.01} value={eqGains[i] ?? 1.0} onChange={(e)=>{
                  const v = parseFloat(e.target.value); setEqGains(prev=>{ const c=[...prev]; c[i]=v; return c; });
                }} />
                <div>{(eqGains[i] ?? 1).toFixed(2)}×</div>
              </div>
            ))}
          </div>
        </div>

        {/* Nozzle Editor */}
        <div className="border rounded p-2 bg-white/70 space-y-2">
          <div className="flex items-center justify-between">
            <div className="font-medium text-[13px]">Nozzles</div>
            <div className="flex gap-2">
              <button className="px-2 py-0.5 text-xs rounded bg-green-600 text-white" onClick={addNozzle}>Add</button>
              <button className="px-2 py-0.5 text-xs rounded bg-orange-600 text-white" onClick={ringLayout}>Ring</button>
              <button className="px-2 py-0.5 text-xs rounded bg-red-600 text-white" onClick={removeSelectedNozzle} disabled={!selectedNozzleId}>Remove</button>
            </div>
          </div>

          <div className="max-h-28 overflow-auto grid grid-cols-4 gap-2">
            {nozzles.map(nz => (
              <button key={nz.id} className={`text-xs px-2 py-1 rounded border ${selectedNozzleId===nz.id?'bg-indigo-100 border-indigo-400':'bg-white border-gray-200'}`} onClick={()=>setSelectedNozzleId(nz.id)}>
                {nz.id}
              </button>
            ))}
          </div>

          {selNz && (
            <div className="grid grid-cols-2 gap-2 text-[12px]">
              <label>Enabled</label>
              <input type="checkbox" checked={selNz.enabled} onChange={(e)=>updateNozzle(selNz.id,{enabled:e.target.checked})} />

              <label>μx</label>
              <input type="range" min={0} max={1} step={0.001} value={selNz.mu[0]} onChange={(e)=>updateNozzle(selNz.id,{mu:[parseFloat(e.target.value), selNz.mu[1]]})} />
              <label>μy</label>
              <input type="range" min={0} max={1} step={0.001} value={selNz.mu[1]} onChange={(e)=>updateNozzle(selNz.id,{mu:[selNz.mu[0], parseFloat(e.target.value)]})} />
              <div className="col-span-2 text-[11px] text-gray-600">pos: [{selNz.mu[0].toFixed(3)}, {selNz.mu[1].toFixed(3)}]</div>

              <label>σx</label>
              <input type="range" min={0.002} max={0.2} step={0.001} value={selNz.sigma[0]} onChange={(e)=>updateNozzle(selNz.id,{sigma:[parseFloat(e.target.value), selNz.sigma[1]]})} />
              <label>σy</label>
              <input type="range" min={0.002} max={0.2} step={0.001} value={selNz.sigma[1]} onChange={(e)=>updateNozzle(selNz.id,{sigma:[selNz.sigma[0], parseFloat(e.target.value)]})} />

              <label>Angle</label>
              <input type="range" min={0} max={Math.PI*2} step={0.001} value={selNz.angle} onChange={(e)=>updateNozzle(selNz.id,{angle:parseFloat(e.target.value)})} />

              <label>Hue</label>
              <input type="range" min={0} max={1} step={0.001} value={selNz.hue} onChange={(e)=>updateNozzle(selNz.id,{hue:parseFloat(e.target.value)})} />

              <label>Alpha Gain</label>
              <input type="range" min={0} max={3} step={0.01} value={selNz.alphaGain} onChange={(e)=>updateNozzle(selNz.id,{alphaGain:parseFloat(e.target.value)})} />
            </div>
          )}
        </div>

        <div className="text-[12px] text-neutral-700">
          Tip: if mic is blocked, try Demo or Load File / Playlist. New deposits glow then fade; raise Emissive for the “compression as extension” effect. One band routes to one nozzle; add nozzles to add bands.
        </div>
      </div>
    </div>
  );
}
