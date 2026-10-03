// app.js — boot, pywebview bridge events, navigation, refresh 15s, tìm kiếm/lọc chung.
    async function checkFirebaseStatus() {
      try {
        await window.pywebview.api.test_firebase_connection();
      } catch (err) {
        console.warn('checkFirebaseStatus:', err);
      }
    }

    // Initialize application when pywebview is ready (+ fallback poll nếu event đến sớm/muộn)
    let hasBooted = false;
    async function bootApp(retries = 30) {
      if (hasBooted) return;
      if (!window.pywebview || !window.pywebview.api || typeof window.pywebview.api.get_initial_data !== 'function' || typeof window.pywebview.api.create_account !== 'function') {
        if (retries <= 0) {
          console.error('PyWebView bridge không khả dụng. Hãy chạy qua python src/main.py, không mở file trực tiếp.');
          document.getElementById('cards-grid').innerHTML =
            '<div class="col-span-full text-center py-16 text-sm text-slate-400">Không kết nối được backend Python.<br>Hãy chạy bằng <b>python src/main.py</b> thay vì mở file trực tiếp.</div>';
          return;
        }
        setTimeout(() => bootApp(retries - 1), 150);
        return;
      }
      hasBooted = true;
      console.log('PyWebView Ready! Fetching initial data...');
      try {
        const initData = await window.pywebview.api.get_initial_data();
        appState.accounts = initData.accounts || [];
        appState.channels = initData.channels || [];
        appState.platforms = initData.platforms || [];
        appState.settings = initData.settings || {};
        
        // Kiểm tra phiên đăng nhập đã lưu
        const rawAuth = initData.auth_state?.user || appState.settings?.firebase?.auth_user || null;
        if (rawAuth && rawAuth.email && isEmailAllowed(rawAuth.email)) {
          appState.auth_user = rawAuth;
          appState.active_user = rawAuth.displayName || rawAuth.email;
        } else {
          appState.auth_user = null;
          appState.active_user = appState.settings?.general?.default_user || 'Admin';
        }

        renderAuthUI();
        renderOperator();
        appState.access_requests = initData.access_requests || [];
        renderAccountFilters();
        renderPlatformFilters();
        renderBranchPlatforms();
        renderTablePlatformOptions();
        renderSettingsData();
        setDisplayMode(appState.display_mode);
        applySidebarState();
        try { renderBell(); } catch (e) {}
        try { startPresenceLoops(); } catch (e) {}
        // Tự động quét phiên cố định 15s — chạy ngay, không cho đổi, không hiển thị
        startAutoRefresh(15);

        // Kiểm tra ngầm trạng thái kết nối Firebase khi start app
        checkFirebaseStatus();

        // Gắn cuộn ngang mượt: kéo-thả chuột + Shift+wheel + touchpad ngang
        attachSmoothHScroll();
      } catch (err) {
        console.error('Lỗi khởi tạo:', err);
        showToast('Lỗi tải dữ liệu từ backend: ' + err, 'error');
      }
    }
    window.addEventListener('pywebviewready', () => bootApp());
    // Fallback poll nếu listener đăng ký sau khi event đã phát
    setTimeout(() => {
      if (!hasBooted) bootApp();
    }, 500);

    // Event listener from backend
    window.addEventListener('channel_status_changed', (e) => {
      const { channel_id, status, locked_by } = e.detail;
      const ch = appState.channels.find(c => c.id === channel_id);
      if (ch) {
        ch.status = status;
        ch.locked_by = locked_by;
        if ('in_use_since' in e.detail) ch.in_use_since = e.detail.in_use_since;
        if ('last_heartbeat' in e.detail) ch.last_heartbeat = e.detail.last_heartbeat;
        renderDashboard();
        renderTableRows();
      } else {
        refreshData(true);
      }
    });

    window.addEventListener('access_request_changed', async (e) => {
      const d = e.detail || {};
      try { await refreshAccessRequests(); } catch (err) {}
      const me = appState.active_user || '';
      if (d.holder === me && d.requester) {
        showToast(`${d.requester} xin mở kênh ${d.channel_id || ''}. Mở panel chuông để duyệt!`, 'warning');
        try { await notifyImportant('request', 'Xin mở kênh', `${d.requester} xin mở ${d.channel_id || ''}`); } catch (err) {}
      } else if (d.action === 'approve' && d.channel_id) {
        showToast(`Kênh ${d.channel_id} đã được nhường. Bạn có thể mở ngay!`, 'success');
        try { await notifyImportant('approve', 'Được nhường kênh', `${d.channel_id} đã được nhường. Mở ngay!`); } catch (err) {}
        try { await window.pywebview.api.close_channel_popups(d.channel_id); } catch (err) {}
        refreshData(true);
      } else if (d.action === 'force_unlock' && d.channel_id) {
        try { await window.pywebview.api.close_channel_popups(d.channel_id); } catch (err) {}
        refreshData(true);
      } else {
        renderDashboard();
        if (appState.current_view === 'TABLE') renderTableRows();
      }
    });

    window.addEventListener('channel_error', (e) => {
      showToast(e.detail.error, 'error');
    });

    // Tự lưu phiên định kỳ từ backend: refresh ngầm, debounce để khỏi render dồn
    let _lastAutosaveRefresh = 0;
    window.addEventListener('session_autosaved', (e) => {
      const now = Date.now();
      if (now - _lastAutosaveRefresh > 60000) {
        _lastAutosaveRefresh = now;
        refreshData(true);
      }
    });

    window.addEventListener('auth_state_changed', (e) => {
      const user = e.detail;
      if (user && user.email) {
        if (!isEmailAllowed(user.email)) {
          showToast(`Tài khoản không được cấp quyền truy cập!`, 'error');
          appState.auth_user = null;
          renderAuthUI();
          const gateErr = document.getElementById('auth-gate-error');
          if (gateErr) {
            gateErr.innerText = `Tài khoản "${user.email}" không được cấp quyền truy cập hệ thống. Vui lòng liên hệ quản trị viên!`;
            gateErr.classList.remove('hidden');
          }
          logoutGoogle(true);
          return;
        }
        appState.auth_user = user;
        appState.active_user = user.displayName || user.email;
        showToast(`Đã xác thực Google: ${user.displayName || user.email}!`, 'success');
      } else {
        appState.auth_user = null;
        appState.active_user = appState.settings?.general?.default_user || 'Admin';
        showToast('Đã đăng xuất tài khoản Google.', 'info');
      }
      renderAuthUI();
      renderOperator();
      checkFirebaseStatus();
    });

    // Navigation View Switcher
    function switchView(viewCode) {
      appState.current_view = viewCode;
      document.getElementById('view-dashboard').classList.toggle('hidden', viewCode !== 'DASHBOARD');
      document.getElementById('view-table').classList.toggle('hidden', viewCode !== 'TABLE');
      document.getElementById('view-socials').classList.toggle('hidden', viewCode !== 'SOCIALS');
      document.getElementById('view-health').classList.toggle('hidden', viewCode !== 'HEALTH');
      document.getElementById('view-settings').classList.toggle('hidden', viewCode !== 'SETTINGS');

      // Update Nav Buttons
      ['DASHBOARD', 'TABLE', 'SOCIALS', 'HEALTH', 'SETTINGS'].forEach(code => {
        const btn = document.getElementById(`nav-btn-${code.toLowerCase()}`);
        if (!btn) return;
        if (code === viewCode) {
          btn.className = 'sb-center w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-bold transition-all bg-blue-600 text-white shadow-sm shadow-blue-500/20';
        } else {
          btn.className = 'sb-center w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-semibold text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-dark-card transition-all';
        }
      });

      if (viewCode === 'TABLE') renderTableRows();
      if (viewCode === 'SOCIALS') renderSocialsTable();
      if (viewCode === 'HEALTH' && typeof renderHealth === 'function') renderHealth();
    }

    // Set Platform Filter
    async function refreshData(silent = false) {
      if (!silent) showAsyncLoading('Đang cập nhật dữ liệu...');
      try {
        const initData = await window.pywebview.api.get_initial_data();
        appState.accounts = initData.accounts || [];
        appState.channels = initData.channels || [];
        if (initData.access_requests) {
          appState.access_requests = initData.access_requests || [];
          try { renderBell(); } catch (e) {}
        }
        if (initData.platforms) {
          appState.platforms = initData.platforms;
          renderBranchPlatforms();
          renderTablePlatformOptions();
          if (appState.current_view === 'SETTINGS') renderSocialsTable();
        }
        renderDashboard();
        if (appState.current_view === 'TABLE') renderTableRows();
        if (appState.current_view === 'HEALTH' && typeof refreshHealth === 'function') refreshHealth(false);
        try { if (typeof updateMyHeldCountBadge === 'function') updateMyHeldCountBadge(); } catch (e) {}
        if (!silent) showToast('Đã làm mới dữ liệu!', 'info');
      } catch (err) {
        if (!silent) showToast('Lỗi làm mới: ' + err, 'error');
      } finally {
        if (!silent) hideAsyncLoading();
      }
    }

    // Tự động quét phiên mỗi N giây (mặc định 15s, chạy ngay không cần setup)
    let autoRefreshTimer = null;
    function startAutoRefresh(seconds) {
      if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
      }
      const s = parseInt(seconds, 10);
      if (!s || s <= 0) return;
      autoRefreshTimer = setInterval(() => refreshData(true), s * 1000);
    }

    // Search and Filters (realtime cho cả Dashboard + Table)
    function onSearchInput() {
      appState.search_keyword = document.getElementById('input-search').value.trim();
      renderDashboard();
      if (appState.current_view === 'TABLE') renderTableRows();
    }

    function onAccountFilterChange() {
      appState.selected_account = document.getElementById('select-account-filter').value;
      renderDashboard();
      if (appState.current_view === 'TABLE') renderTableRows();
    }

    function onSortOrderChange() {
      const sel = document.getElementById('select-sort-order');
      if (sel) {
        appState.sort_order = sel.value;
        renderDashboard();
      }
    }

    function clearFilters() {
      const inp = document.getElementById('input-search');
      if (inp) inp.value = '';
      appState.search_keyword = '';
      appState.selected_platform = 'ALL';
      appState.selected_account = 'ALL';
      appState.selected_status = 'ALL';
      const selAcc = document.getElementById('select-account-filter');
      if (selAcc) selAcc.value = 'ALL';
      setPlatformFilter('ALL');
      setDashboardSort('DEFAULT');
      setDashboardStatusFilter('ALL');
    }
