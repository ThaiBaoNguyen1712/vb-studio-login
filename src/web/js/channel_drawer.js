// channel_drawer.js — slide-over chi tiết kênh: 2 tab Tổng quan + Phiên.
// Mọi thao tác phụ của card cũ (ghim, kiểm tra, sửa, xóa, mở khóa, duyệt) sống ở đây.
(function () {
  const state = { id: null, tab: 'OVERVIEW' };

  function getCh() {
    if (!state.id) return null;
    return (appState.channels || []).find(c => c.id === state.id) || null;
  }

  function initDrawerDelegation() {
    const drawer = document.getElementById('channel-drawer');
    if (!drawer || drawer._delegated) return;
    drawer._delegated = true;

    drawer.addEventListener('click', (e) => {
      const tabBtn = e.target.closest('[data-action="switch-tab"]');
      if (tabBtn && tabBtn.dataset.tabId) {
        switchDrawerTab(tabBtn.dataset.tabId);
        return;
      }

      const copyBtn = e.target.closest('[data-action="copy-text"]');
      if (copyBtn && copyBtn.dataset.text) {
        copyText(copyBtn.dataset.text);
        return;
      }

      const pinBtn = e.target.closest('[data-action="toggle-pin"]');
      if (pinBtn && pinBtn.dataset.channelId && typeof togglePin === 'function') {
        togglePin(pinBtn.dataset.channelId);
        return;
      }

      const checkBtn = e.target.closest('[data-action="check-channel"]');
      if (checkBtn && checkBtn.dataset.channelId && typeof checkChannel === 'function') {
        checkChannel(checkBtn.dataset.channelId);
        return;
      }

      const editBtn = e.target.closest('[data-action="edit-channel"]');
      if (editBtn && editBtn.dataset.channelId && typeof openEditChannelModal === 'function') {
        openEditChannelModal(editBtn.dataset.channelId);
        return;
      }

      const deleteBtn = e.target.closest('[data-action="delete-channel"]');
      if (deleteBtn && deleteBtn.dataset.channelId && typeof deleteChannel === 'function') {
        deleteChannel(deleteBtn.dataset.channelId);
        return;
      }

      const launchBtn = e.target.closest('[data-action="launch-channel"]');
      if (launchBtn && launchBtn.dataset.channelId && typeof launchChannel === 'function') {
        launchChannel(launchBtn.dataset.channelId);
        return;
      }

      const forceUnlockBtn = e.target.closest('[data-action="force-unlock"]');
      if (forceUnlockBtn && forceUnlockBtn.dataset.channelId && typeof forceUnlock === 'function') {
        forceUnlock(forceUnlockBtn.dataset.channelId);
        return;
      }

      const reqAccessBtn = e.target.closest('[data-action="request-access"]');
      if (reqAccessBtn && reqAccessBtn.dataset.channelId && typeof requestAccess === 'function') {
        requestAccess(reqAccessBtn.dataset.channelId);
        return;
      }

      const approveBtn = e.target.closest('[data-action="approve-request"]');
      if (approveBtn && approveBtn.dataset.requestId && typeof approveRequest === 'function') {
        approveRequest(approveBtn.dataset.requestId);
        return;
      }

      const denyBtn = e.target.closest('[data-action="deny-request"]');
      if (denyBtn && denyBtn.dataset.requestId && typeof denyRequest === 'function') {
        denyRequest(denyBtn.dataset.requestId);
        return;
      }
    });
  }

  function openChannelDrawer(channelId, tab) {
    state.id = channelId;
    if (tab) state.tab = tab;
    initDrawerDelegation();
    renderChannelDrawer();
    OverlayController.open('channel-drawer', {
      initialFocusEl: '#drawer-body'
    });
  }

  function closeChannelDrawer() {
    OverlayController.close('channel-drawer');
    state.id = null;
  }

  function switchDrawerTab(tab) {
    state.tab = tab;
    renderChannelDrawer();
  }

  function copyText(t) {
    const done = () => showToast('Đã copy: ' + t, 'success');
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t).then(done).catch(() => showToast('Không copy được!', 'error'));
    } else {
      const ta = document.createElement('textarea');
      ta.value = t; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { showToast('Không copy được!', 'error'); }
      ta.remove();
    }
  }

  function row(label, value) {
    return `<div class="flex items-start justify-between gap-3 py-2 border-b border-slate-100 dark:border-dark-border/60 last:border-0">
      <span class="text-[11px] font-bold text-slate-400 uppercase tracking-wider shrink-0 pt-0.5">${escapeHtml(label)}</span>
      <span class="text-xs font-semibold text-slate-700 dark:text-slate-200 text-right break-all">${value}</span>
    </div>`;
  }

  function renderOverview(ch) {
    const p = getPlatform(ch.platform);
    const safeId = escapeHtml(ch.id);
    return `
      <div class="px-5 py-4">
        ${row('Nền tảng', `${escapeHtml(platName(ch.platform))}`)}
        ${row('ID kênh', `<span class="font-mono">${safeId}</span> <button type="button" data-action="copy-text" data-text="${safeId}" class="ml-1 text-blue-500 hover:text-blue-400 text-[11px] font-bold">Copy</button>`)}
        ${row('Tài khoản', `${escapeHtml(ch.account_display_name || '-')}<br><span class="text-blue-500">${escapeHtml(ch.account_email || '')}</span>`)}
        ${row('Studio URL', `<span class="break-all">${escapeHtml(ch.studio_url || '-')}</span>`)}
        ${row('Login URL', `<span class="break-all">${escapeHtml(ch.login_url || '-')}</span>`)}
        ${row('Cookies', `${Number(ch.cookies_count) || 0} chiếc`)}
        ${row('Sync cuối', `${escapeHtml(ch.last_synced_at || 'chưa có')}`)}
        ${row('Ghim', `<button type="button" data-action="toggle-pin" data-channel-id="${safeId}" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-bold ${ch.pinned ? 'bg-amber-500/20 text-amber-500' : 'bg-slate-100 dark:bg-dark-input text-slate-400'} transition-all">${icon(ch.pinned ? 'star-solid' : 'star', 'w-3.5 h-3.5')}${ch.pinned ? 'Đã ghim — bấm để bỏ' : 'Bấm để ghim'}</button>`)}
      </div>
      <div class="px-5 pb-5 pt-1 grid grid-cols-3 gap-2">
        <button type="button" data-action="check-channel" data-channel-id="${safeId}" title="Soi cookies (ngoại tuyến, không mở trình duyệt)" class="h-9 rounded-lg text-xs font-bold bg-slate-100 dark:bg-dark-input hover:bg-sky-500/20 hover:text-sky-500 transition-all inline-flex items-center justify-center gap-1.5">${icon('check', 'w-3.5 h-3.5')}Kiểm tra</button>
        <button type="button" data-action="edit-channel" data-channel-id="${safeId}" class="h-9 rounded-lg text-xs font-bold bg-slate-100 dark:bg-dark-input hover:bg-slate-200 dark:hover:bg-slate-700 transition-all inline-flex items-center justify-center gap-1.5">${icon('pencil', 'w-3.5 h-3.5')}Sửa</button>
        <button type="button" data-action="delete-channel" data-channel-id="${safeId}" class="h-9 rounded-lg text-xs font-bold bg-slate-100 dark:bg-dark-input hover:bg-red-500/20 text-red-500 transition-all inline-flex items-center justify-center gap-1.5">${icon('trash', 'w-3.5 h-3.5')}Xóa</button>
      </div>`;
  }

  function renderSession(ch) {
    const isInUse = ch.status === 'IN_USE';
    const safeId = escapeHtml(ch.id);
    if (!isInUse) {
      return `
        <div class="px-5 py-8 text-center">
          <p class="text-slate-400 flex justify-center">${icon('moon', 'w-8 h-8')}</p>
          <p class="text-sm font-bold mt-2">Kênh đang trống</p>
          <p class="text-xs text-slate-400 mt-1">Không ai giữ — bạn có thể mở ngay.</p>
          <button type="button" data-action="launch-channel" data-channel-id="${safeId}" class="mt-4 px-5 h-9 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-all">Mở Studio ngay</button>
        </div>`;
    }
    const pr = presenceOf(ch);
    const mine = pr.mine;
    const initial = holderInitial(ch.locked_by);
    const sinceTxt = pr.since ? new Date(pr.since).toLocaleString('vi-VN') : '-';
    const hbTxt = pr.hb ? new Date(pr.hb).toLocaleString('vi-VN') : '-';
    const remoteTag = ch.locked_remote ? ` • máy khác (${ch.locked_machine || '?'})` : '';
    const reqs = ch.pending_requests || [];
    return `
      <div class="px-5 py-4 space-y-4">
        <div class="flex items-center gap-3 p-3 rounded-xl bg-slate-50 dark:bg-dark-input/60 border border-slate-200 dark:border-dark-border">
          <div class="w-10 h-10 rounded-full bg-gradient-to-br from-sky-600 to-indigo-600 text-white font-extrabold flex items-center justify-center shrink-0">${escapeHtml(initial)}</div>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-bold truncate">${escapeHtml(ch.locked_by || 'Session')}${mine ? ' (bạn)' : ''}${escapeHtml(remoteTag)}</p>
            <p class="text-[11px] text-slate-400">Giữ từ ${escapeHtml(sinceTxt)}${pr.stale ? ' • <b class="text-amber-500">có thể treo (mất heartbeat &gt;3p)</b>' : ''}</p>
            <p class="text-[11px] text-slate-400">Heartbeat cuối: ${escapeHtml(hbTxt)}</p>
          </div>
        </div>
        ${mine
          ? `<button type="button" data-action="force-unlock" data-channel-id="${safeId}" class="w-full h-9 rounded-lg text-xs font-bold bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 transition-all">Giải phóng kênh của tôi</button>`
          : `<div class="grid grid-cols-2 gap-2">
               <button type="button" data-action="request-access" data-channel-id="${safeId}" class="h-9 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white transition-all inline-flex items-center justify-center gap-1.5">${icon('send', 'w-3.5 h-3.5')}Xin mở kênh</button>
               <button type="button" data-action="force-unlock" data-channel-id="${safeId}" class="h-9 rounded-lg text-xs font-bold bg-slate-200 dark:bg-slate-700 hover:bg-red-500/30 hover:text-red-500 transition-all inline-flex items-center justify-center gap-1.5" title="Nên xin mở trước">${icon('lock-open', 'w-3.5 h-3.5')}Cưỡng chế</button>
             </div>`}
        <div>
          <p class="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Yêu cầu xin mở (${reqs.length})</p>
          ${reqs.length === 0
            ? '<p class="text-xs text-slate-400">Chưa có yêu cầu nào.</p>'
            : reqs.map(r => `
              <div class="p-3 rounded-xl bg-slate-50 dark:bg-dark-input/60 border border-slate-200 dark:border-dark-border mb-2">
                <p class="text-xs font-bold">${escapeHtml(r.requester)}</p>
                ${r.message ? `<p class="text-[11px] text-slate-400 mt-0.5">“${escapeHtml(r.message)}”</p>` : ''}
                ${mine ? `
                  <div class="flex gap-1.5 mt-2">
                    <button type="button" data-action="approve-request" data-request-id="${escapeHtml(r.id)}" class="flex-1 h-7 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[11px] font-bold transition-all">Nhường kênh</button>
                    <button type="button" data-action="deny-request" data-request-id="${escapeHtml(r.id)}" class="h-7 px-3 bg-slate-200 dark:bg-slate-700 rounded-lg text-[11px] font-bold transition-all">Từ chối</button>
                  </div>` : `<p class="text-[11px] text-amber-500 font-semibold mt-1">Chờ ${escapeHtml(ch.locked_by)} duyệt…</p>`}
              </div>`).join('')}
        </div>
      </div>`;
  }

  function renderChannelDrawer() {
    const ch = getCh();
    const box = document.getElementById('drawer-body');
    const title = document.getElementById('drawer-title');
    const sub = document.getElementById('drawer-sub');
    if (!ch) { closeChannelDrawer(); return; }
    const pendN = (ch.pending_requests || []).length;
    if (title) title.innerHTML = `${platBadge(ch.platform, 'w-5 h-5')} <span class="truncate">${escapeHtml(ch.channel_name)}</span>`;
    if (sub) sub.innerText = `${platName(ch.platform)} • ${ch.id}`;
    const tabBtn = (id, label) => {
      const active = state.tab === id;
      return `<button type="button" data-action="switch-tab" data-tab-id="${escapeHtml(id)}" class="flex-1 pb-2.5 text-xs font-bold border-b-2 transition-all ${active ? 'border-blue-500 text-blue-500' : 'border-transparent text-slate-400 hover:text-slate-200'}">${escapeHtml(label)}</button>`;
    };
    const tabs = document.getElementById('drawer-tabs');
    const sessionLabel = pendN ? `Phiên (${pendN})` : 'Phiên';
    if (tabs) tabs.innerHTML = [tabBtn('OVERVIEW', 'Tổng quan'), tabBtn('SESSION', sessionLabel)].join('');
    if (box) box.innerHTML = state.tab === 'SESSION' ? renderSession(ch) : renderOverview(ch);
  }

  function refreshDrawerIfOpen(channelId) {
    if (state.id && (!channelId || state.id === channelId)) renderChannelDrawer();
  }

  window.openChannelDrawer = openChannelDrawer;
  window.closeChannelDrawer = closeChannelDrawer;
  window.switchDrawerTab = switchDrawerTab;
  window.copyText = copyText;
  window.refreshDrawerIfOpen = refreshDrawerIfOpen;
})();
