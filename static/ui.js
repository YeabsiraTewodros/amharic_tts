 // preserve previous logic: UTF-8 to base64
    function utf8ToB64(str){
      const encoder = new TextEncoder();
      const bytes = encoder.encode(str);
      let binary = '';
      const len = bytes.byteLength;
      for (let i = 0; i < len; i++) binary += String.fromCharCode(bytes[i]);
      return btoa(binary);
    }

    function setStatus(txt, busy=false, type=''){
      const s = document.getElementById('status');
      s.className = 'status' + (type ? ' ' + type : '');
      s.innerHTML = (busy? '<span class="spinner"></span>' : '') + ' ' + txt;
    }

    // API base helper: read from localStorage `API_BASE`, fallback to location.origin
    function apiBase(){
      try{ const v = (localStorage.getItem('API_BASE') || '').trim(); if(v) return v.replace(/\/$/, ''); }catch(e){}
      return location.origin.replace(/\/$/, '');
    }

    function apiUrl(path){
      const base = apiBase();
      if(!path) return base;
      if(path.startsWith('/')) return base + path;
      return base + '/' + path;
    }

    // Camera helpers and server-side OCR upload
    let _stream = null;
    const videoModalHtml = `
      <div id="camModal" style="position:fixed;inset:0;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;z-index:60">
        <div style="background:white;padding:12px;border-radius:12px;max-width:420px;width:92%">
          <video id="camVideo" autoplay playsinline style="width:100%;height:auto;border-radius:8px;background:#000"></video>
          <div style="display:flex;gap:8px;margin-top:8px">
            <button id="captureBtn" class="btn">ይይዙ</button>
            <button id="closeCam" class="btn ghost">ዝጋ</button>
          </div>
        </div>
      </div>`;

    async function startCamera(){
      // If browser supports getUserMedia, open in-page camera modal
      if (navigator && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        if(document.getElementById('camModal')) return;
        document.body.insertAdjacentHTML('beforeend', videoModalHtml);
        const video = document.getElementById('camVideo');
        const constraints = { video: { facingMode: 'environment' }, audio: false };
        try{
          _stream = await navigator.mediaDevices.getUserMedia(constraints);
          video.srcObject = _stream;
        }catch(e){ setStatus('Camera not available: ' + e); document.getElementById('camModal')?.remove(); return; }

        document.getElementById('captureBtn').addEventListener('click', async ()=>{ await captureAndUpload(video); });
        document.getElementById('closeCam').addEventListener('click', ()=>{ stopCamera(); });
        return;
      }

      // Fallback: use file input (works on many mobile browsers, opens camera/gallery)
      setStatus('Camera not supported in this browser — opening file picker...', false);
      const input = document.createElement('input');
      input.type = 'file';
      input.accept = 'image/*';
      input.capture = 'environment';
      input.style.display = 'none';
      input.addEventListener('change', async (ev)=>{
        const f = ev.target.files && ev.target.files[0];
        if(f){ await uploadFile(f); }
        input.remove();
      });
      document.body.appendChild(input);
      input.click();
    }

    async function uploadFile(file){
      setStatus('Uploading image for OCR...', true);
      // show preview
      try{ const prev = document.getElementById('preview'); prev.src = URL.createObjectURL(file); prev.style.display = 'block'; }catch(e){}
      try{
        const fd = new FormData(); fd.append('image', file, file.name || 'capture.jpg');
        const res = await fetch(apiUrl('/ocr_upload'), { method: 'POST', body: fd });
        if(!res.ok){ const j = await res.json().catch(()=>null); setStatus('OCR error: ' + (j&&j.error?j.error:res.statusText)); return; }
        const j = await res.json();
        const text = (j.text||'').trim();
        if(!text){ setStatus('No text found'); return; }
        document.getElementById('text').value = text;
        setStatus('OCR complete — text inserted. Generating speech...', true);
        document.getElementById('convertSend').click();
      }catch(e){ setStatus('Upload/OCR failed: ' + e); }
    }

    function stopCamera(){ if(_stream){ _stream.getTracks().forEach(t=>t.stop()); _stream=null; } document.getElementById('camModal')?.remove(); }

    async function captureAndUpload(video){
      setStatus('Capturing image...', true);
      const w = video.videoWidth || 640; const h = video.videoHeight || 480;
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const ctx = c.getContext('2d'); ctx.drawImage(video, 0, 0, w, h);
      const blob = await new Promise(res=>c.toBlob(res,'image/jpeg',0.9));
      stopCamera();

      // show preview
      try{ const prev = document.getElementById('preview'); prev.src = URL.createObjectURL(blob); prev.style.display = 'block'; }catch(e){}

      setStatus('Uploading image for OCR...', true);
      try{
        const fd = new FormData(); fd.append('image', blob, 'capture.jpg');
        const res = await fetch(apiUrl('/ocr_upload'), { method: 'POST', body: fd });
        if(!res.ok){
          // try to show server response body for debugging
          let body = await res.text().catch(()=>null);
          try{ const j = JSON.parse(body); if(j && j.error) body = j.error; }catch(_){}
          console.error('OCR upload failed', res.status, res.statusText, body);
          setStatus('OCR error: ' + (body || (res.status + ' ' + res.statusText)));
          return;
        }
        const j = await res.json();
        const text = (j.text||'').trim();
        if(!text){ setStatus('No text found'); return; }
        document.getElementById('text').value = text;
        setStatus('OCR complete — text inserted. Generating speech...', true);
        // trigger convert flow
        document.getElementById('convertSend').click();
      }catch(e){
        console.error('Upload/OCR failed', e);
        setStatus('Upload/OCR failed: ' + e);
      }
    }

    // segmented control
    document.querySelectorAll('.segmented button').forEach(b=>{ b.addEventListener('click', ()=>{ document.querySelectorAll('.segmented button').forEach(x=>x.classList.remove('active')); b.classList.add('active'); }); });

    async function sendToESPByPush(ip, blob){ setStatus('Pushing MP3 to ' + ip + '...', true);
      try{ const res = await fetch('http://' + ip + '/play',{method:'POST',headers:{'Content-Type':'audio/mpeg'},body:blob}); if(res.ok){ setStatus('ESP32 accepted audio (push).', false, 'success'); return true; } setStatus('ESP32 push failed: ' + res.status, false, 'error'); return false; }catch(e){ setStatus('ESP32 push error: ' + e, false, 'error'); return false; } }

    async function instructESPtoPull(ip){ setStatus('Instructing ESP32 to fetch latest.mp3...', true); const url = encodeURIComponent(apiUrl('/latest.mp3')); try{ const res = await fetch('http://' + ip + '/play_url?url=' + url); if(res.ok){ setStatus('ESP32 instructed to pull latest.mp3.', false, 'success'); return true } setStatus('ESP32 instruct failed: ' + res.status, false, 'error'); return false; }catch(e){ setStatus('ESP32 instruct error: ' + e, false, 'error'); return false; } }

    // Drag and drop for upload zone
    const uploadZone = document.getElementById('uploadZone');
    uploadZone.addEventListener('click', ()=>{
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/*';
      input.addEventListener('change', async (ev)=>{ const f = ev.target.files && ev.target.files[0]; if(f){ await uploadFile(f); } });
      input.click();
    });
    uploadZone.addEventListener('dragover', (e)=>{ e.preventDefault(); uploadZone.classList.add('dragover'); });
    uploadZone.addEventListener('dragleave', (e)=>{ e.preventDefault(); uploadZone.classList.remove('dragover'); });
    uploadZone.addEventListener('drop', async (e)=>{
      e.preventDefault(); uploadZone.classList.remove('dragover');
      const files = e.dataTransfer.files; if(files.length > 0){ await uploadFile(files[0]); }
    });

    // Interactive background gradient
    document.addEventListener('mousemove', (e) => {
      const x = (e.clientX / window.innerWidth) * 100;
      const y = (e.clientY / window.innerHeight) * 100;
      document.body.style.setProperty('--bg-x', `${x}%`);
      document.body.style.setProperty('--bg-y', `${y}%`);
    });

    // PWA install prompt
    let deferredPrompt = null; window.addEventListener('beforeinstallprompt', (e)=>{ e.preventDefault(); deferredPrompt = e; });
    if('serviceWorker' in navigator){ navigator.serviceWorker.register('/static/sw.js').catch(()=>{}); }
    // Install button handling
    const installBtn = document.getElementById('installBtn');
    if(installBtn){
      installBtn.style.display = 'none';
      window.addEventListener('beforeinstallprompt', (e)=>{
        deferredPrompt = e; e.preventDefault(); installBtn.style.display = 'inline-block';
      });
      installBtn.addEventListener('click', async ()=>{
        if(!deferredPrompt) return;
        deferredPrompt.prompt();
        const choice = await deferredPrompt.userChoice;
        if(choice && choice.outcome === 'accepted'){
          setStatus('App installed', false, 'success');
          installBtn.style.display = 'none';
        }else{
          setStatus('Install dismissed', false);
        }
        deferredPrompt = null;
      });
    }

      const playLocalBtn = document.getElementById('playLocal');
      playLocalBtn.addEventListener('click', async ()=>{
        const p = document.getElementById('player');
        try{
          // toggle play/pause if same source is loaded
          const shouldLoad = !p.src || !p.src.endsWith('/latest.mp3');
          if(shouldLoad){
            p.src = apiUrl('/latest.mp3');
            const st = loadSettings() || {};
            const vol = parseFloat(st.volume ?? 1);
            const playRate = parseFloat(st.rate ?? 1);
            p.volume = vol;
            try{ p.playbackRate = playRate }catch(e){}
            await p.play();
            // setStatus will be handled by event listeners
            return;
          }
          // if playing, pause; otherwise play
          if(!p.paused){ p.pause(); }
          else { await p.play(); }
        }catch(e){ setStatus('Play failed: ' + e); }
      });

      // player event listeners: update UI while playing/paused/ended
      const playerEl = document.getElementById('player');
      playerEl.addEventListener('play', ()=>{
        try{ playLocalBtn.textContent = 'ፈርሂ (Pause)'; }catch(e){}
        setStatus('Playing audio...', true);
      });
      playerEl.addEventListener('pause', ()=>{
        try{ playLocalBtn.textContent = 'እዚህ ይጫወቱ'; }catch(e){}
        setStatus('Paused', false);
      });
      playerEl.addEventListener('ended', ()=>{
        try{ playLocalBtn.textContent = 'እዚህ ይጫወቱ'; }catch(e){}
        setStatus('Finished', false, 'success');
      });
      playerEl.addEventListener('timeupdate', ()=>{
        // show progress percentage in status
        try{
          const cur = playerEl.currentTime || 0;
          const dur = playerEl.duration || 0;
          if(dur && isFinite(dur)){
            const pct = Math.round((cur/dur)*100);
            // keep the spinner while playing
            setStatus(`Playing audio... ${pct}%`, true);
          }
        }catch(e){}
      });

    // add camera capture button behavior
    const camBtn = document.createElement('button'); camBtn.className = 'btn ghost'; camBtn.textContent = 'ፎቶ ይይዙ'; camBtn.style.marginLeft = '6px'; document.querySelector('.actions').insertBefore(camBtn, document.getElementById('playLocal'));
    camBtn.addEventListener('click', ()=>{ startCamera(); });

    // add visible upload button (some browsers block programmatic file pick or lack camera API)
    const uploadBtn = document.createElement('button'); uploadBtn.className = 'btn ghost'; uploadBtn.textContent = 'ፎቶ ላክ'; uploadBtn.style.marginLeft = '6px';
    document.querySelector('.actions').insertBefore(uploadBtn, document.getElementById('playLocal'));
    uploadBtn.addEventListener('click', ()=>{
      const input = document.createElement('input');
      input.type = 'file'; input.accept = 'image/*';
      input.addEventListener('change', async (ev)=>{ const f = ev.target.files && ev.target.files[0]; if(f){ await uploadFile(f); } });
      input.click();
    });

    // Player element
    const player = document.getElementById('player');

    // Settings modal handling and persistence
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettings = document.getElementById('closeSettings');
    const saveSettings = document.getElementById('saveSettings');
    const resetSettings = document.getElementById('resetSettings');
    const testDeviceBtn = document.getElementById('testDevice');

    const s_espIp = document.getElementById('s_espIp');
    const s_apiBase = document.getElementById('s_apiBase');
    const s_voiceSelect = document.getElementById('s_voiceSelect');
    const s_rate = document.getElementById('s_rate_range');
    const s_rate_val = document.getElementById('s_rate_val');
    const s_pitch = document.getElementById('s_pitch_range');
    const s_pitch_val = document.getElementById('s_pitch_val');
    const s_volume = document.getElementById('s_volume_range');
    const s_volume_val = document.getElementById('s_volume_val');
    const s_autoplay = document.getElementById('s_autoplay');
    const s_themeDark = document.getElementById('s_themeDark');

    const SETTINGS_KEY = 'amharic_tts_settings_v1';

    function openSettings(){
      const st = loadSettings();
      s_espIp.value = st.espIp || '';
      if(s_apiBase) s_apiBase.value = st.apiBase || '';
      s_voiceSelect.value = st.voice || document.getElementById('voiceSelect').value || 'server';
      if(s_rate){ s_rate.value = (st.rate !== undefined) ? st.rate : 1; s_rate_val.textContent = parseFloat(s_rate.value).toFixed(1); }
      if(s_pitch){ s_pitch.value = (st.pitch !== undefined) ? st.pitch : 1; s_pitch_val.textContent = parseFloat(s_pitch.value).toFixed(1); }
      if(s_volume){ s_volume.value = (st.volume !== undefined) ? st.volume : 1; s_volume_val.textContent = parseFloat(s_volume.value).toFixed(2); }
      s_autoplay.checked = !!st.autoplay;
      s_themeDark.checked = !!st.themeDark;
      settingsModal.style.display = 'flex';
      settingsModal.setAttribute('aria-hidden','false');
    }

    function closeSettingsModal(){ settingsModal.style.display = 'none'; settingsModal.setAttribute('aria-hidden','true'); }

    function loadSettings(){
      try{ const raw = localStorage.getItem(SETTINGS_KEY); if(!raw) return {}; return JSON.parse(raw); }catch(e){return {};}
    }

    function saveSettingsToStorage(obj){ localStorage.setItem(SETTINGS_KEY, JSON.stringify(obj)); }

    // range input listeners and +/- buttons in Settings
    try{
      if(s_rate){ s_rate.addEventListener('input', ()=>{ if(s_rate_val) s_rate_val.textContent = parseFloat(s_rate.value).toFixed(1); }); }
      if(s_pitch){ s_pitch.addEventListener('input', ()=>{ if(s_pitch_val) s_pitch_val.textContent = parseFloat(s_pitch.value).toFixed(1); }); }
      if(s_volume){ s_volume.addEventListener('input', ()=>{ if(s_volume_val) s_volume_val.textContent = parseFloat(s_volume.value).toFixed(2); }); }

      document.querySelectorAll('.s-incr, .s-decr').forEach(btn=>{
        btn.addEventListener('click', ()=>{
          const target = btn.getAttribute('data-target');
          const el = document.getElementById(target);
          if(!el) return;
          const step = parseFloat(el.getAttribute('step') || '0.1');
          let val = parseFloat(el.value || 0);
          if(btn.classList.contains('s-incr')) val = Math.min(parseFloat(el.max), +(val + step).toFixed(3));
          else val = Math.max(parseFloat(el.min), +(val - step).toFixed(3));
          el.value = val;
          // update display
          const disp = document.getElementById(target.replace('_range','_val'));
          if(disp) disp.textContent = (target.indexOf('volume') !== -1) ? parseFloat(val).toFixed(2) : parseFloat(val).toFixed(1);
        });
      });
    }catch(e){}

    function applySettings(st){
      if(!st) st = loadSettings();
      // update a small summary on the main UI
      const cur = document.getElementById('currentSettings');
      const ip = st.espIp || '(no device)';
      const voice = st.voice || document.getElementById('voiceSelect')?.value || 'server';
      const rate = (st.rate !== undefined) ? st.rate : 1;
      const pitch = (st.pitch !== undefined) ? st.pitch : 1;
      const volume = (st.volume !== undefined) ? st.volume : 1;
      if(cur) cur.textContent = `Device: ${ip} · Voice: ${voice} · rate:${rate} pitch:${pitch} vol:${volume}`;
      // apply theme: set explicitly based on st.themeDark (true => dark, false => light)
      const isDark = !!st.themeDark;
      if(isDark){
        document.documentElement.setAttribute('data-theme','dark');
        document.documentElement.style.setProperty('--card','#0b1220');
        document.documentElement.style.setProperty('--glass','rgba(10,12,18,0.6)');
        document.documentElement.style.setProperty('--accent-2','#ffffff');
        document.documentElement.style.setProperty('--muted','rgba(255,255,255,0.75)');
        document.documentElement.style.setProperty('--subtitle','rgba(255,255,255,0.85)');
        // dark mode component colors
        document.documentElement.style.setProperty('--surface','#0b1220');
        document.documentElement.style.setProperty('--upload-bg','rgba(255,255,255,0.02)');
        document.documentElement.style.setProperty('--input-border','rgba(255,255,255,0.08)');
        document.documentElement.style.setProperty('--segmented-bg','rgba(255,255,255,0.03)');
        document.documentElement.style.setProperty('--ghost-border','rgba(255,255,255,0.08)');
        document.documentElement.style.setProperty('--success-bg','rgba(34,197,94,0.12)');
        document.documentElement.style.setProperty('--success-color','#34d399');
        document.documentElement.style.setProperty('--error-bg','rgba(239,68,68,0.12)');
        document.documentElement.style.setProperty('--error-color','#f87171');
        document.documentElement.style.setProperty('--spinner-border','rgba(255,255,255,0.12)');
        document.documentElement.style.setProperty('--text-color','#ffffff');
      }else{
        document.documentElement.setAttribute('data-theme','light');
        document.documentElement.style.setProperty('--card','#ffffff');
        document.documentElement.style.setProperty('--glass','rgba(255,255,255,0.9)');
        document.documentElement.style.setProperty('--accent-2','#1e1b4b');
        document.documentElement.style.setProperty('--muted','#6b7280');
        document.documentElement.style.setProperty('--subtitle','rgba(30,27,75,0.65)');
        // light mode component colors
        document.documentElement.style.setProperty('--surface','#ffffff');
        document.documentElement.style.setProperty('--upload-bg','#f9fafb');
        document.documentElement.style.setProperty('--input-border','#e5e7eb');
        document.documentElement.style.setProperty('--segmented-bg','#f3f4f6');
        document.documentElement.style.setProperty('--ghost-border','#e5e7eb');
        document.documentElement.style.setProperty('--success-bg','#d1fae5');
        document.documentElement.style.setProperty('--success-color','#065f46');
        document.documentElement.style.setProperty('--error-bg','#fee2e2');
        document.documentElement.style.setProperty('--error-color','#991b1b');
        document.documentElement.style.setProperty('--spinner-border','#e5e7eb');
        document.documentElement.style.setProperty('--text-color','#1e1b4b');
      }
      // reflect theme state in the settings checkbox if present
      try{ const chk = document.getElementById('s_themeDark'); if(chk) chk.checked = isDark; }catch(e){}
    }

    // Test device connectivity by POSTing an empty request to /play (OPTIONS-friendly)
    async function testDevice(){
      const cfg = loadSettings();
      const ip = (s_espIp.value || cfg.espIp || '').trim();
      if(!ip){ setStatus('No device IP provided', false, 'error'); return; }
      setStatus('Testing device ' + ip + '...', true);
      try{
        const res = await fetch('http://' + ip + '/play', { method: 'OPTIONS' , mode: 'cors'});
        if(res.ok || res.status === 204 || res.status === 200){ setStatus('Device reachable', false, 'success'); }
        else { setStatus('Device responded: ' + res.status, false, 'error'); }
      }catch(e){ setStatus('Device test failed: ' + e, false, 'error'); }
    }

    // wire buttons
    settingsBtn?.addEventListener('click', openSettings);
    closeSettings?.addEventListener('click', closeSettingsModal);
    resetSettings?.addEventListener('click', ()=>{
      localStorage.removeItem(SETTINGS_KEY);
      try{ localStorage.removeItem('API_BASE'); }catch(e){}
      const st = loadSettings();
      applySettings(st);
      setStatus('Settings reset', false, 'success');
    });
    testDeviceBtn?.addEventListener('click', testDevice);
    saveSettings?.addEventListener('click', ()=>{
      const obj = { espIp: (s_espIp.value||'').trim(), apiBase: (s_apiBase?.value||'').trim(), voice: s_voiceSelect.value, rate: parseFloat(s_rate.value), pitch: parseFloat(s_pitch.value), volume: parseFloat(s_volume.value), autoplay: !!s_autoplay.checked, themeDark: !!s_themeDark.checked };
      saveSettingsToStorage(obj);
      try{ localStorage.setItem('API_BASE', obj.apiBase || ''); }catch(e){}
      applySettings(obj);
      setStatus('Settings saved', false, 'success');
      closeSettingsModal();
    });

    // apply settings at startup
    applySettings(loadSettings());

    document.getElementById('convertSend').addEventListener('click', async ()=>{
      const t = document.getElementById('text').value.trim(); if(!t) return alert('Enter text');
      const method = document.querySelector('.segmented button.active').dataset.val || 'push';
      const voice = document.getElementById('voiceSelect')?.value || 'server';
      const st = loadSettings();
      const espIp = (st && st.espIp) ? st.espIp.trim() : '';
      const uiRate = parseFloat(st?.rate ?? 1);
      const uiPitch = parseFloat(st?.pitch ?? 1);
      const uiVolume = parseFloat(st?.volume ?? 1);

      // Browser speech option — use SpeechSynthesis locally without hitting server
      if(voice === 'browser'){
        try{
          setStatus('Speaking locally via browser...', true);
          const speakNow = ()=>{
            const utter = new SpeechSynthesisUtterance(t);
            const voices = speechSynthesis.getVoices() || [];
            let chosen = null;
            if(voices.length){
              chosen = voices.find(v=>/amh|amharic/i.test(v.name) || /amh|amharic/i.test(v.lang));
              if(!chosen) chosen = voices.find(v=>/en|en-US|en-US/i.test(v.lang)) || voices[0];
            }
            if(chosen) utter.voice = chosen;
            utter.lang = chosen?.lang || 'am';
            utter.rate = uiRate;
            utter.pitch = uiPitch;
            try{ utter.volume = uiVolume; }catch(e){}
            utter.onend = ()=> setStatus('Spoken locally');
            speechSynthesis.speak(utter);
          };

          const voices = speechSynthesis.getVoices();
          if(!voices || voices.length === 0){
            const onv = ()=>{ window.speechSynthesis.removeEventListener('voiceschanged', onv); speakNow(); };
            window.speechSynthesis.addEventListener('voiceschanged', onv);
            setTimeout(()=>{ if((speechSynthesis.getVoices()||[]).length) speakNow(); }, 500);
          }else{
            speakNow();
          }
        }catch(e){ setStatus('Browser speech failed: ' + e); }
        return;
      }

      const slow = (voice === 'server_slow');

      setStatus('Converting...', true);
      const b64 = utf8ToB64(t);
      try{
        const res = await fetch('/tts_b64',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({b64, slow})});
        if(!res.ok){ const j = await res.json().catch(()=>null); setStatus('Convert error: ' + (j&&j.error?j.error:res.statusText)); return; }
        const blob = await res.blob();
        const p = document.getElementById('player');
        p.src = URL.createObjectURL(blob);
        p.volume = uiVolume;
        try{ p.playbackRate = uiRate; }catch(e){}
        // only autoplay if user enabled it in Settings
        const shouldAuto = (st && typeof st.autoplay !== 'undefined') ? !!st.autoplay : true;
        if(shouldAuto){ p.play().catch(()=>{}); }
        try{ await fetch(apiUrl('/latest.mp3')); }catch(e){}
        if(!espIp){ setStatus('Converted; playing locally.'); return; }
        if(method === 'push'){ const ok = await sendToESPByPush(espIp, blob); if(!ok){ setStatus('Push failed, trying instruct fallback...'); await instructESPtoPull(espIp); } } else { await instructESPtoPull(espIp); }
      }catch(e){ setStatus('Error: ' + e); }
    });