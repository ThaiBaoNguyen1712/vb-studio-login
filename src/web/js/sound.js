// sound.js — âm thanh hệ thống offline 100% (Web Audio API, không file ngoài).
// Tôn trọng cài đặt: appState.settings.general.enable_sound_notifications (mặc định TẮT).
(function () {
  let _ctx = null;

  function soundEnabled() {
    try {
      return !!(appState && appState.settings && appState.settings.general
        && appState.settings.general.enable_sound_notifications);
    } catch (e) { return false; }
  }

  function ctx() {
    if (_ctx) return _ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    _ctx = new AC();
    return _ctx;
  }

  function beep(freq, startAt, dur, vol, type) {
    const ac = ctx();
    if (!ac) return;
    const o = ac.createOscillator();
    const g = ac.createGain();
    o.type = type || 'sine';
    o.frequency.value = freq;
    const t = ac.currentTime + (startAt || 0);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol || 0.12, t + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, t + (dur || 0.15));
    o.connect(g); g.connect(ac.destination);
    o.start(t); o.stop(t + (dur || 0.15) + 0.05);
  }

  // Các mẫu âm phân biệt theo ngữ cảnh (ngắn, không gây khó chịu)
  const PATTERNS = {
    info:    [[660, 0, 0.10]],
    success: [[523, 0, 0.10], [784, 0.09, 0.14]],
    warning: [[440, 0, 0.12], [440, 0.14, 0.12]],
    error:   [[220, 0, 0.20]],
    request: [[880, 0, 0.12], [880, 0.16, 0.12]],   // ai đó xin mở kênh bạn giữ
    approve: [[523, 0, 0.10], [659, 0.09, 0.10], [784, 0.18, 0.16]], // được nhường kênh
  };

  function playSound(type) {
    if (!soundEnabled()) return;
    _play(type);
  }

  // Nghe thử trong Settings — bỏ qua toggle để test được cả khi đang TẮT
  function previewSound(type) {
    try {
      _play(type);
      showToast('Đang phát thử âm: ' + type, 'info');
    } catch (e) {
      showToast('Trình duyệt chặn âm thanh: bấm vào trang 1 lần rồi thử lại.', 'warning');
    }
  }

  function _play(type) {
    const ac = ctx();
    if (!ac) throw new Error('no-audio');
    if (ac.state === 'suspended') ac.resume();
    const seq = PATTERNS[type] || PATTERNS.info;
    seq.forEach(([f, at, d]) => beep(f, at, d, 0.12, 'sine'));
  }

  // Bật/tắt nhanh từ Settings, persist qua backend save_settings có sẵn
  async function setSoundEnabled(on) {
    try {
      if (!appState.settings.general) appState.settings.general = {};
      appState.settings.general.enable_sound_notifications = !!on;
      await window.pywebview.api.save_settings({ general: { enable_sound_notifications: !!on } });
      if (on) playSound('success');
      showToast(on ? 'Đã bật âm thanh thông báo!' : 'Đã tắt âm thanh thông báo.', 'info');
    } catch (err) {
      showToast('Lỗi lưu cài đặt âm thanh: ' + err, 'error');
    }
  }

  window.playSound = playSound;
  window.previewSound = previewSound;
  window.setSoundEnabled = setSoundEnabled;
  window.soundEnabled = soundEnabled;
})();
