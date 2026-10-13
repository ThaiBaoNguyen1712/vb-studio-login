// dashboard.js — render cards dashboard (lưới/cuộn ngang), sort, filter nền tảng/trạng thái.
    // Render bộ lọc nền tảng động từ registry + badge đếm kênh
    function renderPlatformFilters() {
      const box = document.getElementById('platform-filter-list');
      if (!box) return;
      if (!box.dataset.bound) {
        box.dataset.bound = 'true';
        box.addEventListener('click', (e) => {
          const btn = e.target.closest('[data-action="filter-platform"]');
          if (btn && btn.dataset.platform) {
            setPlatformFilter(btn.dataset.platform);
          }
        });
      }
      const plats = appState.platforms || [];
      const total = appState.channels.length;
      const countOf = (code) => code === 'ALL'
        ? total
        : appState.channels.filter(c => c.platform === code).length;
      const btnCls = (active) => active
        ? 'sb-center w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-bold text-blue-600 dark:text-white bg-blue-50 dark:bg-blue-600/20 transition-all'
        : 'sb-center w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-dark-card transition-all';
      const allBtn = `
        <button type="button" data-action="filter-platform" data-platform="ALL" class="${btnCls(appState.selected_platform === 'ALL')}">
          <span class="flex items-center gap-2 sb-label">${icon('globe', 'w-4 h-4 shrink-0')}<span class="sb-label">Tất cả kênh</span></span>
          <span class="sb-label text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 font-bold">${countOf('ALL')}</span>
        </button>`;
      box.innerHTML = [
        allBtn,
        ...plats.map(p => `
          <button type="button" data-action="filter-platform" data-platform="${escapeHtml(p.code)}" class="${btnCls(appState.selected_platform === p.code)}">
            <span class="flex items-center gap-2 min-w-0">
              ${platBadge(p.code, 'w-4 h-4')}
              <span class="sb-label truncate">${escapeHtml(p.name || p.code)}</span>
            </span>
            <span class="sb-label text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700/50 font-bold shrink-0">${countOf(p.code)}</span>
          </button>`)
      ].join('');
    }

    function setPlatformFilter(platformCode) {
      appState.selected_platform = platformCode;
      if (appState.current_view !== 'DASHBOARD') switchView('DASHBOARD');
      renderPlatformFilters();
      renderDashboard();
    }

    // Card gọn tối đa: icon nền tảng + tên kênh + dot trạng thái + 1 nút chính + nút drawer.
    // Mọi thao tác phụ (ghim, kiểm tra, sửa, xóa, mở khóa) chuyển vào drawer chi tiết.
    const STATUS_DOT = {
      READY: ['bg-emerald-400', 'Sẵn sàng'],
      NOT_SETUP: ['bg-amber-400', 'Chưa thiết lập'],
      IN_USE: ['bg-sky-400', 'Đang mở'],
      EXPIRED: ['bg-red-400', 'Hết hạn']
    };
    function renderChannelCard(ch, isColumnMode = false, showAccount = false) {
      const isReady = ch.status === 'READY';
      const isInUse = ch.status === 'IN_USE';
      const isExpired = ch.status === 'EXPIRED';
      const pr = (typeof presenceOf === 'function') ? presenceOf(ch) : { mine: false, alive: true, stale: false, since: null };
      const pendN = (ch.pending_requests || []).length;
      const safeId = escapeHtml(ch.id);
      const safeName = escapeHtml(ch.channel_name || '');
      const safeAccEmail = escapeHtml(ch.account_email || '');
      const safeAccDisplay = escapeHtml(ch.account_display_name || 'Acc');
      const safeLockedBy = escapeHtml(ch.locked_by || 'Session');
      const remoteTag = ch.locked_remote ? ` • máy khác (${ch.locked_machine || '?'})` : '';

      const [dotCls, dotLabel] = STATUS_DOT[ch.status] || STATUS_DOT.NOT_SETUP;
      const dotPulse = (isInUse && pr.alive) ? ' animate-pulse' : '';
      const dotTitle = isInUse
        ? `Đang mở bởi ${ch.locked_by || 'Session'}${remoteTag}${pr.stale ? ' — heartbeat mất >3p, có thể treo' : ''}${pendN ? ` — ${pendN} yêu cầu xin mở` : ''}`
        : dotLabel;
      const dot = `<span class="w-2 h-2 rounded-full ${dotCls}${dotPulse} shrink-0" title="${escapeHtml(dotTitle)}"></span>`;
      const pendBadge = pendN > 0
        ? `<span class="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30 shrink-0" title="${pendN} yêu cầu xin mở đang chờ">${icon('send', 'w-3 h-3')}${pendN}</span>` : '';
      const pinStar = ch.pinned ? `<span class="text-amber-500 shrink-0 inline-flex items-center" title="Kênh đã ghim">${icon('star-solid', 'w-3.5 h-3.5')}</span>` : '';

      let mainText = isReady ? 'Mở Studio' : (isInUse ? (pr.mine ? 'Bạn đang mở' : 'Xin mở') : (isExpired ? 'Thiết lập lại' : 'Thiết lập'));
      let mainColor = isReady ? 'bg-emerald-600 hover:bg-emerald-500 text-white' : (isInUse ? (pr.mine ? 'bg-sky-600 text-white cursor-not-allowed opacity-80' : 'bg-blue-600 hover:bg-blue-500 text-white') : (isExpired ? 'bg-red-600 hover:bg-red-500 text-white' : 'bg-amber-600 hover:bg-amber-500 text-white'));
      const mainActionAttr = isInUse ? (pr.mine ? '' : `data-action="request-access" data-channel-id="${safeId}"`) : `data-action="launch-channel" data-channel-id="${safeId}"`;
      const mainDisabled = (isInUse && pr.mine) ? 'disabled' : '';
      const mainTitle = isInUse ? (pr.mine ? 'Bạn đang giữ kênh này' : 'Gửi yêu cầu xin mở tới ' + (ch.locked_by || '')) : mainText;

      const presenceLine = isInUse
        ? `<div class="ch-presence-line flex items-center gap-1.5 text-[11px] text-slate-400 truncate">
             <span class="w-1.5 h-1.5 rounded-full ${pr.alive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'} shrink-0"></span>
             <span class="truncate">${safeLockedBy}${remoteTag ? escapeHtml(remoteTag) : ''}${pr.stale ? ' • treo?' : ''}${pr.since ? ` • <span data-presence-since="${escapeHtml(ch.in_use_since || '')}">${(typeof elapsedText === 'function') ? elapsedText(pr.since) : ''}</span>` : ''}</span>
           </div>`
        : '';

      const cardHighlight = ch.pinned
        ? 'border-amber-400 dark:border-amber-500/80 ring-2 ring-amber-400/50 dark:ring-amber-500/40 shadow-sm shadow-amber-500/15 bg-amber-50/30 dark:bg-amber-950/15'
        : 'border-slate-200 dark:border-dark-border hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-dark-card shadow-xs';

      return `
        <div class="ch-card border ${cardHighlight} rounded-xl p-3 transition-all flex flex-col gap-2">
          <div class="flex items-center gap-2 min-w-0">
            <span title="${escapeHtml(platName(ch.platform))}">${platBadge(ch.platform, 'w-5 h-5')}</span>
            <h4 class="font-bold text-[13px] tracking-tight text-slate-800 dark:text-slate-100 truncate flex-1" title="${safeName} (${safeId})">${safeName}</h4>
            ${pinStar}${pendBadge}${dot}
          </div>
          <div class="ch-acc-line flex items-center gap-1 text-[11px] text-slate-400 truncate" title="${safeAccEmail}">${icon('user', 'w-3 h-3 shrink-0')}<span class="truncate">${safeAccDisplay}${ch.account_email ? ' • ' + safeAccEmail : ''}</span></div>
          ${presenceLine}
          <div class="flex items-center gap-1.5">
            <button type="button" ${mainActionAttr} ${mainDisabled} title="${escapeHtml(mainTitle)}" class="ch-main-btn flex-1 h-8 ${mainColor} font-bold text-xs rounded-lg transition-all shadow-xs truncate px-2">
              ${escapeHtml(mainText)}
            </button>
            <button type="button" data-action="open-drawer" data-channel-id="${safeId}" title="Chi tiết kênh" class="w-8 h-8 shrink-0 flex items-center justify-center rounded-lg bg-slate-100 dark:bg-dark-input hover:bg-blue-500/20 hover:text-blue-500 text-slate-500 transition-colors">${icon('eye', 'w-4 h-4')}</button>
          </div>
        </div>
      `;
    }

    // Cập nhật thanh hiển thị trạng thái lọc
    function updateActiveFilterBar(matchingCount, totalCount) {
      const bar = document.getElementById('active-filter-bar');
      const chipsContainer = document.getElementById('active-filter-chips');
      if (!bar || !chipsContainer) return;
      if (!chipsContainer.dataset.bound) {
        chipsContainer.dataset.bound = 'true';
        chipsContainer.addEventListener('click', (e) => {
          const btn = e.target.closest('[data-action]');
          if (!btn) return;
          const act = btn.dataset.action;
          if (act === 'filter-platform') setPlatformFilter(btn.dataset.platform || 'ALL');
          else if (act === 'filter-status') setDashboardStatusFilter(btn.dataset.status || 'ALL');
          else if (act === 'clear-account-filter') clearAccountFilter();
          else if (act === 'clear-search-filter') clearSearchFilter();
        });
      }

      const chips = [];

      if (appState.selected_platform !== 'ALL') {
        const pName = platName(appState.selected_platform);
        chips.push(`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/60 font-semibold">Nền tảng: ${escapeHtml(pName)} <button type="button" data-action="filter-platform" data-platform="ALL" class="hover:text-red-500 ml-0.5 inline-flex">${icon('x', 'w-3 h-3')}</button></span>`);
      }

      if (appState.selected_status && appState.selected_status !== 'ALL') {
        const statusMap = { 'READY': 'Sẵn sàng', 'NOT_SETUP': 'Chưa thiết lập', 'IN_USE': 'Đang mở', 'EXPIRED': 'Hết hạn' };
        chips.push(`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/60 font-semibold">Trạng thái: ${escapeHtml(statusMap[appState.selected_status] || appState.selected_status)} <button type="button" data-action="filter-status" data-status="ALL" class="hover:text-red-500 ml-0.5 inline-flex">${icon('x', 'w-3 h-3')}</button></span>`);
      }

      if (appState.selected_account !== 'ALL') {
        const acc = appState.accounts.find(a => a.id === appState.selected_account);
        const aName = acc ? acc.display_name : appState.selected_account;
        chips.push(`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/60 font-semibold">Tài khoản: ${escapeHtml(aName)} <button type="button" data-action="clear-account-filter" class="hover:text-red-500 ml-0.5 inline-flex">${icon('x', 'w-3 h-3')}</button></span>`);
      }

      if (appState.search_keyword) {
        chips.push(`<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-100 dark:bg-blue-900/60 font-semibold">Tìm kiếm: "${escapeHtml(appState.search_keyword)}" <button type="button" data-action="clear-search-filter" class="hover:text-red-500 ml-0.5 inline-flex">${icon('x', 'w-3 h-3')}</button></span>`);
      }

      if (chips.length > 0) {
        chipsContainer.innerHTML = [
          `<span class="font-bold text-slate-500 dark:text-slate-400">Đang lọc (${escapeHtml(String(matchingCount))}/${escapeHtml(String(totalCount))} kênh):</span>`,
          ...chips
        ].join('');
        bar.classList.remove('hidden');
      } else {
        chipsContainer.innerHTML = '';
        bar.classList.add('hidden');
      }
    }

    function clearAccountFilter() {
      appState.selected_account = 'ALL';
      const sel = document.getElementById('select-account-filter');
      if (sel) sel.value = 'ALL';
      renderDashboard();
    }

    function clearSearchFilter() {
      appState.search_keyword = '';
      const inp = document.getElementById('input-search');
      if (inp) inp.value = '';
      renderDashboard();
    }

    // Render Dashboard Cards & KPI Stats
    function renderDashboard() {
      const grid = document.getElementById('cards-grid');
      const emptyState = document.getElementById('empty-state');
      try {
        renderDashboardInner(grid, emptyState);
        if (typeof refreshDrawerIfOpen === 'function') refreshDrawerIfOpen();
      } catch (err) {
        console.error('renderDashboard:', err);
        showToast('Lỗi vẽ dashboard: ' + (err && err.message ? err.message : err), 'error');
      }
    }

    function initDashboardDelegation(grid) {
      if (!grid || grid.dataset.bound) return;
      grid.dataset.bound = 'true';
      grid.addEventListener('click', (e) => {
        const launchBtn = e.target.closest('[data-action="launch-channel"]');
        if (launchBtn && launchBtn.dataset.channelId && typeof launchChannel === 'function') {
          launchChannel(launchBtn.dataset.channelId);
          return;
        }
        const reqBtn = e.target.closest('[data-action="request-access"]');
        if (reqBtn && reqBtn.dataset.channelId && typeof requestAccess === 'function') {
          requestAccess(reqBtn.dataset.channelId);
          return;
        }
        const drawerBtn = e.target.closest('[data-action="open-drawer"]');
        if (drawerBtn && drawerBtn.dataset.channelId && typeof openChannelDrawer === 'function') {
          openChannelDrawer(drawerBtn.dataset.channelId);
          return;
        }
        const bulkBtn = e.target.closest('[data-action="start-bulk-open"]');
        if (bulkBtn && bulkBtn.dataset.accountId && typeof startBulkOpen === 'function') {
          startBulkOpen(bulkBtn.dataset.accountId);
          return;
        }
        const addChBtn = e.target.closest('[data-action="add-channel"]');
        if (addChBtn && addChBtn.dataset.accountId && typeof openAddChannelModal === 'function') {
          openAddChannelModal(addChBtn.dataset.accountId);
          return;
        }
        const editAccBtn = e.target.closest('[data-action="edit-account"]');
        if (editAccBtn && editAccBtn.dataset.accountId && typeof openEditAccountModal === 'function') {
          openEditAccountModal(editAccBtn.dataset.accountId);
          return;
        }
      });
    }

    function updateDashboardEmptyState(hasFilters, totalChannels) {
      const emptyState = document.getElementById('empty-state');
      const titleEl = document.getElementById('empty-state-title');
      const descEl = document.getElementById('empty-state-desc');
      const btnEl = document.getElementById('empty-state-btn');
      if (!emptyState) return;
      if (totalChannels === 0) {
        if (titleEl) titleEl.innerText = 'Chưa có kênh nào trong hệ thống';
        if (descEl) descEl.innerText = 'Hệ thống chưa có kênh nào. Vui lòng thêm tài khoản và kênh mới để bắt đầu.';
        if (btnEl) btnEl.classList.add('hidden');
      } else {
        if (titleEl) titleEl.innerText = 'Không tìm thấy kênh phù hợp';
        if (descEl) descEl.innerText = 'Không tìm thấy kênh phù hợp với bộ lọc hiện tại.';
        if (btnEl) btnEl.classList.remove('hidden');
      }
    }

    function renderDashboardInner(grid, emptyState) {
      initDashboardDelegation(grid);
      const filtered = appState.channels.filter(ch => {
        if (appState.selected_platform !== 'ALL' && ch.platform !== appState.selected_platform) return false;
        if (appState.selected_account !== 'ALL' && ch.account_id !== appState.selected_account) return false;
        if (appState.selected_status && appState.selected_status !== 'ALL' && ch.status !== appState.selected_status) return false;
        if (appState.search_keyword) {
          const kw = appState.search_keyword.toLowerCase();
          const match = (ch.channel_name && ch.channel_name.toLowerCase().includes(kw)) || 
                        (ch.id && ch.id.toLowerCase().includes(kw)) || 
                        (ch.account_email && ch.account_email.toLowerCase().includes(kw)) ||
                        (ch.account_display_name && ch.account_display_name.toLowerCase().includes(kw));
          if (!match) return false;
        }
        return true;
      });

      // Update KPIs & Badges (dựa trên toàn bộ dữ liệu hệ thống)
      const totalCount = appState.channels.length;
      document.getElementById('stat-total').innerText = totalCount;
      document.getElementById('stat-ready').innerText = appState.channels.filter(c => c.status === 'READY').length;
      document.getElementById('stat-not-setup').innerText = appState.channels.filter(c => c.status === 'NOT_SETUP').length;
      document.getElementById('stat-in-use').innerText = appState.channels.filter(c => c.status === 'IN_USE').length;
      if (typeof updateMyHeldCountBadge === 'function') updateMyHeldCountBadge();

      const topCountEl = document.getElementById('top-count');
      if (topCountEl) topCountEl.innerText = totalCount;

      // Vẽ lại badge nền tảng (đếm động theo registry)
      renderPlatformFilters();

      // Cập nhật thanh hiển thị bộ lọc đang áp dụng
      updateActiveFilterBar(filtered.length, totalCount);

      const sortOrder = appState.sort_order || 'DEFAULT';
      const platOrder = platOrderMap();
      const statusOrder = { 'IN_USE': 1, 'READY': 2, 'EXPIRED': 3, 'NOT_SETUP': 4 };

      // Map account_id -> created_at (ngày nhập tài khoản) để sort
      const accDateMap = {};
      (appState.accounts || []).forEach(a => { accDateMap[a.id] = a.created_at || ''; });
      const accDateVal = (id) => accDateMap[id] || id || '';
      const sortChannelsFn = (a, b) => {
        // Kênh ghim luôn lên đầu
        if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
        if (sortOrder === 'DATE_DESC') {
          return String(accDateVal(b.account_id)).localeCompare(String(accDateVal(a.account_id)));
        } else if (sortOrder === 'DATE_ASC') {
          return String(accDateVal(a.account_id)).localeCompare(String(accDateVal(b.account_id)));
        } else if (sortOrder === 'PLATFORM') {
          return (platOrder[a.platform] || 99) - (platOrder[b.platform] || 99);
        } else if (sortOrder === 'STATUS') {
          return (statusOrder[a.status] || 99) - (statusOrder[b.status] || 99);
        } else if (sortOrder === 'ACCOUNT') {
          return (a.account_display_name || '').localeCompare(b.account_display_name || '', 'vi');
        }
        return (platOrder[a.platform] || 99) - (platOrder[b.platform] || 99) || (a.id || '').localeCompare(b.id || '', undefined, { numeric: true });
      };

      const hasActiveFilters = appState.selected_platform !== 'ALL' || 
                               appState.selected_account !== 'ALL' || 
                               (appState.selected_status && appState.selected_status !== 'ALL') || 
                               Boolean(appState.search_keyword);

      const scrollControls = document.getElementById('horizontal-scroll-controls');

      // ========================================================
      // CHẾ ĐỘ 1: CUỘN NGANG (CỘT THEO TÀI KHOẢN, CARDS XẾP DỌC)
      // ========================================================
      if (appState.display_mode === 'HORIZONTAL') {
        if (scrollControls) {
          scrollControls.classList.remove('hidden');
          scrollControls.classList.add('flex');
        }
        // Cuộn dọc tự nhiên theo trang (không giới hạn chiều cao cột), cuộn ngang native
        grid.className = 'h-scroll flex flex-row flex-nowrap overflow-x-auto gap-5 pb-4 pt-1 items-start';

        // Gom nhóm theo từng tài khoản
        const accountGroups = [];
        const seenAccountIds = new Set();

        (appState.accounts || []).forEach(acc => {
          seenAccountIds.add(acc.id);
          const allChannelsOfAcc = appState.channels.filter(c => c.account_id === acc.id);
          const matchingChannels = filtered.filter(c => c.account_id === acc.id);
          accountGroups.push({
            id: acc.id,
            display_name: acc.display_name || acc.email || acc.id,
            email: acc.email || '',
            logo: acc.logo || '',
            created_at: acc.created_at || '',
            totalChannels: allChannelsOfAcc.length,
            matchingChannels: matchingChannels
          });
        });

        // Gom thêm các tài khoản chưa có trong bảng accounts nhưng có trong channels
        appState.channels.forEach(ch => {
          if (ch.account_id && !seenAccountIds.has(ch.account_id)) {
            seenAccountIds.add(ch.account_id);
            const allChannelsOfAcc = appState.channels.filter(c => c.account_id === ch.account_id);
            const matchingChannels = filtered.filter(c => c.account_id === ch.account_id);
            accountGroups.push({
              id: ch.account_id,
              display_name: ch.account_display_name || ch.account_email || ch.account_id,
              email: ch.account_email || '',
              totalChannels: allChannelsOfAcc.length,
              matchingChannels: matchingChannels
            });
          }
        });

        // Sắp xếp thứ tự các cột tài khoản (theo ngày nhập hoặc tên)
        accountGroups.sort((a, b) => {
          if (sortOrder === 'ACCOUNT') {
            return (a.display_name || '').localeCompare(b.display_name || '', 'vi');
          } else if (sortOrder === 'DATE_DESC') {
            return String(b.created_at || b.id || '').localeCompare(String(a.created_at || a.id || ''));
          } else if (sortOrder === 'DATE_ASC') {
            return String(a.created_at || a.id || '').localeCompare(String(b.created_at || b.id || ''));
          }
          return (a.id || '').localeCompare(b.id || '', undefined, { numeric: true });
        });

        // Lọc cột hiển thị: nếu đang lọc thì chỉ hiện cột có card khớp; nếu không lọc hiện tất cả tài khoản
        const visibleGroups = hasActiveFilters ? accountGroups.filter(g => g.matchingChannels.length > 0) : accountGroups;

        if (visibleGroups.length === 0) {
          grid.innerHTML = '';
          updateDashboardEmptyState(hasActiveFilters, totalCount);
          emptyState.classList.remove('hidden');
          return;
        }

        emptyState.classList.add('hidden');

        // Lọc theo 1 nền tảng: gộp nhiều card vào chung cột (3 card/cột) thay vì 1 card/cột
        if (appState.selected_platform !== 'ALL' && filtered.length > 0) {
          const all = filtered.slice().sort(sortChannelsFn);
          const perCol = 3;
          const chunks = [];
          for (let i = 0; i < all.length; i += perCol) chunks.push(all.slice(i, i + perCol));
          const pCode = appState.selected_platform;
          grid.innerHTML = chunks.map((cards) => {
            return `
            <div class="w-[320px] min-w-[280px] max-w-[340px] shrink-0 bg-slate-100/70 dark:bg-dark-sidebar/60 border border-slate-200 dark:border-dark-border rounded-2xl p-4 flex flex-col gap-3 shadow-xs self-start">
              <div class="flex items-center gap-2.5 pb-3 border-b border-slate-200/80 dark:border-dark-border/80 min-h-[58px] min-w-0">
                ${platBadge(pCode, 'w-9 h-9')}
                <h4 class="font-extrabold text-sm text-slate-800 dark:text-slate-100 truncate leading-tight min-w-0 flex-1">${escapeHtml(platName(pCode))}</h4>
              </div>
              <div class="flex flex-col gap-3">
                ${cards.map(ch => renderChannelCard(ch, true, true)).join('')}
              </div>
            </div>
            `;
          }).join('');
          return;
        }

        grid.innerHTML = visibleGroups.map((group, idx) => {
          // Sắp xếp card bên trong cột tài khoản
          group.matchingChannels.sort(sortChannelsFn);

          const initial = (group.display_name || 'A')[0].toUpperCase();
          const avatarGradients = [
            'from-blue-600 to-indigo-600',
            'from-purple-600 to-pink-600',
            'from-emerald-600 to-teal-600',
            'from-amber-500 to-orange-600'
          ];
          const grad = avatarGradients[idx % avatarGradients.length];

          const countBadgeText = hasActiveFilters ? `${group.matchingChannels.length} / ${group.totalChannels} thẻ kênh` : `${group.matchingChannels.length} thẻ kênh`;
          const hasPinned = group.matchingChannels.some(c => c.pinned);
          const colBorder = hasPinned
            ? 'border-amber-400/80 dark:border-amber-500/70 ring-2 ring-amber-400/25 dark:ring-amber-500/20 shadow-xs'
            : 'border-slate-200 dark:border-dark-border shadow-xs';

          const logoHtml = group.logo
            ? `<img src="${escapeHtml(group.logo)}" class="w-9 h-9 rounded-xl object-cover shrink-0 shadow-xs ring-1 ring-slate-200 dark:ring-dark-border" title="${escapeHtml(group.display_name)}">`
            : `<div class="w-9 h-9 rounded-xl bg-gradient-to-br ${grad} text-white font-extrabold text-xs flex items-center justify-center shrink-0 shadow-xs">${escapeHtml(initial)}</div>`;

          return `
            <div class="w-[320px] min-w-[280px] max-w-[340px] shrink-0 bg-slate-100/70 dark:bg-dark-sidebar/60 border ${colBorder} rounded-2xl p-4 flex flex-col gap-3 self-start">
              <!-- Cột Header Tài khoản (cố định chiều cao để các cột thẳng hàng) -->
              <div class="flex items-center justify-between gap-2 pb-3 border-b border-slate-200/80 dark:border-dark-border/80 min-h-[58px]">
                <div class="flex items-center gap-2.5 min-w-0 flex-1">
                  ${logoHtml}
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-1.5 min-w-0">
                      <h4 class="font-extrabold text-sm text-slate-800 dark:text-slate-100 truncate leading-tight" title="${escapeHtml(group.display_name)}">${escapeHtml(group.display_name)}</h4>
                      ${hasPinned ? `<span class="text-amber-500 text-xs shrink-0" title="Có kênh đã ghim">${icon('star-solid', 'w-3.5 h-3.5')}</span>` : ''}
                    </div>
                    <p class="text-[11px] text-slate-500 dark:text-slate-400 truncate leading-tight" title="${escapeHtml(group.email || '')}">${escapeHtml(group.email || 'Tài khoản Google')}</p>
                  </div>
                </div>
                <div class="flex flex-col items-end gap-1 shrink-0">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 whitespace-nowrap">
                    ${countBadgeText}
                  </span>
                  <div class="flex items-center gap-2 leading-none">
                    <button type="button" data-action="start-bulk-open" data-account-id="${escapeHtml(group.id)}" title="Mở nối tiếp tất cả kênh Sẵn sàng của tài khoản này" class="inline-flex items-center gap-0.5 text-[10px] font-bold text-sky-500 hover:text-sky-400 transition-colors">Mở hết ${icon('play', 'w-2.5 h-2.5')}</button>
                    <button type="button" data-action="add-channel" data-account-id="${escapeHtml(group.id)}" title="Thêm kênh cho tài khoản này" class="text-[10px] font-bold text-emerald-500 hover:text-emerald-400 transition-colors">+ Kênh</button>
                    <button type="button" data-action="edit-account" data-account-id="${escapeHtml(group.id)}" title="Sửa tài khoản / đổi logo" class="inline-flex items-center gap-0.5 text-[10px] font-bold text-slate-400 hover:text-blue-500 transition-colors">Sửa ${icon('pencil', 'w-2.5 h-2.5')}</button>
                  </div>
                </div>
              </div>

              <!-- Danh sách Card xếp dọc, cao tự nhiên theo trang -->
              <div class="flex flex-col gap-3">
                ${group.matchingChannels.length > 0 ?
                  group.matchingChannels.map(ch => renderChannelCard(ch, true)).join('') :
                  `<div class="py-8 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-dark-border rounded-xl">Không có kênh nào khớp bộ lọc</div>`
                }
              </div>
            </div>
          `;
        }).join('');

      } else {
        // ========================================================
        // CHẾ ĐỘ 2: LƯỚI (GRID VIEW MẶC ĐỊNH)
        // ========================================================
        if (scrollControls) {
          scrollControls.classList.add('hidden');
          scrollControls.classList.remove('flex');
        }
        grid.className = 'grid grid-cols-[repeat(auto-fill,minmax(280px,340px))] gap-4 justify-start';

        if (filtered.length === 0) {
          grid.innerHTML = '';
          updateDashboardEmptyState(hasActiveFilters, totalCount);
          emptyState.classList.remove('hidden');
          return;
        }

        emptyState.classList.add('hidden');
        filtered.sort(sortChannelsFn);
        grid.innerHTML = filtered.map(ch => renderChannelCard(ch, false)).join('');
      }
    }

    // Dashboard Order & Display Mode Controllers
    function setDashboardSort(order) {
      appState.sort_order = order;
      ['DEFAULT', 'DATE_DESC', 'DATE_ASC', 'PLATFORM', 'STATUS', 'ACCOUNT'].forEach(k => {
        const btn = document.getElementById(`sort-btn-${k}`);
        if (btn) {
          btn.setAttribute('aria-pressed', k === order ? 'true' : 'false');
          const baseCls = 'inline-flex items-center justify-center gap-1 px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap transition-all';
          if (k === order) {
            btn.className = `${baseCls} font-bold bg-blue-600 text-white shadow-xs`;
          } else {
            btn.className = `${baseCls} font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-dark-input hover:bg-slate-200 dark:hover:bg-slate-700`;
          }
        }
      });
      renderDashboard();
    }

    function setDashboardStatusFilter(status) {
      appState.selected_status = status;
      ['ALL', 'READY', 'NOT_SETUP', 'IN_USE', 'EXPIRED'].forEach(st => {
        const btn = document.getElementById(`status-btn-${st}`);
        if (btn) {
          btn.setAttribute('aria-pressed', st === status ? 'true' : 'false');
          if (st === status) {
            btn.className = 'px-2 py-1 rounded-md text-xs font-bold bg-blue-600 text-white shadow-xs transition-all';
          } else {
            btn.className = 'px-2 py-1 rounded-md text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-all';
          }
        }
      });
      renderDashboard();
    }

    function setDisplayMode(mode) {
      appState.display_mode = mode;
      try { localStorage.setItem('vb_display_mode', mode); } catch (e) {}
      ['GRID', 'HORIZONTAL'].forEach(m => {
        const btn = document.getElementById(`display-mode-${m}`);
        if (btn) {
          btn.setAttribute('aria-pressed', m === mode ? 'true' : 'false');
          if (m === mode) {
            btn.className = 'px-2.5 py-1 rounded-md text-xs font-bold bg-blue-600 text-white shadow-xs transition-all';
          } else {
            btn.className = 'px-2.5 py-1 rounded-md text-xs font-semibold text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white transition-all';
          }
        }
      });
      renderDashboard();
      attachSmoothHScroll();
    }

    function scrollColumns(offset) {
      const grid = document.getElementById('cards-grid');
      if (!grid) return;
      // Cuộn đúng 1 cột (340 + gap 20) cho thẳng hàng, mượt
      const step = 360;
      const dir = offset > 0 ? 1 : -1;
      grid.scrollBy({ left: dir * step, behavior: 'smooth' });
    }

    // Cuộn ngang native: Shift + lăn chuột -> ngang; còn lại để trình duyệt xử lý
    function attachSmoothHScroll() {
      const gridEl = document.getElementById('cards-grid');
      if (!gridEl || gridEl._smoothAttached) return;
      gridEl._smoothAttached = true;

      gridEl.addEventListener('wheel', (e) => {
        if (appState.display_mode !== 'HORIZONTAL') return;
        if (!e.shiftKey) return; // lăn dọc/touchpad: native, không can thiệp
        e.preventDefault();
        let dx = e.deltaY || e.deltaX;
        if (e.deltaMode === 1) dx *= 16; // Firefox: dòng -> pixel
        gridEl.scrollLeft += dx;
      }, { passive: false });
    }
