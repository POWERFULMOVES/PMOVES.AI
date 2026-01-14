const logEl = document.getElementById('log');
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const statusEl = document.getElementById('status');
const roomInput = document.getElementById('room');
const passInput = document.getElementById('pass');
const encryptChk = document.getElementById('encrypt');
const decryptChk = document.getElementById('decrypt');
const peerListEl = document.getElementById('peerList');
const peersEl = document.getElementById('peers');

let ws = null;
let pc = null;
let dc = null;
let peers = 0;
let lastCGP = null;
let peerId = Math.random().toString(16).slice(2);
let rttMs = null;
const peersMap = new Map(); // peerId -> {rtt, lastSeen}

function log(...args){
  const s = args.map(x => typeof x==='string'? x : JSON.stringify(x)).join(' ');
  logEl.textContent += s+"\n";
  logEl.scrollTop = logEl.scrollHeight;
}

function drawPoints(points){
  ctx.clearRect(0,0,canvas.width,canvas.height);
  const cx = canvas.width/2, cy = canvas.height/2;
  for(const p of points){
    const x = cx + (p.proj? p.proj*200 : (Math.random()-0.5)*240);
    const y = cy + (Math.random()-0.5)*200;
    ctx.beginPath();
    ctx.arc(x,y, 4, 0, Math.PI*2);
    const mod = (p.modality||'text').toLowerCase();
    if(mod==='video') ctx.strokeStyle = '#6df1a5';
    else if(mod==='audio') ctx.strokeStyle = '#ffd166';
    else ctx.strokeStyle = '#9fb3ff';
    ctx.fillStyle = (p.conf||0)<0.5? '#a27db7' : '#5ad4e6';
    ctx.fill(); ctx.stroke();
  }
}

async function connect(){
  const room = roomInput.value || 'public';
  ws = new WebSocket(`${location.origin.replace('http','ws')}/ws/signaling/${room}`);
  ws.onopen = () => { statusEl.textContent = `WS: ${room}`; log('WS open'); sendSignal({type:'presence', from: peerId}); setupRTC(room); setInterval(()=>wsPingAll(), 7000); };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if(msg.relay){ onSignal(msg.relay); return; }
      if(msg.type==='geometry.cgp.v1'){
        let data = msg.data;
        if(decryptChk.checked && passInput.value){ try { data = await decryptAnchors(data, passInput.value); } catch(e){ log('decrypt failed'); } }
        const consts = (data.super_nodes||[]).flatMap(sn=> sn.constellations||[]);
        const pts = consts.flatMap(c=> c.points||[]);
        drawPoints(pts);
        lastCGP = data;
        return;
      }
      if(msg.type==='presence' && msg.from && msg.from!==peerId){
        peersMap.set(msg.from, {rtt:null, lastSeen:Date.now()});
        renderPeers();
        return;
      }
      if(msg.type==='roster' && msg.peers){
        // initialize unknown peers
        for(const id of msg.peers){ if(id!==peerId && !peersMap.has(id)) peersMap.set(id, {rtt:null, lastSeen:null}); }
        // prune peers not listed
        for(const id of Array.from(peersMap.keys())){ if(!msg.peers.includes(id)) peersMap.delete(id); }
        renderPeers();
        return;
      }
      if(msg.type==='ws-ping' && msg.to===peerId){
        sendSignal({type:'ws-pong', to: msg.from, from: peerId, ts: msg.ts});
        return;
      }
      if(msg.type==='ws-pong' && msg.to===peerId){
        const p = peersMap.get(msg.from)||{}; p.rtt = Date.now()-msg.ts; p.lastSeen=Date.now(); peersMap.set(msg.from,p); renderPeers();
        return;
      }
    } catch(e) { log('bad ws message'); }
  };
  ws.onclose = () => { statusEl.textContent = 'WS: closed'; };
}

function sendSignal(obj){ if(ws && ws.readyState===1) ws.send(JSON.stringify(obj)); }

async function setupRTC(room){
  pc = new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
  dc = pc.createDataChannel('shapes');
  dc.onopen = ()=>{
    log('DC open'); peers++; peersEl.textContent = `Peers: ${peers}`;
    dc.send(JSON.stringify({type:'shape-hello', room, peerId, forms:['POWERFULMOVES','CREATOR','RESEARCHER'], policy:{shapes_only:true}}));
    startPing();
  };
  dc.onmessage = (ev)=>{
    try{
      const msg = JSON.parse(ev.data);
      if(msg.type==='ping'){
        dc.send(JSON.stringify({type:'pong', ts: msg.ts, peerId}));
        return;
      }
      if(msg.type==='pong'){
        if(typeof msg.ts==='number'){
          rttMs = Date.now() - msg.ts;
          statusEl.textContent = `WS: ${room} | RTT: ${rttMs}ms`;
        }
        return;
      }
    }catch{}
    log('DC:', ev.data);
  };
  dc.onclose = ()=>{ peers=Math.max(0, peers-1); peersEl.textContent = `Peers: ${peers}`; };
  pc.onicecandidate = (e)=>{ if(e.candidate) sendSignal({type:'candidate', candidate:e.candidate, from: peerId}); };
  pc.ondatachannel = (e)=>{ const c=e.channel; c.onmessage=(ev)=>log('peer:',ev.data); };
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  sendSignal({type:'offer', sdp: offer.sdp, from: peerId});
}

async function onSignal(sig){
  if(!pc) return;
  if(sig.from && sig.from===peerId) return; // ignore own
  if(sig.type==='offer' && (!pc.currentRemoteDescription)){
    await pc.setRemoteDescription({type:'offer', sdp:sig.sdp});
    const ans = await pc.createAnswer();
    await pc.setLocalDescription(ans);
    sendSignal({type:'answer', sdp: ans.sdp, from: peerId});
  } else if(sig.type==='answer'){
    await pc.setRemoteDescription({type:'answer', sdp: sig.sdp});
  } else if(sig.type==='candidate'){
    try{ await pc.addIceCandidate(sig.candidate); }catch(e){ log('ice error'); }
  }
}

document.getElementById('connectBtn').onclick = connect;
document.getElementById('disconnectBtn').onclick = ()=>{ if(ws){ ws.close(); ws=null;} if(dc){dc.close();} if(pc){pc.close();} };
document.getElementById('shareBtn').onclick = ()=>{
  if(dc && dc.readyState==='open'){
    dc.send(JSON.stringify({type:'shape-share', note:'hello', ts:Date.now()}));
  }
};
document.getElementById('sendCgpBtn').onclick = async ()=>{
  if(!lastCGP){ log('no CGP received yet'); return; }
  const pass = passInput.value || '';
  let cgp = JSON.parse(JSON.stringify(lastCGP));
  if(encryptChk.checked && pass){
    try{ cgp = await encryptAnchors(cgp, pass); }catch(e){ log('encrypt failed'); }
  }
  let capsule = { kind:'cgp', data:cgp, ts: Date.now(), from: peerId };
  if(pass){
    try{
      const mac = await hmacSign(pass, canonicalize(cgp));
      capsule.sig = { alg:'HMAC-SHA256', hmac: mac };
    }catch(e){ log('sign failed'); }
  }
  showPreview(capsule);
};
document.getElementById('sendMeshBtn').onclick = async ()=>{
  if(!lastCGP){ log('no CGP received yet'); return; }
  const pass = passInput.value || '';
  let cgp = JSON.parse(JSON.stringify(lastCGP));
  if(encryptChk.checked && pass){
    try{ cgp = await encryptAnchors(cgp, pass); }catch(e){ log('encrypt failed'); }
  }
  let capsule = { kind:'cgp', data: cgp, ts: Date.now(), from: peerId };
  if(pass){
    try{
      const canon = canonicalize(cgp);
      const mac = await hmacSign(pass, canon);
      capsule.sig = { alg:'HMAC-SHA256', hmac: mac };
    }catch(e){ log('sign failed'); }
  }
  showPreview(capsule, true);
};
document.getElementById('saveCapsuleBtn').onclick = async ()=>{
  if(!lastCGP){ log('no CGP'); return; }
  const pass = passInput.value || '';
  let cgp = JSON.parse(JSON.stringify(lastCGP));
  if(encryptChk.checked && pass){ try{ cgp = await encryptAnchors(cgp, pass);}catch(e){ log('encrypt failed'); } }
  let capsule = { kind:'cgp', data: cgp, ts: Date.now(), from: peerId };
  if(pass){ try{ capsule.sig = { alg:'HMAC-SHA256', hmac: await hmacSign(pass, canonicalize(cgp)) }; }catch(e){} }
  const blob = new Blob([JSON.stringify({type:'shape-capsule', capsule}, null, 2)], {type:'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = `shape-capsule-${Date.now()}.json`; a.click(); URL.revokeObjectURL(url);
};

// Auto-connect on load
connect();

// Simple HMAC-SHA256 signer using Web Crypto
async function hmacSign(secret, message){
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(message));
  return btoa(String.fromCharCode(...new Uint8Array(sig)));
}

function canonicalize(obj){
  // stable JSON stringify with sorted keys
  return JSON.stringify(obj, Object.keys(obj).sort(), 0);
}

function startPing(){ setInterval(()=>{ if(dc && dc.readyState==='open'){ dc.send(JSON.stringify({type:'ping', ts: Date.now(), peerId})); } }, 5000); }

// --- AES-GCM anchor encryption compatible with server format ---
async function encryptAnchors(cgp, pass){
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await deriveKey(pass, salt);
  for(const sn of cgp.super_nodes||[]){
    for(const c of sn.constellations||[]){
      if(!('anchor' in c)) continue;
      const plain = packFloats(c.anchor||[]);
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const aad = new TextEncoder().encode(JSON.stringify({id: c.id||''}));
      const ct = await crypto.subtle.encrypt({name:'AES-GCM', iv, additionalData: aad}, key, plain);
      delete c.anchor;
      c.anchor_enc = { alg:'AES-GCM', iv: b64(iv), salt: b64(salt), ct: b64(new Uint8Array(ct)) };
    }
  }
  return cgp;
}

async function deriveKey(pass, salt){
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey('raw', enc.encode(pass), 'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:100000, hash:'SHA-256'}, baseKey, {name:'AES-GCM', length:256}, false, ['encrypt']);
}

function packFloats(arr){
  const n = arr.length|0; const buf = new ArrayBuffer(4 + 4*n);
  const dv = new DataView(buf); dv.setUint32(0, n);
  const fa = new Float32Array(buf, 4, n);
  for(let i=0;i<n;i++) fa[i] = Number(arr[i]||0);
  return new Uint8Array(buf);
}

function b64(bytes){ return btoa(String.fromCharCode(...bytes)); }

function b64dec(str){ const bin = atob(str); const arr = new Uint8Array(bin.length); for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i); return arr; }

async function decryptAnchors(cgp, pass){
  // Returns a deep copy with anchors restored
  const out = JSON.parse(JSON.stringify(cgp));
  for(const sn of out.super_nodes||[]){
    for(const c of sn.constellations||[]){
      const enc = c.anchor_enc; if(!enc) continue;
      const iv = b64dec(enc.iv); const salt = b64dec(enc.salt); const ct = b64dec(enc.ct);
      const key = await deriveKey(pass, salt);
      const aad = new TextEncoder().encode(JSON.stringify({id: c.id||''}));
      const pt = await crypto.subtle.decrypt({name:'AES-GCM', iv, additionalData: aad}, key, ct);
      const dv = new DataView(pt); const n = dv.getUint32(0);
      const fa = new Float32Array(pt, 4, n);
      c.anchor = Array.from(fa);
      delete c.anchor_enc;
    }
  }
  return out;
}

function wsPingAll(){
  const now = Date.now();
  for(const id of peersMap.keys()){
    sendSignal({type:'ws-ping', from: peerId, to: id, ts: now});
  }
}

function renderPeers(){
  peerListEl.innerHTML = '';
  for(const [id,info] of peersMap.entries()){
    const li = document.createElement('li');
    const r = info.rtt; let cls = 'peer-ok'; if(r==null) cls='peer-warn'; else if(r>300) cls='peer-bad';
    li.className = cls; li.textContent = `${id} ${r!=null? r+'ms':''}`;
    peerListEl.appendChild(li);
  }
}
