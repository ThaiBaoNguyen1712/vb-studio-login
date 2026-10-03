// presence.js — Đợt 1: Presence (avatar, timer, heartbeat/stale) + Xin mở kênh + chuông thông báo.
(function () {
  const HEARTBEAT_MS = 30000;
  const STALE_MS = 3 * 60 * 1000;
  let _hbTimer = null;
  let _clockTimer = null;

  function parseTs(v) {
    if (!v) return null;
    const t = new Date(v).getTime();
    return isNaN(t) ? null : t;
  }

  function presenceOf(ch) {
    const mine = (ch.locked_by || '') === (appState.active_user || '');
    const since = parseTs(ch.in_use_since);
    const hb = parseTs(ch.last_heartbeat) || since;
    const age = hb ? (Date.now() - hb) : null;
    const alive = ch.status === 'IN_USE' ? (age === null ? false : age < STALE_MS) : false;
    const stale = ch.status === 'IN_USE' && !alive;
    return { mine, since, hb, age, alive, stale };
  }

  function elapsedText(sinceTs) {
    if (!sinceTs) return '';
    let s = Math.max(0, Math.floor((Date.now() - sinceTs) / 1000));
    const h = Math.floor(s / 3600); s -= h * 3600;
    const m = Math.floor(s / 60); s -= m * 60;
    if (h > 0) return `${h}g${m}p`;
    if (m > 0) return `${m}p${s < 10 ? '0' : ''}${s}s`;
    return `${s}s`;
  }

  function holderInitial(name) {
    return ((name || '?').trim()[0] || '?').toUpperCase();
  }

  function myHeldChannels() {
    const me = appState.active_user || '';
    return (appState.channels || []).filter(c => c.status === 'IN_USE' && c.locked_by === me);
  }

  async function heartbeatTick() {
    const mine = myHeldChannels();
    if (!mine.length || !window.pywebview || !window.pywebview.api) return;
    for (const ch of mine) {
      try {
        const res = await window.pywebview.api.heartbeat(ch.id, appState.active_user);
        if (res && res.success === false) {
          // Mất quyền giữ (ai đó force unlock) -> refresh để đồng bộ
          await refreshData(true);
          break;
        }
      } catch (e) { /* offline — bỏ qua */ }
    }
  }

  function startPresenceLoops() {
    if (_hbTimer) clearInterval(_hbTimer);
    if (_clockTimer) clearInterval(_clockTimer);
    _hbTimer = setInterval(heartbeatTick, HEARTBEAT_MS);
    // Cập nhật timer "mở Xp" mỗi 30s mà không re-render nặng
    _clockTimer = setInterval(() => {
      document.querySelectorAll('[data-presence-since]').forEach(el => {
        const ts = parseTs(el.getAttribute('data-presence-since'));
        if (ts) el.textContent = elapsedText(ts);
      });
    }, 30000);
  }

  // ---------- Xin mở kênh ----------
  async function requestAccess(channelId) {
    const ch = (appState.channels || []).find(c => c.id === channelId);
    if (!ch) return;
    if (ch.status !== 'IN_USE') { showToast('Kênh đang trống, bạn có thể mở trực tiếp.', 'info'); return; }
    if ((ch.locked_by || '') === (appState.active_user || '')) { showToast('Bạn đang giữ kênh này rồi.', 'info'); return; }
    const msg = await showPromptToast({
      title: 'Xin mở kênh',
      message: `Kênh đang do "${ch.locked_by}" giữ. Nhập lời nhắn (tùy chọn, tối đa 200 ký tự):`,
      placeholder: 'VD: Mình cần đăng video gấp, xong trong 10p...',
      okText: 'Gửi yêu cầu'
    });
    if (msg === null) return; // bấm Hủy
    try {
      const res = await window.pywebview.api.request_access(channelId, appState.active_user, msg || '');
      if (res && res.success) {
        showToast(res.message || 'Đã gửi yêu cầu!', 'success');
        await refreshAccessRequests();
      } else {
        showToast((res && res.message) || 'Không gửi được yêu cầu!', 'warning');
      }
    } catch (err) {
      showToast('Lỗi gửi yêu cầu: ' + err, 'error');
    }
  }

  function popupEnabled() {
    try {
      return appState.settings.general.enable_request_popup !== false;
    } catch (e) { return true; }
  }

  function seenReqIds() {
    try { return JSON.parse(localStorage.getItem('vb_seen_reqs') || '[]'); }
    catch (e) { return []; }
  }

  // Yêu cầu mới gửi tới mình mà chưa thấy -> bật popup overlay nổi trên mọi app
  async function maybePopupIncoming() {
    try {
      const me = appState.active_user || '';
      const incoming = (appState.access_requests || []).filter(r => r.holder === me);
      if (!incoming.length) return;
      let seen = seenReqIds();
      const fresh = incoming.filter(r => !seen.includes(r.id));
      if (!fresh.length) return;
      seen = seen.concat(fresh.map(r => r.id)).slice(-50);
      try { localStorage.setItem('vb_seen_reqs', JSON.stringify(seen)); } catch (e) {}
      if (!popupEnabled()) return;
      const target = fresh[fresh.length - 1];
      await window.pywebview.api.show_request_popup(target);
    } catch (e) { /* popup là tính năng phụ — không chặn app */ }
  }

  async function refreshAccessRequests() {
    try {
      const reqs = await window.pywebview.api.get_access_requests('pending');
      appState.access_requests = reqs || [];
      // Đồng bộ pending vào từng channel để card hiện badge không cần refresh full
      const byCh = {};
      (appState.access_requests || []).forEach(r => {
        (byCh[r.channel_id] = byCh[r.channel_id] || []).push(r);
      });
      (appState.channels || []).forEach(c => { c.pending_requests = byCh[c.id] || []; });
      renderBell();
      maybePopupIncoming();
    } catch (e) { /* bỏ qua */ }
  }

  async function approveRequest(reqId) {
    try {
      const res = await window.pywebview.api.resolve_access_request(reqId, appState.active_user, 'approve');
      showToast((res && res.message) || 'Đã duyệt!', res && res.success ? 'success' : 'error');
      try { await window.pywebview.api.close_request_popup(reqId); } catch (e) {}
      await refreshData(true);
      await refreshAccessRequests();
    } catch (err) { showToast('Lỗi duyệt: ' + err, 'error'); }
  }

  async function denyRequest(reqId) {
    try {
      const res = await window.pywebview.api.resolve_access_request(reqId, appState.active_user, 'deny');
      showToast((res && res.message) || 'Đã từ chối!', res && res.success ? 'success' : 'error');
      try { await window.pywebview.api.close_request_popup(reqId); } catch (e) {}
      await refreshAccessRequests();
    } catch (err) { showToast('Lỗi từ chối: ' + err, 'error'); }
  }

  // ---------- Chuông thông báo ----------
  function pendingForMe() {
    const me = appState.active_user || '';
    return (appState.access_requests || []).filter(r => r.holder === me || r.requester === me);
  }

  function renderBell() {
    const badge = document.getElementById('notif-badge');
    const list = document.getElementById('notif-list');
    const items = pendingForMe();
    const incoming = items.filter(r => r.holder === (appState.active_user || ''));
    const n = incoming.length;
    if (badge) {
      badge.innerText = n > 9 ? '9+' : String(n);
      badge.classList.toggle('hidden', n === 0);
    }
    updateMyHeldCountBadge();
    if (!list) return;
    if (!items.length) {
      list.innerHTML = '<div class="px-4 py-6 text-center text-xs text-slate-400">Không có yêu cầu xin mở nào.<br>Khi đồng đội xin kênh bạn giữ, thông báo sẽ hiện ở đây.</div>';
      return;
    }
    list.innerHTML = items.map(r => {
      const isIncoming = r.holder === (appState.active_user || '');
      const when = r.created_at ? new Date(r.created_at).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }) : '';
      const actionBtns = isIncoming
        ? `<div class="flex gap-1.5 mt-2">
             <button onclick="approveRequest('${r.id}')" class="flex-1 h-7 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[11px] font-bold transition-all">Nhường kênh</button>
             <button onclick="denyRequest('${r.id}')" class="h-7 px-3 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg text-[11px] font-bold transition-all">Từ chối</button>
           </div>`
        : `<p class="text-[11px] text-amber-500 font-semibold mt-1.5">Đang chờ ${r.holder || 'holder'} duyệt…</p>`;
      return `
        <div class="px-3.5 py-3 border-b border-slate-100 dark:border-dark-border/60 last:border-0">
          <div class="flex items-center justify-between gap-2">
            <p class="text-xs font-bold text-slate-800 dark:text-slate-100 truncate">${isIncoming ? 'Xin mở kênh' : 'Đã gửi yêu cầu'}: ${r.channel_name || r.channel_id}</p>
            <span class="text-[10px] text-slate-400 shrink-0">${when}</span>
          </div>
          <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
            ${isIncoming ? `<b class="text-blue-500">${r.requester}</b> xin mở` : `Bạn xin <b>${r.holder || ''}</b> mở`}
            ${r.message ? ` — “${String(r.message).replace(/</g, '&lt;')}”` : ''}
          </p>
          ${actionBtns}
        </div>`;
    }).join('');
  }

  // Gọi khi có sự kiện quan trọng: phát âm đúng loại + báo OS nếu tab/app đang ẩn
  async function notifyImportant(kind, title, msg) {
    try {
      if (typeof playSound === 'function') playSound(kind === 'request' ? 'request' : (kind === 'approve' ? 'approve' : 'warning'));
    } catch (e) {}
    try {
      if (document.hidden && window.pywebview && window.pywebview.api && typeof window.pywebview.api.notify_os === 'function') {
        await window.pywebview.api.notify_os(title || 'VB-Studio', msg || '', kind || 'info', true);
      }
    } catch (e) {}
  }

  // ---------- Xả phiên & cập nhật Floating Action Button (FAB) ----------
  function updateMyHeldCountBadge() {
    const mine = myHeldChannels();
    const count = mine.length;
    const totalInUse = (appState.channels || []).filter(c => c.status === 'IN_USE').length;

    // 1. Badge trên Header Bar
    const badge = document.getElementById('badge-my-held-count');
    if (badge) {
      if (count > 0) {
        badge.textContent = count;
        badge.classList.remove('hidden');
      } else {
        badge.classList.add('hidden');
      }
    }

    // 2. Biến đếm trên Floating Action Button (FAB)
    const fabBadge = document.getElementById('fab-held-count');
    const fabBtn = document.getElementById('fab-release-btn');
    const fabPulse = document.getElementById('fab-pulse-dot');

    if (fabBadge) {
      fabBadge.textContent = count;
    }

    if (fabBtn) {
      if (count > 0) {
        fabBtn.classList.remove('bg-slate-900/90', 'dark:bg-dark-card/95', 'border-slate-700/60', 'text-slate-200');
        fabBtn.classList.add('bg-gradient-to-r', 'from-rose-600', 'to-red-600', 'text-white', 'border-rose-400/50', 'shadow-rose-600/40', 'ring-2', 'ring-rose-400/40');
        fabBtn.title = `Bạn đang giữ ${count} phiên. Bấm để xả và đóng tab! (Tổng hệ thống: ${totalInUse})`;
        if (fabPulse) fabPulse.classList.remove('hidden');
      } else {
        fabBtn.classList.add('bg-slate-900/90', 'dark:bg-dark-card/95', 'border-slate-700/60', 'text-slate-200');
        fabBtn.classList.remove('bg-gradient-to-r', 'from-rose-600', 'to-red-600', 'text-white', 'border-rose-400/50', 'shadow-rose-600/40', 'ring-2', 'ring-rose-400/40');
        fabBtn.title = totalInUse > 0 
          ? `Bạn không giữ phiên nào (${totalInUse} phiên đang mở bởi thành viên khác).` 
          : `Không có phiên làm việc nào đang mở.`;
        if (fabPulse) fabPulse.classList.add('hidden');
      }
    }
  }

  async function releaseMySessions() {
    const mine = myHeldChannels();
    const count = mine.length;

    if (count === 0) {
      const totalInUse = (appState.channels || []).filter(c => c.status === 'IN_USE').length;
      if (totalInUse > 0) {
        showToast(`Bạn không giam phiên nào (${totalInUse} phiên đang mở thuộc về đồng đội).`, 'info');
      } else {
        showToast('Hiện không có phiên làm việc nào đang mở.', 'info');
      }
      return;
    }

    const names = mine.map(c => c.channel_name || c.id).join(', ');
    const ok = await showConfirm({
      title: 'Xác nhận xả phiên',
      message: `Bạn đang mở ${count} kênh (${names}). Bạn có chắc muốn đóng các tab trình duyệt và giải phóng các phiên này ngay bây giờ?`,
      okText: 'Xả ngay',
      okDanger: true
    });

    if (!ok) return;

    try {
      showToast('Đang đóng các tab và xả phiên làm việc...', 'info');
      if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.release_my_sessions === 'function') {
        const res = await window.pywebview.api.release_my_sessions(appState.active_user || '');
        if (res && res.success) {
          const released = res.released_count || 0;
          if (released > 0) {
            showToast(`Đã đóng và xả thành công ${released} kênh đang mở!`, 'success');
            if (typeof playSound === 'function') playSound('success');
          } else {
            showToast('Đã làm mới trạng thái phiên.', 'info');
          }
        }
      }
      if (typeof refreshData === 'function') {
        await refreshData(true);
      }
      updateMyHeldCountBadge();
    } catch (err) {
      showToast('Lỗi khi xả phiên: ' + err, 'error');
    }
  }

  function toggleNotifPanel() {
    const p = document.getElementById('notif-panel');
    if (p) p.classList.toggle('hidden');
  }

  function closeNotifOnOutside(e) {
    const p = document.getElementById('notif-panel');
    const btn = document.getElementById('notif-bell-btn');
    if (!p || p.classList.contains('hidden')) return;
    if (p.contains(e.target) || (btn && btn.contains(e.target))) return;
    p.classList.add('hidden');
  }
  document.addEventListener('click', closeNotifOnOutside);

  // Expose
  window.popupEnabled = popupEnabled;
  window.maybePopupIncoming = maybePopupIncoming;
  window.notifyImportant = notifyImportant;
  window.presenceOf = presenceOf;
  window.elapsedText = elapsedText;
  window.holderInitial = holderInitial;
  window.myHeldChannels = myHeldChannels;
  window.updateMyHeldCountBadge = updateMyHeldCountBadge;
  window.releaseMySessions = releaseMySessions;
  window.requestAccess = requestAccess;
  window.approveRequest = approveRequest;
  window.denyRequest = denyRequest;
  window.refreshAccessRequests = refreshAccessRequests;
  window.renderBell = renderBell;
  window.toggleNotifPanel = toggleNotifPanel;
  window.startPresenceLoops = startPresenceLoops;
})();
