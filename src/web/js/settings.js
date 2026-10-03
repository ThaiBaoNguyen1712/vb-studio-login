// settings.js — tabs cài đặt, Firebase config, trình duyệt, cập nhật.
    // Settings tabs
    function switchSettingsTab(tabId) {
      ['tab-firebase', 'tab-browser', 'tab-vault', 'tab-theme', 'tab-data', 'tab-app'].forEach(t => {
        const el = document.getElementById(t);
        if (el) el.classList.toggle('hidden', t !== tabId);
        const btn = document.getElementById(`btn-${t}`);
        if (btn) {
          if (t === tabId) {
            btn.className = 'pb-3 border-b-2 border-blue-500 text-blue-500';
          } else {
            btn.className = 'pb-3 border-b-2 border-transparent text-slate-500 hover:text-slate-200';
          }
        }
      });
      // Tải mới nội dung tab động khi mở (bảng vault/thùng rác/trạng thái đồng bộ)
      if (tabId === 'tab-vault') renderVaultStatus();
      if (tabId === 'tab-data') {
        renderTrash();
        checkDataSyncStatus();
      }
    }

    function renderSettingsData() {
      const browser = appState.settings.browser || {};
      const dirInput = document.getElementById('cfg-browser-dir');
      if (dirInput) dirInput.value = browser.profiles_dir || './profiles';
      const stealthInput = document.getElementById('cfg-browser-stealth');
      if (stealthInput) stealthInput.checked = browser.disable_bot_detection !== false;
      const soundInput = document.getElementById('cfg-sound-enabled');
      if (soundInput) soundInput.checked = !appState.settings.general || appState.settings.general.enable_sound_notifications !== false;
      const popupInput = document.getElementById('cfg-popup-enabled');
      if (popupInput) popupInput.checked = !appState.settings.general || appState.settings.general.enable_request_popup !== false;
      const verEl = document.getElementById('app-current-version-label');
      if (verEl && appState.settings && appState.settings.app_info && appState.settings.app_info.version) {
        verEl.innerText = appState.settings.app_info.version;
      }

      renderAuthUI();

      renderSocialsTable();
      renderVaultStatus();
    }

    // Bật/tắt popup overlay nổi khi có người xin mở kênh
    async function setRequestPopup(on) {
      try {
        if (!appState.settings.general) appState.settings.general = {};
        appState.settings.general.enable_request_popup = !!on;
        await window.pywebview.api.save_settings({ general: { enable_request_popup: !!on } });
        showToast(on ? 'Đã bật popup nổi khi có yêu cầu!' : 'Đã tắt popup nổi.', 'info');
      } catch (err) {
        showToast('Lỗi lưu cài đặt popup: ' + err, 'error');
      }
    }

    // Hiện popup thử (dữ liệu mock demo, có thể bấm thử nhiều lần liên tục)
    async function testRequestPopup() {
      try {
        const mockReq = {
          id: '__demo_' + Date.now(),
          channel_id: 'ch_demo_101',
          channel_name: 'YouTube Shorts - Kênh Demo 01',
          requester: 'Đồng đội (Demo User)',
          message: 'Cho mình mượn kênh 15 phút để kiểm tra và upload video nhé!'
        };
        const res = await window.pywebview.api.show_request_popup(mockReq);
        if (!(res && res.success)) showToast((res && res.message) || 'Không mở được popup!', 'error');
      } catch (err) {
        showToast('Lỗi mở popup: ' + err, 'error');
      }
    }

    let latestUpdateInfo = null;

    async function checkForUpdates() {
      showAsyncLoading('Kiểm tra cập nhật...');
      showToast('Đang kiểm tra cập nhật...', 'info');
      try {
        const res = await window.pywebview.api.check_for_updates();
        latestUpdateInfo = res;

        if (res && res.has_update) {
          const newVerEl = document.getElementById('update-new-version');
          if (newVerEl) newVerEl.innerText = res.latest_version || 'Mới nhất';
          const curVerEl = document.getElementById('update-cur-version');
          if (curVerEl) curVerEl.innerText = res.current_version || 'v1.0.0';
          const notesEl = document.getElementById('update-release-notes');
          if (notesEl) notesEl.innerText = res.release_notes || 'Không có ghi chú phát hành.';
          
          // Reset progress bar
          const prog = document.getElementById('update-progress-container');
          if (prog) prog.classList.add('hidden');
          const btnApply = document.getElementById('btn-apply-update');
          if (btnApply) {
            btnApply.disabled = false;
            btnApply.classList.remove('opacity-50', 'cursor-not-allowed');
          }

          const modal = document.getElementById('modal-update-dialog');
          if (modal) modal.classList.remove('hidden');
          showToast(`Phát hiện phiên bản mới: ${res.latest_version}!`, 'info');
        } else {
          showToast((res && res.message) || 'Bạn đang sử dụng phiên bản mới nhất!', (res && res.error) ? 'error' : 'success');
        }
      } catch (err) {
        showToast('Lỗi kiểm tra cập nhật: ' + err, 'error');
      } finally {
        hideAsyncLoading();
      }
    }

    function closeUpdateDialog() {
      const modal = document.getElementById('modal-update-dialog');
      if (modal) modal.classList.add('hidden');
    }

    async function openGitHubRelease() {
      try {
        const url = latestUpdateInfo ? latestUpdateInfo.html_url : null;
        await window.pywebview.api.open_release_page(url);
      } catch (err) {
        showToast('Lỗi mở trình duyệt: ' + err, 'error');
      }
    }

    async function applyUpdateNow() {
      if (!latestUpdateInfo || !latestUpdateInfo.download_url) {
        showToast('Không tìm thấy file exe direct trong Release. Đang mở trang GitHub...', 'info');
        openGitHubRelease();
        return;
      }

      const progContainer = document.getElementById('update-progress-container');
      const progBar = document.getElementById('update-progress-bar');
      const progPercent = document.getElementById('update-progress-percent');
      const btnApply = document.getElementById('btn-apply-update');

      if (progContainer) progContainer.classList.remove('hidden');
      if (progBar) progBar.style.width = '0%';
      if (progPercent) progPercent.innerText = '0%';
      if (btnApply) {
        btnApply.disabled = true;
        btnApply.classList.add('opacity-50', 'cursor-not-allowed');
      }

      showToast('Đang tải bản cập nhật...', 'info');

      try {
        const res = await window.pywebview.api.download_and_apply_update(latestUpdateInfo.download_url);
        if (res && res.success) {
          showToast(res.message, 'success');
          if (progPercent) progPercent.innerText = '100% (Đang khởi động lại...)';
          if (progBar) progBar.style.width = '100%';
        } else {
          showToast((res && res.message) || 'Cập nhật thất bại!', 'error');
          if (btnApply) {
            btnApply.disabled = false;
            btnApply.classList.remove('opacity-50', 'cursor-not-allowed');
          }
        }
      } catch (err) {
        showToast('Lỗi cập nhật: ' + err, 'error');
        if (btnApply) {
          btnApply.disabled = false;
          btnApply.classList.remove('opacity-50', 'cursor-not-allowed');
        }
      }
    }

    // Lắng nghe tiến độ tải cập nhật từ Python
    window.addEventListener('update_download_progress', (e) => {
      const pct = e.detail?.percent || 0;
      const progBar = document.getElementById('update-progress-bar');
      const progPercent = document.getElementById('update-progress-percent');
      if (progBar) progBar.style.width = `${pct}%`;
      if (progPercent) progPercent.innerText = `${pct}%`;
    });


    async function browseProfilesFolder() {
      const path = await window.pywebview.api.browse_folder();
      if (path) document.getElementById('cfg-browser-dir').value = path;
    }

    async function saveBrowserSettings() {
      showBlockingLoading('Đang lưu cấu hình trình duyệt...');
      try {
        const data = {
          browser: {
            profiles_dir: document.getElementById('cfg-browser-dir').value.trim(),
            disable_bot_detection: document.getElementById('cfg-browser-stealth').checked
          }
        };
        await window.pywebview.api.save_settings(data);
        showToast('Đã lưu cấu hình trình duyệt!', 'success');
      } catch (err) {
        showToast('Lỗi lưu cấu hình: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    function backupFeedback(msg, ok) {
      const fb = document.getElementById('backup-feedback');
      if (fb) {
        fb.innerText = msg;
        fb.className = 'text-xs font-semibold ' + (ok ? 'text-emerald-400' : 'text-rose-400');
      }
    }

    async function exportBackup() {
      const password = (document.getElementById('backup-password')?.value || '');
      const includeProfiles = !!document.getElementById('backup-include-profiles')?.checked;
      showBlockingLoading('Đang đóng gói backup...');
      try {
        const savePath = await window.pywebview.api.pick_save_backup_path();
        if (!savePath) return; // người dùng bấm Hủy
        const res = await window.pywebview.api.export_backup(savePath, includeProfiles, password);
        if (res && res.success) {
          backupFeedback(res.message, true);
          showToast(res.message, 'success');
        } else {
          backupFeedback((res && res.message) || 'Lỗi xuất backup!', false);
          showToast((res && res.message) || 'Lỗi xuất backup!', 'error');
        }
      } catch (err) {
        backupFeedback('Lỗi xuất backup: ' + err, false);
        showToast('Lỗi xuất backup: ' + err, 'error');
      } finally {
        hideBlockingLoading();
      }
    }

    async function importBackup() {
      const password = (document.getElementById('backup-password')?.value || '');
      try {
        const zipPath = await window.pywebview.api.pick_backup_file();
        if (!zipPath) return; // người dùng bấm Hủy
        const ok = await showConfirm({
          title: 'Nhập backup',
          message: `Nhập backup từ file đã chọn? Dữ liệu hiện tại được sao lưu an toàn trước khi ghi đè, app sẽ tải lại sau khi xong.`,
          okText: 'Nhập backup'
        });
        if (!ok) return;
        showBlockingLoading('Đang nhập backup...');
        try {
          const res = await window.pywebview.api.import_backup(zipPath, password);
          if (res && res.success) {
            backupFeedback(res.message, true);
            showToast(res.message + ' Đang tải lại...', 'success');
            setTimeout(() => location.reload(), 1500);
          } else {
            backupFeedback((res && res.message) || 'Lỗi nhập backup!', false);
            showToast((res && res.message) || 'Lỗi nhập backup!', 'error');
          }
        } finally {
          hideBlockingLoading();
        }
      } catch (err) {
        backupFeedback('Lỗi nhập backup: ' + err, false);
        showToast('Lỗi nhập backup: ' + err, 'error');
      }
    }

    // Auto-refresh cố định 15s — không cho đổi, không hiển thị trong Settings.

    // Kiểm tra trạng thái đồng bộ Firebase (Cloud Sync) — chỉ hiển thị trạng thái kết nối, không hiện thông tin cấu hình
    async function checkDataSyncStatus() {
      const dot = document.getElementById('data-sync-dot');
      const text = document.getElementById('data-sync-text');
      const time = document.getElementById('data-sync-time');
      const btn = document.getElementById('btn-check-data-sync');

      if (btn) btn.disabled = true;
      if (text) {
        text.className = 'font-semibold text-slate-500 dark:text-slate-400 truncate';
        text.textContent = 'Đang kiểm tra kết nối đồng bộ...';
      }
      if (dot) dot.className = 'w-2.5 h-2.5 rounded-full bg-sky-400 animate-pulse shrink-0';

      try {
        const res = await window.pywebview.api.test_firebase_connection();
        const nowStr = new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        if (res && res.success) {
          if (dot) dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0';
          if (text) {
            text.className = 'font-semibold text-emerald-600 dark:text-emerald-400 truncate';
            text.textContent = 'Dữ liệu đã được đồng bộ với Đám mây (Firebase Realtime)';
          }
          if (time) time.textContent = `Kiểm tra lúc ${nowStr}`;
        } else {
          if (dot) dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0';
          if (text) {
            text.className = 'font-semibold text-amber-600 dark:text-amber-400 truncate';
            text.textContent = 'Chưa đồng bộ Đám mây (Đang hoạt động Ngoại tuyến / Local JSON)';
          }
          if (time) time.textContent = `Kiểm tra lúc ${nowStr}`;
        }
      } catch (err) {
        if (dot) dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0';
        if (text) {
          text.className = 'font-semibold text-rose-600 dark:text-rose-400 truncate';
          text.textContent = 'Không thể kiểm tra đồng bộ (Ngoại tuyến)';
        }
      } finally {
        if (btn) btn.disabled = false;
      }
    }
