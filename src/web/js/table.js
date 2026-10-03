// table.js — bảng dữ liệu: sort/filter realtime, thao tác kênh (mở/sửa/xóa/mở khóa).
    // Table state: sort + realtime filter
    appState.table_sort = { key: null, dir: 1 };
    appState.table_q = '';
    appState.table_status = 'ALL';
    appState.table_platform = 'ALL';

    function sortTableBy(key) {
      if (appState.table_sort.key === key) {
        appState.table_sort.dir *= -1;
      } else {
        appState.table_sort = { key, dir: 1 };
      }
      renderTableRows();
    }

    function onTableFilterInput() {
      appState.table_q = (document.getElementById('table-search').value || '').trim().toLowerCase();
      appState.table_status = document.getElementById('table-status-filter').value;
      appState.table_platform = document.getElementById('table-platform-filter').value;
      renderTableRows();
    }

    function clearTableFilters() {
      document.getElementById('table-search').value = '';
      document.getElementById('table-status-filter').value = 'ALL';
      document.getElementById('table-platform-filter').value = 'ALL';
      appState.table_q = '';
      appState.table_status = 'ALL';
      appState.table_platform = 'ALL';
      renderTableRows();
    }

    function updateSortIndicators() {
      const keys = ['platform', 'channel_name', 'account', 'status'];
      keys.forEach(k => {
        const el = document.getElementById('sort-' + k);
        if (!el) return;
        if (appState.table_sort.key === k) {
          el.innerHTML = icon(appState.table_sort.dir === 1 ? 'chev-up' : 'chev-down', 'w-3 h-3 inline');
        } else {
          el.innerHTML = '';
        }
      });
    }

    function getTableData() {
      let rows = [...appState.channels];
      // Kế thừa filter toàn cục (sidebar + topbar) để đồng bộ với Dashboard
      if (appState.selected_platform !== 'ALL') {
        rows = rows.filter(c => c.platform === appState.selected_platform);
      }
      if (appState.selected_account !== 'ALL') {
        rows = rows.filter(c => c.account_id === appState.selected_account);
      }
      if (appState.search_keyword) {
        const kw = appState.search_keyword.toLowerCase();
        rows = rows.filter(c =>
          (c.channel_name || '').toLowerCase().includes(kw) ||
          (c.id || '').toLowerCase().includes(kw) ||
          (c.account_email || '').toLowerCase().includes(kw)
        );
      }
      // Filter riêng của bảng (realtime)
      if (appState.table_platform !== 'ALL') {
        rows = rows.filter(c => c.platform === appState.table_platform);
      }
      if (appState.table_status !== 'ALL') {
        rows = rows.filter(c => c.status === appState.table_status);
      }
      if (appState.table_q) {
        const q = appState.table_q;
        rows = rows.filter(c =>
          (c.channel_name || '').toLowerCase().includes(q) ||
          (c.id || '').toLowerCase().includes(q) ||
          (c.account_email || '').toLowerCase().includes(q) ||
          (c.account_display_name || '').toLowerCase().includes(q)
        );
      }
      // Sort theo header
      const { key, dir } = appState.table_sort;
      if (key) {
        const val = (c) => {
          if (key === 'platform') return platName(c.platform) || '';
          if (key === 'channel_name') return c.channel_name || '';
          if (key === 'account') return (c.account_display_name || '') + ' ' + (c.account_email || '');
          if (key === 'status') return c.status || '';
          return '';
        };
        rows.sort((a, b) => String(val(a)).localeCompare(String(val(b)), 'vi') * dir);
      }
      // Kênh ghim luôn lên đầu (giữ thứ tự sort trong từng nhóm)
      rows.sort((a, b) => (!!b.pinned - !!a.pinned));
      return rows;
    }

    // Render Table View Rows (có filter + sort + đếm realtime)
    function renderTableRows() {
      const tbody = document.getElementById('table-body');
      if (!tbody) return;
      const rows = getTableData();
      updateSortIndicators();
      if (typeof updateMyHeldCountBadge === 'function') updateMyHeldCountBadge();

      const counter = document.getElementById('table-result-count');
      if (counter) counter.innerText = `Hiển thị ${rows.length} / ${appState.channels.length} kênh`;

      if (rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="py-12 px-4 text-center text-slate-400 text-sm">Không có kênh nào khớp bộ lọc.<br><button onclick="clearTableFilters()" class="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold">Xóa lọc bảng</button></td></tr>`;
        return;
      }

      const accLogoMap = {};
      (appState.accounts || []).forEach(a => { accLogoMap[a.id] = a.logo || ''; });

      tbody.innerHTML = rows.map(ch => {
        const platLabel = platName(ch.platform);
        const isReady = ch.status === 'READY';
        const isInUse = ch.status === 'IN_USE';
        const accLogo = accLogoMap[ch.account_id] || '';

        const isExpired = ch.status === 'EXPIRED';
        let statusText = isReady ? statusDot('READY', 'Sẵn sàng') : (isExpired ? statusDot('EXPIRED', 'Hết hạn') : statusDot('NOT_SETUP', 'Chưa Setup'));
        if (isInUse) {
          let extra = '';
          try {
            const pr = presenceOf(ch);
            if (pr.since) extra = ` • <span data-presence-since="${ch.in_use_since || ''}">${elapsedText(pr.since)}</span>`;
            if (pr.stale) extra += ' • treo?';
            if (pr.mine) extra += ' (bạn)';
          } catch (e) {}
          const pend = (ch.pending_requests || []).length;
          statusText = `${statusDot('IN_USE', `Đang mở (${ch.locked_by})`)}${extra}${pend ? ` <span class="inline-flex items-center gap-0.5 text-amber-500 font-bold">${icon('send', 'w-3 h-3')}${pend}</span>` : ''}`;
        }

        // Nút hành động chính theo trạng thái: READY -> Mở, chưa setup/hết hạn -> Setup, đang mở -> khóa
        const actBtn = isInUse
          ? `<button disabled title="Đang mở bởi ${ch.locked_by || 'Session'}" class="h-8 px-3 inline-flex items-center gap-1.5 bg-sky-600/60 text-white/80 cursor-not-allowed rounded-lg text-xs font-bold transition-all shadow-xs">
               <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5-11-6.5Z"/></svg>
               <span>Đang mở</span>
             </button>`
          : isReady
          ? `<button onclick="launchChannel('${ch.id}')" title="Mở trình duyệt" class="h-8 px-3 inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs">
               <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5-11-6.5Z"/></svg>
               <span>Mở</span>
             </button>`
          : `<button onclick="launchChannel('${ch.id}')" title="${isExpired ? 'Đăng nhập lại (phiên đã hết hạn)' : 'Thiết lập đăng nhập lần đầu'}" class="h-8 px-3 inline-flex items-center gap-1.5 ${isExpired ? 'bg-red-600 hover:bg-red-500' : 'bg-amber-600 hover:bg-amber-500'} text-white rounded-lg text-xs font-bold transition-all shadow-xs">
               <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a4.5 4.5 0 0 0-6 6L3 18l3 3 5.7-5.7a4.5 4.5 0 0 0 6-6L14 13l-3-3 3.7-3.7Z"/></svg>
               <span>${isExpired ? 'Setup lại' : 'Setup'}</span>
             </button>`;

        const accCell = accLogo
          ? `<span class="flex items-center gap-2"><img src="${accLogo}" class="w-6 h-6 rounded-lg object-cover shrink-0 ring-1 ring-slate-200 dark:ring-dark-border"><span class="min-w-0"><span class="block font-semibold text-slate-700 dark:text-slate-200 truncate">${ch.account_display_name || 'Acc'}</span><span class="block text-xs truncate">${ch.account_email || ''}</span></span></span>`
          : `${ch.account_display_name || 'Acc'} • ${ch.account_email || ''}`;

        return `
          <tr class="hover:bg-slate-50/50 dark:hover:bg-dark-input/50 transition-colors">
            <td class="py-3 px-4 font-bold text-sm whitespace-nowrap">
              <span class="flex items-center gap-2">
                ${platBadge(ch.platform, 'w-5 h-5')}
                <span>${platLabel}</span>
              </span>
            </td>
            <td class="py-3 px-4 font-bold text-sm text-slate-800 dark:text-slate-100">${ch.channel_name} <span class="text-slate-400 font-normal text-xs">(#${ch.id})</span></td>
            <td class="py-3 px-4 text-sm text-slate-500 dark:text-slate-400">${accCell}</td>
            <td class="py-3 px-4 font-bold text-sm whitespace-nowrap">${statusText}</td>
            <td class="py-3 px-4 text-right whitespace-nowrap">
              <div class="inline-flex items-center gap-1.5">
                <button onclick="togglePin('${ch.id}')" title="${ch.pinned ? 'Bỏ ghim' : 'Ghim kênh'}" class="h-8 w-8 inline-flex items-center justify-center ${ch.pinned ? 'text-amber-500' : 'text-slate-400 hover:text-amber-500'} transition-colors">${icon(ch.pinned ? 'star-solid' : 'star', 'w-4 h-4')}</button>
                ${actBtn}
                <select onchange="handleTableAction(this, '${ch.id}')" title="Thao tác khác" class="no-native-arrow h-8 bg-slate-100 dark:bg-dark-input hover:bg-slate-200 dark:hover:bg-slate-700 border border-slate-200 dark:border-dark-border rounded-lg pl-2.5 text-xs font-bold text-slate-700 dark:text-slate-200 outline-none cursor-pointer transition-colors">
                  <option value="" selected disabled>Thao tác</option>
                  <option value="detail">Chi tiết</option>
                  <option value="edit">Chỉnh sửa</option>
                  ${isInUse ? '<option value="request">Xin mở kênh</option>' : ''}
                  <option value="unlock">Mở khóa</option>
                  <option value="delete">Xóa kênh</option>
                </select>
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    function handleTableAction(sel, channelId) {
      const act = sel.value;
      sel.value = '';
      if (act === 'detail') {
        openChannelDrawer(channelId);
      } else if (act === 'edit') {
        openEditChannelModal(channelId);
      } else if (act === 'request') {
        requestAccess(channelId);
      } else if (act === 'unlock') {
        forceUnlock(channelId);
      } else if (act === 'delete') {
        deleteChannel(channelId);
      }
    }

    // Actions
    async function togglePin(channelId) {
      try {
        const res = await window.pywebview.api.toggle_pin(channelId);
        if (res && res.success) {
          const ch = appState.channels.find(c => c.id === channelId);
          if (ch) ch.pinned = res.pinned;
          renderDashboard();
          if (appState.current_view === 'TABLE') renderTableRows();
          showToast(res.pinned ? 'Đã ghim kênh!' : 'Đã bỏ ghim kênh!', 'success');
        } else {
          showToast((res && res.message) || 'Lỗi ghim kênh!', 'error');
        }
      } catch (err) {
        showToast('Lỗi ghim kênh: ' + err, 'error');
      }
    }

    async function startBulkOpen(accountId) {
      const acc = (appState.accounts || []).find(a => a.id === accountId);
      const readyN = appState.channels.filter(c => c.account_id === accountId && c.status === 'READY').length;
      if (!readyN) {
        showToast('Tài khoản này không có kênh nào Sẵn sàng để mở.', 'warning');
        return;
      }
      const ok = await showConfirm({
        title: 'Mở hàng loạt',
        message: `Mở nối tiếp ${readyN} kênh Sẵn sàng của "${acc ? acc.display_name : accountId}"? Mỗi kênh là 1 cửa sổ Chromium riêng, cách nhau vài giây.\n\nLưu ý: mở dồn dập nhiều phiên cùng lúc có thể bị nền tảng đánh dấu bất thường (checkpoint/khóa tạm), nhất là acc mới hoặc yếu. Nếu thấy captcha/xác minh thì Dừng ngay.`,
        okText: 'Bắt đầu mở',
        okDanger: false
      });
      if (!ok) return;
      try {
        const res = await window.pywebview.api.launch_account_channels(accountId, appState.active_user);
        if (res && res.success) {
          showBulkPanel(accountId, 0, res.total);
        } else {
          showToast((res && res.message) || 'Không mở được hàng loạt!', 'error');
        }
      } catch (err) {
        showToast('Lỗi mở hàng loạt: ' + err, 'error');
      }
    }

    async function stopBulkOpen() {
      try {
        await window.pywebview.api.stop_bulk_launch();
      } catch (err) {
        console.error('stopBulkOpen:', err);
      }
    }

    function showBulkPanel(accountId, done, total) {
      const panel = document.getElementById('bulk-panel');
      if (!panel) return;
      panel.classList.remove('hidden');
      delete panel.dataset.kind;
      document.getElementById('bulk-stop-btn').onclick = stopBulkOpen;
      updateBulkPanel(accountId, done, total, null, false, false);
    }

    function updateBulkPanel(accountId, done, total, currentId, stopped, finished, opened, skipped) {
      const panel = document.getElementById('bulk-panel');
      if (!panel) return;
      const acc = (appState.accounts || []).find(a => a.id === accountId);
      const accName = acc ? acc.display_name : accountId;
      const pct = total > 0 ? Math.round((done / total) * 100) : 0;
      document.getElementById('bulk-text').innerText = finished
        ? (stopped ? `Đã dừng: mở ${opened}/${total} kênh (${accName})` : `Xong: mở ${opened}/${total} kênh, bỏ qua ${skipped || 0} (${accName})`)
        : `Đang mở ${done + 1}/${total} (${accName})${currentId ? ' — ' + currentId : ''}`;
      document.getElementById('bulk-bar').style.width = pct + '%';
      const stopBtn = document.getElementById('bulk-stop-btn');
      stopBtn.classList.toggle('hidden', !!finished);
      stopBtn.onclick = stopBulkOpen;
      if (finished) {
        showToast(stopped ? `Đã dừng mở hàng loạt (${opened}/${total}).` : `Mở hàng loạt xong: ${opened}/${total} kênh!`, stopped ? 'warning' : 'success');
        setTimeout(() => panel.classList.add('hidden'), 6000);
      }
    }

    window.addEventListener('bulk_progress', (e) => {
      const d = e.detail || {};
      updateBulkPanel(d.account_id, d.done, d.total, d.current_id, d.stopped, d.finished, d.opened, d.skipped);
    });

    // Kiểm tra 1 kênh (kết quả ghi vào report ở module Kiểm Tra Phiên)
    async function checkChannel(channelId) {
      showToast(`Đang phân tích cookies kênh #${channelId} (an toàn, không mở trình duyệt)...`, 'info');
      try {
        const res = await window.pywebview.api.check_channel(channelId, appState.active_user);
        if (!(res && res.success)) showToast((res && res.message) || 'Lỗi kiểm tra!', 'error');
      } catch (err) {
        showToast('Lỗi kiểm tra: ' + err, 'error');
      }
    }

    async function launchChannel(channelId) {
      showToast(`Đang mở trình duyệt Chromium cho kênh #${channelId}...`, 'info');
      showAsyncLoading(`Khởi động kênh #${channelId}...`);
      try {
        const res = await window.pywebview.api.launch_channel(channelId, appState.active_user);
        if (!res.success) showToast(res.message, 'warning');
      } catch (err) {
        showToast(`Lỗi: ${err}`, 'error');
      } finally {
        hideAsyncLoading();
      }
    }

    async function forceUnlock(channelId) {
      const ch = (appState.channels || []).find(c => c.id === channelId);
      const holder = ch ? ch.locked_by : '';
      const pendN = ch && ch.pending_requests ? ch.pending_requests.length : 0;
      const ok = await showConfirm({
        title: 'Mở khóa cưỡng chế',
        message: `Bạn có chắc muốn cưỡng chế mở khóa kênh #${channelId}${holder ? ` (đang do "${holder}" giữ)` : ''}${pendN ? ` — có ${pendN} yêu cầu xin mở đang chờ` : ''}? Nên dùng "Xin mở" trước để tránh xung đột. Phiên đang mở (nếu có) sẽ bị giải phóng.`,
        okText: 'Mở khóa'
      });
      if (!ok) return;
      const reason = await showPromptToast({
        title: 'Lý do mở khóa',
        message: 'Nhập lý do ngắn để ghi log team (Enter để bỏ qua):',
        placeholder: 'VD: phiên treo, đồng đội về quên tắt...',
        okText: 'Xác nhận mở khóa'
      });
      if (reason === null) return;
      showBlockingLoading('Đang giải phóng khóa kênh...');
      try {
        await window.pywebview.api.force_unlock(channelId, reason || '', appState.active_user);
        try { await window.pywebview.api.close_channel_popups(channelId); } catch (e) {}
        showToast('Đã giải phóng khóa kênh thành công!', 'success');
        await refreshData(true);
      } catch (err) {
        showToast('Lỗi mở khóa: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function deleteChannel(channelId) {
      const ok = await showConfirm({
        title: 'Xóa kênh',
        message: `Chuyển kênh #${channelId} vào thùng rác? Khôi phục được trong 30 ngày.`,
        okText: 'Chuyển vào thùng rác'
      });
      if (!ok) return;
      showBlockingLoading('Đang chuyển kênh vào thùng rác...');
      try {
        const res = await window.pywebview.api.delete_channel(channelId);
        showToast((res && res.message) || 'Đã xóa kênh!', 'info');
        await refreshData(true);
      } catch (err) {
        showToast('Lỗi xóa kênh: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function deleteAccount(accountId) {
      const acc = (appState.accounts || []).find(a => a.id === accountId);
      const ok = await showConfirm({
        title: 'Xóa tài khoản',
        message: `Chuyển tài khoản "${acc ? acc.display_name : accountId}" và toàn bộ kênh của nó vào thùng rác? Khôi phục được trong 30 ngày.`,
        okText: 'Chuyển vào thùng rác'
      });
      if (!ok) return;
      showBlockingLoading('Đang chuyển tài khoản vào thùng rác...');
      try {
        const res = await window.pywebview.api.delete_account(accountId);
        if (res && res.success) {
          closeModal('modal-edit-account');
          showToast(res.message || 'Đã xóa tài khoản!', 'info');
          await refreshData(true);
        } else {
          showToast((res && res.message) || 'Lỗi xóa tài khoản!', 'error');
        }
      } catch (err) {
        showToast('Lỗi xóa tài khoản: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }
