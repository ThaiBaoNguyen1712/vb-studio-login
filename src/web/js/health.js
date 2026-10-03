// health.js — module Kiểm tra phiên riêng biệt: chạy đợt kiểm tra, lịch sử runs, report chi tiết.
(function () {
  let pollTimer = null;

  function runs() { return appState.health_runs || []; }
  function selectedRun() {
    return runs().find(r => r.id === appState.health_selected_run) || runs()[0] || null;
  }

  function fmtTime(iso) {
    if (!iso) return '-';
    try { return new Date(iso).toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' }); }
    catch (e) { return iso; }
  }

  function resultPill(st) {
    const map = {
      alive: ['bg-emerald-500/10 text-emerald-400 border-emerald-500/20', 'bg-emerald-400', 'Sống'],
      dead: ['bg-red-500/10 text-red-400 border-red-500/20', 'bg-red-400', 'Hết hạn'],
      error: ['bg-amber-500/10 text-amber-400 border-amber-500/20', 'bg-amber-400', 'Lỗi'],
      empty: ['bg-slate-500/10 text-slate-400 border-slate-500/20', 'bg-slate-400', 'Trống'],
      skipped: ['bg-slate-500/10 text-slate-400 border-slate-500/20', 'bg-slate-400', 'Bỏ qua'],
    };
    const [cls, dot, txt] = map[st] || map.error;
    return `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold border ${cls} whitespace-nowrap"><span class="w-1.5 h-1.5 rounded-full ${dot}"></span>${txt}</span>`;
  }

  function runStatusPill(run) {
    if (!run) return '-';
    if (run.status === 'running') return `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20 whitespace-nowrap">${icon('refresh', 'w-3 h-3 animate-spin')}Đang chạy</span>`;
    if (run.status === 'stopped') return '<span class="px-2 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20 whitespace-nowrap">Đã dừng</span>';
    return `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">${icon('check', 'w-3 h-3')}Xong</span>`;
  }

  // ---------- Render ----------
  async function renderHealth() {
    if (!runs().length) await refreshHealth(false);
    else paintHealth();
  }

  async function refreshHealth(manual) {
    try {
      const list = await window.pywebview.api.get_health_runs(30);
      appState.health_runs = list || [];
      if (!appState.health_selected_run && appState.health_runs.length) {
        appState.health_selected_run = appState.health_runs[0].id;
      }
      paintHealth();
      if (manual) showToast('Đã làm mới lịch sử kiểm tra!', 'info');
    } catch (err) {
      if (manual) showToast('Lỗi tải lịch sử: ' + err, 'error');
    }
  }

  function paintHealth() {
    paintSummary();
    paintHistory();
    paintNavBadge();
    managePoll();
  }

  function paintSummary() {
    const run = selectedRun();
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.innerText = v; };
    if (!run) {
      set('health-sum-total', '-'); set('health-sum-alive', '-'); set('health-sum-dead', '-');
      set('health-sum-error', '-'); set('health-sum-skipped', '-');
      hideProgress();
      return;
    }
    const st = run.stats || {};
    set('health-sum-total', run.total != null ? run.total : '-');
    set('health-sum-alive', st.alive || 0);
    set('health-sum-dead', st.dead || 0);
    set('health-sum-error', (st.error || 0) + (st.empty || 0));
    set('health-sum-skipped', st.skipped || 0);
    if (run.status === 'running') {
      const done = Object.values(st).reduce((a, b) => a + (b || 0), 0);
      showProgress(run, done);
    } else {
      hideProgress();
    }
  }

  function paintHistory() {
    const tbody = document.getElementById('health-runs-tbody');
    if (!tbody) return;
    const list = runs();
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="py-10 px-4 text-center text-slate-400 text-sm">Chưa có đợt kiểm tra nào.<br>Bấm “Kiểm tra tất cả kênh” để chạy đợt đầu tiên.</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(r => {
      const st = r.stats || {};
      const sel = r.id === (selectedRun() && selectedRun().id);
      return `
        <tr class="transition-colors ${sel ? 'bg-blue-500/5' : 'hover:bg-slate-50/50 dark:hover:bg-dark-input/50'}">
          <td class="py-3 px-4 text-sm font-semibold whitespace-nowrap">${fmtTime(r.started_at)}</td>
          <td class="py-3 px-4 text-sm">${r.triggered_by || '-'}</td>
          <td class="py-3 px-4 text-sm whitespace-nowrap">${r.scope === 'ALL' ? 'Tất cả kênh' : `<span class="font-mono text-xs">${r.scope}</span>`}</td>
          <td class="py-3 px-4 text-sm text-center whitespace-nowrap">
            <b class="text-emerald-500">${st.alive || 0}</b> /
            <b class="text-red-400">${st.dead || 0}</b> /
            <b class="text-amber-500">${(st.error || 0) + (st.empty || 0)}</b> /
            <b class="text-slate-400">${st.skipped || 0}</b>
          </td>
          <td class="py-3 px-4 text-center">${runStatusPill(r)}</td>
          <td class="py-3 px-4 text-right">
            <button onclick="selectHealthRun('${r.id}')" class="h-8 px-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all">Xem report</button>
          </td>
        </tr>`;
    }).join('');
  }

  async function selectHealthRun(runId) {
    appState.health_selected_run = runId;
    try {
      const full = await window.pywebview.api.get_health_run(runId);
      if (full && full.id) {
        const i = runs().findIndex(r => r.id === runId);
        if (i >= 0) appState.health_runs[i] = full;
      }
    } catch (e) { /* dùng cache list */ }
    paintHealth();
    paintDetail();
    document.getElementById('health-detail-card').classList.remove('hidden');
    document.getElementById('health-detail-card').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function closeHealthDetail() {
    document.getElementById('health-detail-card').classList.add('hidden');
  }

  function paintDetail() {
    const run = selectedRun();
    const tbody = document.getElementById('health-detail-tbody');
    const title = document.getElementById('health-detail-title');
    if (!tbody || !run) return;
    if (title) title.innerText = `${run.id} • ${fmtTime(run.started_at)}`;
    const results = run.results || [];
    if (!results.length) {
      tbody.innerHTML = '<tr><td colspan="4" class="py-8 px-4 text-center text-slate-400 text-sm">Đợt này chưa có kết quả chi tiết (đang chạy hoặc run cũ trước khi có report).</td></tr>';
      return;
    }
    tbody.innerHTML = results.map(r => `
      <tr class="hover:bg-slate-50/50 dark:hover:bg-dark-input/50 transition-colors">
        <td class="py-3 px-4 text-sm font-bold">${r.channel_name || r.channel_id} <span class="text-slate-400 font-normal text-xs">(${r.channel_id})</span></td>
        <td class="py-3 px-4 text-center">${resultPill(r.status)}</td>
        <td class="py-3 px-4 text-xs text-slate-500 dark:text-slate-400">${(r.detail || '').replace(/</g, '&lt;')}</td>
        <td class="py-3 px-4 text-right whitespace-nowrap">
          ${r.status === 'dead'
            ? `<button onclick="launchChannel('${r.channel_id}')" class="h-8 px-3 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold transition-all">Setup lại</button>`
            : `<button onclick="openChannelDrawer('${r.channel_id}')" class="h-8 px-3 bg-slate-200 dark:bg-slate-700 hover:bg-slate-300 dark:hover:bg-slate-600 rounded-lg text-xs font-bold transition-all">Chi tiết</button>`}
        </td>
      </tr>`).join('');
  }

  function paintNavBadge() {
    const badge = document.getElementById('health-nav-badge');
    if (!badge) return;
    const latest = runs().find(r => r.status === 'finished');
    const dead = latest && latest.stats ? (latest.stats.dead || 0) : 0;
    if (dead > 0) {
      badge.innerText = dead > 9 ? '9+' : String(dead);
      badge.classList.remove('hidden');
      badge.title = `${dead} kênh hết hạn ở đợt kiểm tra gần nhất`;
    } else {
      badge.classList.add('hidden');
    }
  }

  // ---------- Progress ----------
  function showProgress(run, done) {
    const wrap = document.getElementById('health-progress-wrap');
    const stopBtn = document.getElementById('health-stop-btn');
    if (!wrap) return;
    wrap.classList.remove('hidden');
    if (stopBtn) stopBtn.classList.remove('hidden');
    const total = run.total || 1;
    const pct = Math.min(100, Math.round((done / total) * 100));
    document.getElementById('health-progress-text').innerText =
      `Đang kiểm tra ${Math.min(done + 1, total)}/${total} — ${run.triggered_by || ''}`;
    document.getElementById('health-progress-pct').innerText = pct + '%';
    document.getElementById('health-progress-bar').style.width = pct + '%';
  }

  function hideProgress() {
    const wrap = document.getElementById('health-progress-wrap');
    const stopBtn = document.getElementById('health-stop-btn');
    if (wrap) wrap.classList.add('hidden');
    if (stopBtn) stopBtn.classList.add('hidden');
  }

  function managePoll() {
    const run = selectedRun();
    const running = run && run.status === 'running';
    if (running && !pollTimer) {
      pollTimer = setInterval(pollSelectedRun, 3000);
    } else if (!running && pollTimer) {
      clearInterval(pollTimer); pollTimer = null;
    }
  }

  async function pollSelectedRun() {
    const run = selectedRun();
    if (!run || run.status !== 'running') { managePoll(); return; }
    try {
      const full = await window.pywebview.api.get_health_run(run.id);
      if (full && full.id) {
        const i = runs().findIndex(r => r.id === run.id);
        if (i >= 0) appState.health_runs[i] = full;
        paintHealth();
        if (appState.health_selected_run === run.id) paintDetail();
        if (full.status !== 'running') onRunSettled(full);
      }
    } catch (e) { /* poll sau */ }
  }

  function onRunSettled(run) {
    const st = run.stats || {};
    showToast(`Kiểm tra xong: ${st.alive || 0} sống / ${st.dead || 0} hết hạn / ${(st.error || 0) + (st.empty || 0)} lỗi!`, (st.dead || 0) > 0 ? 'warning' : 'success');
    refreshData(true); // cập nhật badge EXPIRED trên dashboard/table
  }

  // ---------- Actions ----------
  async function startHealthAll() {
    const n = (appState.channels || []).filter(c => c.status === 'READY' || c.status === 'EXPIRED').length;
    if (!n) { showToast('Không có kênh nào có phiên để kiểm tra.', 'warning'); return; }
    const ok = await showConfirm({
      title: 'Kiểm tra hàng loạt',
      message: `Phân tích cookies ${n} kênh (offline, không mở trình duyệt, không nguy cơ khóa acc)? Kênh đang mở sẽ bị bỏ qua. Kết quả lưu thành report xem lại được.`,
      okText: 'Bắt đầu kiểm tra',
      okDanger: false
    });
    if (!ok) return;
    try {
      const res = await window.pywebview.api.check_all_channels(appState.active_user);
      if (res && res.success) {
        appState.health_selected_run = res.run_id;
        await refreshHealth(false);
        const card = document.getElementById('health-detail-card');
        if (card) card.classList.add('hidden');
        showToast(`Bắt đầu kiểm tra ${res.total} kênh...`, 'info');
      } else {
        showToast((res && res.message) || 'Không kiểm tra được!', 'error');
      }
    } catch (err) {
      showToast('Lỗi kiểm tra: ' + err, 'error');
    }
  }

  async function stopHealthCheck() {
    try { await window.pywebview.api.stop_health_check(); }
    catch (err) { console.error('stopHealthCheck:', err); }
  }

  // Realtime từ backend
  window.addEventListener('health_run_progress', (e) => {
    const d = e.detail || {};
    if (d.finished) {
      refreshHealth(false).then(() => {
        if (appState.health_selected_run === d.run_id) selectHealthRun(d.run_id);
      });
      return;
    }
    if (d.run_id && d.run_id === appState.health_selected_run) {
      showProgress({ total: d.total, triggered_by: '' }, d.done);
    }
  });

  window.addEventListener('health_run_finished', async (e) => {
    const d = e.detail || {};
    await refreshHealth(false);
    if (d.run_id) {
      appState.health_selected_run = d.run_id;
      paintHealth();
      const run = selectedRun();
      if (run && run.status !== 'running') onRunSettled(run);
    }
  });

  window.renderHealth = renderHealth;
  window.refreshHealth = refreshHealth;
  window.selectHealthRun = selectHealthRun;
  window.closeHealthDetail = closeHealthDetail;
  window.startHealthAll = startHealthAll;
  window.stopHealthCheck = stopHealthCheck;
})();
