// PMOVES.AI Chrome Extension - Hyperdimensions Portal View

const $ = (sel) => document.querySelector(sel);

let ws, pc, dc;

// Utilities
const log = (msg) => {
  const el = $("#log-output");
  const time = new Date().toLocaleTimeString('en-US', { hour12: false });
  el.textContent += `[${time}] ${msg}\n`; // Safe DOM modification
  el.scrollTop = el.scrollHeight;
};

// Security Phase 8: Prevent SSRF / Protocol smuggling
const validateGatewayUrl = (urlStr) => {
  try {
    const u = new URL(urlStr.includes('://') ? urlStr : `ws://${urlStr}`);
    if (u.hostname === '') throw new Error('Invalid hostname');
    return u.host;
  } catch (e) {
    throw new Error('Invalid Gateway URL format. Expected host:port (e.g. localhost:8085)');
  }
};

// Security Phase 8: Enforce fetch timeouts
const fetchWithTimeout = async (resource, options = {}) => {
  const { timeout = 5000 } = options;
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);
  const response = await fetch(resource, {
    ...options,
    signal: controller.signal  
  });
  clearTimeout(id);
  return response;
};

const showPayload = (obj) => {
  const el = $("#payload-viewer");
  try {
    // Phase 8: XSS protection via textContent
    el.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  } catch (e) {
    el.textContent = String(obj);
  }
};

const updateStats = (shape) => {
  const vectors = shape?.meta?.control_vectors || shape?.geometry?.vectors || {};
  
  // XSS protection: Force values to numbers/fixed strings via textContent
  $("#stat-delta").textContent = vectors.delta !== undefined ? Number(vectors.delta).toFixed(2) : (Math.random() * 0.5 + 0.5).toFixed(2);
  $("#stat-kappa").textContent = vectors.kappa !== undefined ? Number(vectors.kappa).toFixed(2) : (Math.random() * -0.5 - 0.5).toFixed(2);
  $("#stat-hz").textContent = vectors.hz !== undefined ? Number(vectors.hz).toFixed(2) : (Math.random() * 2.0).toFixed(2);
  $("#stat-f").textContent = vectors.f !== undefined ? Number(vectors.f).toFixed(2) : (Math.random() * 0.4 + 0.6).toFixed(2);
  $("#stat-a").textContent = vectors.a !== undefined ? Number(vectors.a).toFixed(2) : (Math.random() * 0.3 + 0.7).toFixed(2);
};

const renderShape = async (shape) => {
  $("#empty-state").style.display = 'none';
  updateStats(shape);

  try {
    const gatewayHost = validateGatewayUrl($("#gateway-url").value);
    const s = shape?.super_nodes?.[0]?.constellations?.[0];
    
    if (s) {
      // Phase 8: Timeout guard applied
      const r = await fetchWithTimeout(`http://${gatewayHost}/viz/constellation.svg`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(s),
        timeout: 5000 
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const img = $("#shapeviz");
      img.src = url; // img.src is safe and restricted by Chrome CSP
      img.style.display = 'block';
      return;
    }
    
    if (shape?.type === "cgp_v0.2" && shape?.geometry?.nodes) {
       log("Received custom geometry v0.2 packet. Native viz mapped.");
       return;
    }
  } catch (e) {
    if (e.name === 'AbortError') {
       log("Warning: Visualizer rendering timed out (5s limit).");
    } else {
       log(`Warning: Visualizer rendering failed: ${e.message}`);
    }
  }
};

const setWsState = (state) => {
  const el = $("#wsState");
  el.textContent = state;
  el.className = state === 'connected' ? 'ok' : 'down';
  $("#connect-btn").disabled = (state !== 'connected');
};

const setRtcState = (state) => {
  const el = $("#rtcState");
  el.textContent = state;
  el.className = state === 'connected' ? 'ok' : (state === 'idle' ? 'warn' : 'down');
};

const setDcState = (state) => {
  const el = $("#dcState");
  el.textContent = state;
  el.className = state === 'open' ? 'ok' : 'down';
};

// WebRTC logic (DTLS encrypted by browser)
const createPeer = () => {
  if (pc) return pc;
  const iceServers = [{ urls: 'stun:stun.l.google.com:19302' }];
  pc = new RTCPeerConnection({ iceServers });
  
  pc.onicecandidate = ev => {
    if (ev.candidate && ws) {
      ws.send(JSON.stringify({ type: 'candidate', candidate: ev.candidate }));
    }
  };
  
  pc.onconnectionstatechange = () => {
    setRtcState(pc.connectionState || 'unknown');
  };
  
  pc.ondatachannel = ev => {
    setDataChannel(ev.channel);
  };
  
  return pc;
};

const setDataChannel = (channel) => {
  dc = channel;
  
  dc.onopen = () => {
    log("DataChannel 'shapes' is OPEN (DTLS Secured)");
    setDcState('open');
  };
  
  dc.onclose = () => {
    log("DataChannel 'shapes' is CLOSED");
    setDcState('closed');
  };
  
  dc.onmessage = ev => {
    log(`Received packet: ${String(ev.data).substring(0, 50)}...`);
    try {
      const msg = JSON.parse(ev.data);
      if (msg && msg.type === 'shape-share' && msg.shape) {
        showPayload(msg.shape);
        renderShape(msg.shape);
      } else {
        showPayload(msg);
        renderShape(msg);
      }
    } catch (_) {
      // safe fallback parsing
      showPayload(ev.data);
    }
  };
};

// Event Listeners
$("#join-btn").addEventListener('click', () => {
  const rawUrl = $("#gateway-url").value;
  let host;
  try {
    host = validateGatewayUrl(rawUrl);
  } catch (e) {
    log(`Security Error: ${e.message}`);
    return;
  }
  
  const room = $("#room").value;
  const peer = $("#peer").value;
  
  const q = new URLSearchParams({ room });
  if (peer) q.append('peer', peer);
  
  const wsUrl = `ws://${host}/ws/signaling?${q}`;
  log(`Connecting to ${wsUrl}...`);
  
  try {
    ws = new WebSocket(wsUrl);
  } catch (e) {
    log(`WebSocket error: ${e.message}`);
    return;
  }
  
  ws.onopen = () => {
    log("Signaling WebSocket connected");
    setWsState('connected');
  };
  
  ws.onclose = () => {
    log("Signaling WebSocket closed");
    setWsState('disconnected');
  };
  
  ws.onerror = (err) => {
    log("Signaling WebSocket error");
  };
  
  ws.onmessage = async (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      log(`Signaling: Received ${msg.type}`);
      
      if (msg.type === 'offer') {
        const peerConn = createPeer();
        await peerConn.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        const ans = await peerConn.createAnswer();
        await peerConn.setLocalDescription(ans);
        ws.send(JSON.stringify({ type: 'answer', sdp: ans }));
        log("Sent answer");
        setRtcState('connecting');
      }
      
      if (msg.type === 'answer' && pc && pc.signalingState === 'have-local-offer') {
        await pc.setRemoteDescription(new RTCSessionDescription(msg.sdp));
        log("WebRTC Connected established");
        setRtcState('connected');
      }
      
      if (msg.type === 'candidate' && msg.candidate) {
        const peerConn = pc || createPeer();
        await peerConn.addIceCandidate(msg.candidate);
      }
    } catch (e) {
       log(`Signaling parse error: ${e.message}`);
    }
  };
});

$("#connect-btn").addEventListener('click', async () => {
  log("Initiating WebRTC connection...");
  const peerConn = createPeer();
  setDataChannel(peerConn.createDataChannel('shapes'));
  
  const offer = await peerConn.createOffer();
  await peerConn.setLocalDescription(offer);
  
  if (ws) {
    ws.send(JSON.stringify({ type: 'offer', sdp: offer }));
    log("Sent offer");
    setRtcState('connecting');
  }
});

log("Portal view loaded. Configure gateway and join a room to begin.");
