// Runs as an init script BEFORE Meet's own JS.
// Hooks RTCPeerConnection so we can grab every remote audio track,
// mixes them into one MediaStream, records with MediaRecorder, and
// streams base64 chunks back to Python via window.__sendAudioChunk
// (exposed by Playwright's page.expose_function).

(() => {
  const OriginalRTCPeerConnection = window.RTCPeerConnection;
  const audioCtx = new AudioContext();
  const mixDest = audioCtx.createMediaStreamDestination();

  window.__meetCapture = { tracks: 0, recorder: null, started: false };

  const attachTrack = (track) => {
    if (track.kind !== 'audio') return;
    const stream = new MediaStream([track]);
    const src = audioCtx.createMediaStreamSource(stream);
    src.connect(mixDest);
    window.__meetCapture.tracks += 1;
  };

  window.RTCPeerConnection = function (...args) {
    const pc = new OriginalRTCPeerConnection(...args);
    pc.addEventListener('track', (event) => {
      try { attachTrack(event.track); } catch (e) { console.error('attachTrack', e); }
    });
    return pc;
  };
  window.RTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;

  // Caller invokes this once admitted to start the recorder.
  window.__startCapture = () => {
    if (window.__meetCapture.started) return 'already-started';
    const rec = new MediaRecorder(mixDest.stream, { mimeType: 'audio/webm;codecs=opus' });
    rec.ondataavailable = async (e) => {
      if (!e.data || e.data.size === 0) return;
      const buf = await e.data.arrayBuffer();
      // Base64-encode in chunks to avoid call-stack limits on large blobs.
      const bytes = new Uint8Array(buf);
      let binary = '';
      const CHUNK = 0x8000;
      for (let i = 0; i < bytes.length; i += CHUNK) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
      }
      window.__sendAudioChunk(btoa(binary));
    };
    rec.start(5000); // emit a chunk every 5s
    window.__meetCapture.recorder = rec;
    window.__meetCapture.started = true;
    return 'started';
  };

  window.__stopCapture = () => {
    const rec = window.__meetCapture.recorder;
    if (rec && rec.state !== 'inactive') rec.stop();
    return 'stopped';
  };
})();
